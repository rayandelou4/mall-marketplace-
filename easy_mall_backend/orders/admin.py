from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = [
        "product", "product_title", "seller", "quantity", "unit_price",
        "original_unit_price", "promotion_discount", "promotion_name",
        "loyalty_discount", "loyalty_points_redeemed", "shipping_cost",
        "original_shipping_cost",
    ]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "buyer", "status", "total_amount", "currency", "created_at"]
    list_filter = ["status", "currency"]
    search_fields = ["id", "buyer__username", "buyer__email"]
    inlines = [OrderItemInline]
    readonly_fields = ["created_at", "updated_at", "total_amount"]
