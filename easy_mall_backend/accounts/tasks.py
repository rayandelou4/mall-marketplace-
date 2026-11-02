"""
Tâches asynchrones (Celery) de l'app `accounts`.

Pour l'inscription, l'envoi du mail de confirmation est un prérequis métier :
si l'e-mail ne peut pas être envoyé, l'inscription est annulée pour éviter de
créer un compte non vérifiable. La règle est donc explicitement différente de
la réinitialisation du mot de passe, où un échec d'envoi ne doit pas faire
échec la demande elle-même.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def _send_verification_email(user, code):
    send_mail(
        subject="Code de vérification — Mall",
        message=(
            f"Bonjour {user.username},\n\n"
            f"Votre code de vérification est : {code}\n\n"
            "Entrez ce code dans l'application pour confirmer votre adresse e-mail. "
            "Ce code expire dans 24 heures."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


@shared_task
def send_verification_email_task(user_id, code):
    """Envoie l'e-mail de vérification contenant le code à 6 chiffres."""
    from .models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    try:
        _send_verification_email(user, code)
    except Exception:
        logger.exception("Échec de l'envoi de l'e-mail de vérification à %s", user.email)
        raise


@shared_task
def send_phone_otp_task(user_id, code):
    """Envoie le code OTP par SMS."""
    # TODO: brancher une passerelle SMS africaine (ex. Africa's Talking, Twilio)
    # — aucun compte fournisseur n'est configuré pour l'instant. En attendant,
    # le code s'affiche ici en dev pour pouvoir tester le flux de bout en bout.
    # (Vérification téléphone actuellement retirée du parcours obligatoire —
    # voir User.is_fully_verified — mais la tâche reste fonctionnelle si
    # rappelée directement.)
    if settings.DEBUG:
        print(f"[DEV] Code OTP pour l'utilisateur {user_id} : {code}")


@shared_task
def send_password_reset_email_task(user_id, code):
    """Envoie le code à 6 chiffres de réinitialisation du mot de passe."""
    from .models import User

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    try:
        send_mail(
            subject="Code de réinitialisation — Mall",
            message=(
                f"Bonjour {user.username},\n\n"
                f"Votre code de réinitialisation est : {code}\n\n"
                "Ce code expire dans 1 heure. Si vous n'êtes pas à l'origine de cette "
                "demande, ignorez simplement cet e-mail."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
    except Exception:
        logger.exception("Échec de l'envoi de l'e-mail de réinitialisation à %s", user.email)
