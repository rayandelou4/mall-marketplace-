from django.contrib import admin

from .models import LoyaltyProgram, LoyaltyTransaction, Promotion


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ["name", "seller", "discount_type", "value", "is_active", "starts_at", "ends_at"]
    list_filter = ["is_active", "discount_type", "free_shipping"]
    search_fields = ["name", "seller__username"]
    filter_horizontal = ["products"]


@admin.register(LoyaltyProgram)
class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = ["is_active", "points_per_currency_unit", "redemption_value_per_point", "max_redemption_percent"]

    def has_add_permission(self, request):
        return not LoyaltyProgram.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ["user", "kind", "points_delta", "order", "checkout_group", "created_at"]
    list_filter = ["kind", "created_at"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["user", "kind", "points_delta", "order", "checkout_group", "created_at"]

    def has_add_permission(self, request):
        return False