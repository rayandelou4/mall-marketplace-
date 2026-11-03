from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateVerificationStorage(FileSystemStorage):
    def __init__(self):
        location = getattr(
            settings,
            "PRIVATE_MEDIA_ROOT",
            Path(settings.BASE_DIR).parent / "private_uploads",
        )
        super().__init__(
            location=location,
            file_permissions_mode=0o600,
            directory_permissions_mode=0o700,
        )

    def url(self, name):
        raise ValueError("Les documents de vérification ne sont pas publiquement accessibles.")


private_verification_storage = PrivateVerificationStorage()