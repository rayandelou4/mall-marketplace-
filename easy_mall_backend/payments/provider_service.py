from django.utils.module_loading import import_string

from .models import PaymentProvider


def get_payment_adapter(provider):
    if not provider.is_active or not provider.adapter_path:
        return None
    adapter_class = import_string(provider.adapter_path)
    return adapter_class()


def get_configured_providers():
    return [
        provider
        for provider in PaymentProvider.objects.filter(is_active=True).order_by("code")
        if provider.adapter_path
    ]