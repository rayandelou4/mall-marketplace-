from django.contrib import admin

from .models import Commission, Payment, PaymentProvider, SupportedMarket, Wallet


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["transaction_reference", "order", "provider", "amount", "currency", "status", "created_at"]
    list_filter = ["status", "provider"]
    search_fields = ["transaction_reference", "order__id"]
    readonly_fields = ["created_at", "confirmed_at"]


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["user", "balance", "currency", "updated_at"]
    search_fields = ["user__username"]
    readonly_fields = ["updated_at"]


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ["order", "rate", "amount", "created_at"]
    search_fields = ["order__id"]


admin.site.register(PaymentProvider)
admin.site.register(SupportedMarket)
