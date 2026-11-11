from django.conf import settings
from django.utils.module_loading import import_string


def is_configured():
    return bool(settings.VISUAL_SEARCH_PROVIDER)


def get_provider():
    if not is_configured():
        return None
    return import_string(settings.VISUAL_SEARCH_PROVIDER)()