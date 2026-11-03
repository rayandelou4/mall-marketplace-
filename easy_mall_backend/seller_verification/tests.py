from datetime import timedelta

from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import EmailVerificationToken, User
from accounts.serializers import EmailVerificationConfirmSerializer
from orders.models import Order, OrderItem
from reviews.models import Review

from .models import (
    SellerCertification,
    VerificationCriteria,
    VerificationDocument,
    VerificationLevel,
    VerificationRequest,
    VerificationRequestStatus,
    VerificationType,
)
from .serializers import (
    UserVerificationStatusSerializer,
    VerificationDocumentSerializer,
    VerificationDocumentUploadSerializer,
    VerificationRequestSerializer,
)
from .services import CertificationCalculator, VerificationService


class EarlySellerVerificationTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.test",
            phone_number="+243800000001",
            username="seller",
            password="password-123",
            is_email_verified=True,
            first_name="Seller",
            last_name="One",
            city="Kinshasa",
            country="CD",
        )
        self.other = User.objects.create_user(
            email="other@example.test",
            phone_number="+243800000002",
            username="other",
            password="password-123",
            is_email_verified=True,
        )

    def create_request(self, user=None, status=VerificationRequestStatus.DRAFT):
        return VerificationRequest.objects.create(
            user=user or self.seller,
            verification_type=VerificationType.IDENTITY_DOCUMENT,
            target_level=VerificationLevel.LEVEL_2_IDENTITY_VERIFIED,
            status=status,
        )

    def test_profile_and_email_levels_are_derived_from_account(self):
        data = UserVerificationStatusSerializer(self.seller).data
        self.assertEqual(
            data["current_highest_level"]["level"],
            VerificationLevel.LEVEL_1_EMAIL_VERIFIED,
        )
        self.assertFalse(SellerCertification.objects.filter(user=self.seller).exists())

    def test_level_two_can_be_granted_without_preexisting_identity_certification(self):
        service = VerificationService()
        criteria = service._get_criteria_by_level()[
            VerificationLevel.LEVEL_2_IDENTITY_VERIFIED
        ]
        self.assertTrue(
            service._check_level_eligibility(
                self.seller, criteria, exclude_target_proof=True
            )
        )
        certification = service.grant_certification(
            self.seller, VerificationLevel.LEVEL_2_IDENTITY_VERIFIED
        )
        self.assertTrue(certification.is_active)

    def test_level_four_uses_completed_orders_and_transaction_reviews(self):
        criteria = VerificationCriteria.objects.create(
            level=VerificationLevel.LEVEL_4_RELIABLE_HISTORY,
            requires_transaction_count=1,
            requires_account_age_days=0,
            requires_minimum_rating=4,
            max_cancellation_rate=100,
        )
        order = Order.objects.create(buyer=self.other, status=Order.Status.DELIVERED)
        OrderItem.objects.create(
            order=order,
            seller=self.seller,
            product=None,
            product_title="Article vendu",
            quantity=1,
            unit_price=10,
        )
        Review.objects.create(
            reviewer=self.other,
            reviewed_user=self.seller,
            order=order,
            rating=5,
            moderation_status=Review.ModerationStatus.APPROVED,
        )
        self.assertIn(
            VerificationLevel.LEVEL_4_RELIABLE_HISTORY,
            CertificationCalculator.calculate_automatic_certifications(self.seller),
        )
        criteria.delete()

    def test_request_status_cannot_be_set_by_seller_api(self):
        request = APIRequestFactory().post("/")
        request.user = self.seller
        serializer = VerificationRequestSerializer(
            data={
                "verification_type": VerificationType.IDENTITY_DOCUMENT,
                "target_level": VerificationLevel.LEVEL_2_IDENTITY_VERIFIED,
                "status": VerificationRequestStatus.APPROVED,
            },
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        request = serializer.save()
        self.assertEqual(request.status, VerificationRequestStatus.DRAFT)

    def test_repeated_active_request_is_rejected_by_database(self):
        self.create_request()
        with self.assertRaises(Exception):
            self.create_request()

    def test_request_transitions_reject_invalid_states(self):
        request = self.create_request(status=VerificationRequestStatus.REJECTED)
        with self.assertRaises(Exception):
            request.submit()

    def test_revocation_removes_identity_badge_without_creating_history_badge(self):
        certification = SellerCertification.objects.create(
            user=self.seller,
            level=VerificationLevel.LEVEL_2_IDENTITY_VERIFIED,
        )
        certification.revoke(self.other, "Réexamen terminé")
        data = UserVerificationStatusSerializer(self.seller).data
        self.assertFalse(data["certifications"])
        self.assertNotEqual(
            data["current_highest_level"]["level"],
            VerificationLevel.LEVEL_4_RELIABLE_HISTORY,
        )

    def test_document_download_requires_explicit_permission(self):
        verification_request = self.create_request()
        document = VerificationDocument.objects.create(
            request=verification_request,
            document_type="identity",
            file="",
            original_filename="identity.jpg",
            file_size=20,
            mime_type="image/jpeg",
        )
        self.other.is_staff = True
        self.other.save(update_fields=["is_staff"])
        client = APIClient()
        client.force_authenticate(self.other)
        response = client.get(
            reverse("verification-document-download", args=[document.id])
        )
        self.assertEqual(response.status_code, 403)

    def test_other_user_cannot_fetch_request_or_documents(self):
        request = self.create_request()
        client = APIClient()
        client.force_authenticate(self.other)
        response = client.get(reverse("verification-request-detail", args=[request.id]))
        self.assertEqual(response.status_code, 404)

    def test_self_approval_is_rejected(self):
        request = self.create_request(status=VerificationRequestStatus.PENDING)
        permission = Permission.objects.get(codename="change_verificationrequest")
        self.seller.is_staff = True
        self.seller.save(update_fields=["is_staff"])
        self.seller.user_permissions.add(permission)
        client = APIClient()
        client.force_authenticate(self.seller)
        response = client.post(
            reverse("admin-verification-request-review", args=[request.id]),
            {"decision": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_document_upload_validates_signature_and_size(self):
        verification_request = self.create_request()
        api_request = APIRequestFactory().post("/")
        api_request.user = self.seller
        invalid = VerificationDocumentUploadSerializer(
            data={
                "document_type": "identity",
                "file": SimpleUploadedFile(
                    "fake.jpg", b"not an image", content_type="image/jpeg"
                ),
            },
            context={
                "request": api_request,
                "verification_request": verification_request,
            },
        )
        self.assertFalse(invalid.is_valid())

        oversized = VerificationDocumentUploadSerializer(
            data={
                "document_type": "identity",
                "file": SimpleUploadedFile(
                    "large.jpg",
                    b"\xff\xd8\xff" + b"0" * (10 * 1024 * 1024),
                    content_type="image/jpeg",
                ),
            },
            context={
                "request": api_request,
                "verification_request": verification_request,
            },
        )
        self.assertFalse(oversized.is_valid())

    def test_public_serializers_never_return_file_path_or_internal_notes(self):
        verification_request = self.create_request()
        verification_request.decision_notes = "internal-only"
        verification_request.save()
        serialized = VerificationRequestSerializer(verification_request).data
        self.assertNotIn("decision_notes", serialized)
        self.assertNotIn("file", serialized)

    def test_email_token_is_limited_to_five_attempts(self):
        token = EmailVerificationToken.objects.create(
            user=self.other,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        for expected_attempt in range(1, EmailVerificationToken.MAX_ATTEMPTS + 1):
            serializer = EmailVerificationConfirmSerializer(
                data={
                    "email": self.other.email,
                    "code": "000000" if token.code != "000000" else "111111",
                },
            )
            self.assertFalse(serializer.is_valid())
            token.refresh_from_db()
            self.assertEqual(token.attempts, expected_attempt)
        self.assertFalse(token.is_valid())

    def test_expired_email_token_is_rejected(self):
        EmailVerificationToken.objects.create(
            user=self.other,
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        serializer = EmailVerificationConfirmSerializer(
            data={"email": self.other.email, "code": "000000"},
        )
        self.assertFalse(serializer.is_valid())

    def test_document_serializer_does_not_expose_storage_path(self):
        document = VerificationDocument(
            request=self.create_request(),
            document_type="identity",
            original_filename="identity.jpg",
            file_size=20,
            mime_type="image/jpeg",
        )
        data = VerificationDocumentSerializer(document).data
        self.assertNotIn("file", data)
        self.assertNotIn("original_filename", data)


from decimal import Decimal

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import EmailVerificationToken, User
from accounts.serializers import EmailVerificationConfirmSerializer
from orders.models import Order, OrderItem
from reviews.models import Review

from .models import (
    CertificationAuditLog,
    SellerCertification,
    VerificationCriteria,
    VerificationDocument,
    VerificationLevel,
    VerificationRequest,
    VerificationRequestStatus,
    VerificationType,
)
from .serializers import UserVerificationStatusSerializer
from .services import VerificationService


class SellerVerificationTests(TestCase):
    def setUp(self):
        self.user = self.make_user("seller@example.test", is_email_verified=True)
        self.client = APIClient()

    def tearDown(self):
        for document in VerificationDocument.objects.all():
            if document.file:
                document.file.delete(save=False)

    @staticmethod
    def make_user(email, **fields):
        return User.objects.create_user(
            email=email,
            phone_number=f"+243{abs(hash(email)) % 10**9:09d}",
            username=email.split("@")[0],
            password="Strong-test-pass-98!",
            **fields,
        )

    def make_request(self, user=None, status=VerificationRequestStatus.DRAFT):
        return VerificationRequest.objects.create(
            user=user or self.user,
            verification_type=VerificationType.IDENTITY_DOCUMENT,
            target_level=VerificationLevel.LEVEL_2_IDENTITY_VERIFIED,
            status=status,
        )

    def make_document(self, verification_request):
        return VerificationDocument.objects.create(
            request=verification_request,
            document_type="identity",
            file=SimpleUploadedFile(
                "proof.jpg", b"\xff\xd8\xffimage-data", content_type="image/jpeg"
            ),
            original_filename="proof.jpg",
            mime_type="image/jpeg",
            is_valid_format=True,
            content_sha256="a" * 64,
        )

    def test_level_zero_and_email_level_are_derived_from_account(self):
        data = UserVerificationStatusSerializer(self.user).data
        self.assertEqual(
            data["current_highest_level"]["level"],
            VerificationLevel.LEVEL_1_EMAIL_VERIFIED,
        )
        self.assertIn("level_0", [item["level"] for item in data["eligible_levels"]])
        self.assertIn("level_1", [item["level"] for item in data["eligible_levels"]])
        self.assertFalse(SellerCertification.objects.filter(user=self.user).exists())

    def test_closed_requests_remain_visible_to_the_owner(self):
        verification_request = self.make_request(
            status=VerificationRequestStatus.REJECTED
        )
        verification_request.rejection_reason = "Le document est illisible."
        verification_request.save()
        data = UserVerificationStatusSerializer(self.user).data
        self.assertEqual(len(data["requests"]), 1)
        self.assertEqual(
            data["requests"][0]["rejection_reason"], "Le document est illisible."
        )

    def test_reputation_level_cannot_be_persisted_as_identity_certification(self):
        with self.assertRaises(ValueError):
            VerificationService().grant_certification(
                self.user, VerificationLevel.LEVEL_4_RELIABLE_HISTORY
            )

    def test_needs_more_information_can_be_resubmitted(self):
        verification_request = self.make_request(
            status=VerificationRequestStatus.NEEDS_MORE_INFORMATION
        )
        verification_request.submit()
        self.assertEqual(verification_request.status, VerificationRequestStatus.PENDING)
        self.assertIsNotNone(verification_request.submitted_at)

    def test_duplicate_open_request_is_rejected(self):
        self.make_request()
        with self.assertRaises(DjangoValidationError):
            self.make_request()

    def test_document_download_requires_explicit_permission(self):
        verification_request = self.make_request()
        document = self.make_document(verification_request)
        self.client.force_authenticate(self.user)
        response = self.client.get(
            f"/api/v1/seller-verification/documents/{document.id}/download/"
        )
        self.assertEqual(response.status_code, 403)

        reviewer = self.make_user("reviewer@example.test", is_staff=True)
        permission = Permission.objects.get(
            content_type__app_label="seller_verification",
            codename="view_verificationdocument",
        )
        reviewer.user_permissions.add(permission)
        self.client.force_authenticate(reviewer)
        response = self.client.get(
            f"/api/v1/seller-verification/documents/{document.id}/download/"
        )
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_invalid_upload_content_and_oversized_file_are_rejected(self):
        verification_request = self.make_request()
        self.client.force_authenticate(self.user)
        invalid = SimpleUploadedFile(
            "id.jpg", b"not an image", content_type="image/jpeg"
        )
        response = self.client.post(
            f"/api/v1/seller-verification/requests/{verification_request.id}/documents/",
            {"document_type": "identity", "file": invalid},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

        oversized = SimpleUploadedFile(
            "id.jpg",
            b"\xff\xd8\xff" + b"0" * VerificationDocument.MAX_FILE_SIZE,
            content_type="image/jpeg",
        )
        response = self.client.post(
            f"/api/v1/seller-verification/requests/{verification_request.id}/documents/",
            {"document_type": "identity", "file": oversized},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_vendor_api_does_not_expose_private_file_metadata_or_internal_notes(self):
        verification_request = self.make_request()
        self.make_document(verification_request)
        self.client.force_authenticate(self.user)
        response = self.client.get("/api/v1/seller-verification/status/")
        self.assertEqual(response.status_code, 200)
        rendered = str(response.data)
        for sensitive_name in (
            "original_filename",
            "mime_type",
            "file",
            "decision_notes",
            "notes",
        ):
            self.assertNotIn(sensitive_name, rendered)

    def test_user_cannot_approve_own_request_even_with_admin_permission(self):
        verification_request = self.make_request(
            status=VerificationRequestStatus.PENDING
        )
        self.make_document(verification_request)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        permission = Permission.objects.get(
            content_type__app_label="seller_verification",
            codename="change_verificationrequest",
        )
        self.user.user_permissions.add(permission)
        self.client.force_authenticate(self.user)
        response = self.client.post(
            f"/api/v1/seller-verification/admin/verification-requests/{verification_request.id}/review/",
            {"decision": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(SellerCertification.objects.filter(user=self.user).exists())

    def test_authorized_review_grants_identity_certification_and_audit(self):
        verification_request = self.make_request(
            status=VerificationRequestStatus.PENDING
        )
        self.make_document(verification_request)
        reviewer = self.make_user("admin@example.test", is_staff=True)
        permission = Permission.objects.get(
            content_type__app_label="seller_verification",
            codename="change_verificationrequest",
        )
        reviewer.user_permissions.add(permission)
        self.client.force_authenticate(reviewer)
        response = self.client.post(
            f"/api/v1/seller-verification/admin/verification-requests/{verification_request.id}/review/",
            {"decision": "approve"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(
            SellerCertification.objects.filter(
                user=self.user,
                level=VerificationLevel.LEVEL_2_IDENTITY_VERIFIED,
                revoked_at__isnull=True,
            ).exists()
        )
        self.assertEqual(
            verification_request.__class__.objects.get(
                pk=verification_request.pk
            ).status,
            VerificationRequestStatus.APPROVED,
        )
        self.assertTrue(
            CertificationAuditLog.objects.filter(
                request=verification_request,
                action=CertificationAuditLog.ActionType.REQUEST_APPROVED,
            ).exists()
        )

    def test_reputation_uses_completed_transactions_not_profile_counters(self):
        self.user.total_sales = 100
        self.user.average_rating = Decimal("5.00")
        self.user.save(update_fields=["total_sales", "average_rating"])
        criteria = VerificationCriteria.objects.create(
            level=VerificationLevel.LEVEL_4_RELIABLE_HISTORY,
            requires_email_verification=True,
            requires_transaction_count=1,
            requires_account_age_days=0,
            requires_minimum_rating=Decimal("4.00"),
            max_cancellation_rate=Decimal("100.00"),
            requires_no_active_disputes=False,
        )
        service = VerificationService()
        self.assertFalse(service._check_level_eligibility(self.user, criteria))

        buyer = self.make_user("buyer@example.test", is_email_verified=True)
        order = Order.objects.create(buyer=buyer, status=Order.Status.DELIVERED)
        OrderItem.objects.create(
            order=order,
            seller=self.user,
            product=None,
            product_title="Article vendu",
            quantity=1,
            unit_price=Decimal("12.00"),
        )
        Review.objects.create(
            reviewer=buyer,
            reviewed_user=self.user,
            order=order,
            rating=4,
        )
        self.assertTrue(service._check_level_eligibility(self.user, criteria))


class EmailVerificationTokenTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="new-user@example.test",
            phone_number="+243811111111",
            username="new-user",
            password="Strong-test-pass-98!",
            is_active=False,
            is_email_verified=False,
        )

    def test_wrong_code_consumes_attempt_and_expired_code_is_invalid(self):
        token = EmailVerificationToken.objects.create(
            user=self.user,
            code="123456",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        wrong_code = "000000" if token.code != "000000" else "000001"
        serializer = EmailVerificationConfirmSerializer(
            data={"email": self.user.email, "code": wrong_code}
        )
        self.assertFalse(serializer.is_valid())
        token.refresh_from_db()
        self.assertEqual(token.attempts, 1)

        expired = EmailVerificationToken.objects.create(
            user=self.user,
            code="654321",
            expires_at=timezone.now() - timezone.timedelta(seconds=1),
        )
        self.assertFalse(expired.is_valid())

    def test_email_code_is_single_use(self):
        token = EmailVerificationToken.objects.create(
            user=self.user,
            code="123456",
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )
        serializer = EmailVerificationConfirmSerializer(
            data={"email": self.user.email, "code": token.code}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)
        self.assertTrue(EmailVerificationToken.objects.get(pk=token.pk).is_used)

        replay = EmailVerificationConfirmSerializer(
            data={"email": self.user.email, "code": token.code}
        )
        self.assertFalse(replay.is_valid())
