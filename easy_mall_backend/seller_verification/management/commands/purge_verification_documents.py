from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from notifications.services import notify
from seller_verification.models import (
    CertificationAuditLog,
    VerificationDocument,
    VerificationRequest,
    VerificationRequestStatus,
)


class Command(BaseCommand):
    help = "Expire les demandes anciennes et supprime les justificatifs après leur durée de conservation."

    def handle(self, *args, **options):
        now = timezone.now()
        open_statuses = [
            VerificationRequestStatus.PENDING,
            VerificationRequestStatus.UNDER_REVIEW,
            VerificationRequestStatus.NEEDS_MORE_INFORMATION,
        ]
        expired_count = 0
        for request in VerificationRequest.objects.filter(
            status__in=open_statuses,
            expires_at__lte=now,
        ).iterator():
            with transaction.atomic():
                locked = VerificationRequest.objects.select_for_update().get(pk=request.pk)
                if locked.status not in open_statuses:
                    continue
                locked.status = VerificationRequestStatus.EXPIRED
                locked.save(update_fields=["status", "updated_at"])
                locked.documents.filter(retention_expires_at__isnull=True).update(
                    retention_expires_at=now + timedelta(days=90)
                )
                CertificationAuditLog.objects.create(
                    user=locked.user,
                    request=locked,
                    action=CertificationAuditLog.ActionType.REQUEST_EXPIRED,
                    details={"status": VerificationRequestStatus.EXPIRED},
                )
                transaction.on_commit(lambda user=locked.user: notify(
                    user,
                    "verification_update",
                    "Demande expirée",
                    "Votre demande a expiré. Vous pouvez en déposer une nouvelle depuis votre espace vendeur.",
                    "/vendeur?section=verification",
                ))
                expired_count += 1

        deleted_count = 0
        documents = VerificationDocument.objects.filter(
            retention_expires_at__lte=now,
            request__status__in=[
                VerificationRequestStatus.APPROVED,
                VerificationRequestStatus.REJECTED,
                VerificationRequestStatus.EXPIRED,
                VerificationRequestStatus.CANCELLED,
            ],
        )
        for document in documents.iterator():
            if document.file:
                document.file.delete(save=False)
            document.delete()
            deleted_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"{expired_count} demande(s) expirée(s), {deleted_count} document(s) supprimé(s)."
        ))