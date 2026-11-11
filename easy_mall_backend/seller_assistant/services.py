from django.conf import settings
from django.utils.module_loading import import_string


def is_configured():
    return bool(settings.SELLER_ASSISTANT_PROVIDER)


def get_provider():
    if not is_configured():
        return None
    provider_class = import_string(settings.SELLER_ASSISTANT_PROVIDER)
    return provider_class()