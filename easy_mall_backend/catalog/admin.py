from django.contrib import admin
from django.utils.translation import ngettext

from .models import Category, Favorite, Product, ProductIdentity, ProductImage, ProductVariant, ProductVideo, SavedSearch


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Point important : avant cet enregistrement, rien dans l'application ne
    faisait jamais passer `moderation_status` de "pending" à "approved" — les
    annonces créées via le tableau de bord vendeur restaient donc invisibles
    dans le catalogue public indéfiniment. Les actions ci-dessous sont le
    premier vrai mécanisme d'approbation.
    """

    list_display = ["title", "seller", "category", "price", "currency", "status", "moderation_status", "created_at"]
    list_filter = ["status", "moderation_status", "condition", "category"]
    search_fields = ["title", "description", "seller__username", "city"]
    inlines = [ProductImageInline]
    actions = ["approve_products", "reject_products"]
    autocomplete_fields = ["comparison_identity"]

    @admin.action(description="Approuver les annonces sélectionnées")
    def approve_products(self, request, queryset):
        updated = 0
        for product in queryset.iterator():
            product.moderation_status = Product.ModerationStatus.APPROVED
            product.save(update_fields=["moderation_status"])
            updated += 1
        self.message_user(
            request,
            ngettext("%d annonce approuvée.", "%d annonces approuvées.", updated) % updated,
        )

    @admin.action(description="Rejeter les annonces sélectionnées")
    def reject_products(self, request, queryset):
        updated = 0
        for product in queryset.iterator():
            product.moderation_status = Product.ModerationStatus.REJECTED
            product.save(update_fields=["moderation_status"])
            updated += 1
        self.message_user(
            request,
            ngettext("%d annonce rejetée.", "%d annonces rejetées.", updated) % updated,
        )


@admin.register(ProductIdentity)
class ProductIdentityAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "brand", "model_name", "manufacturer_reference", "variant"]
    list_filter = ["category"]
    search_fields = ["name", "brand", "model_name", "manufacturer_reference", "variant"]
    readonly_fields = ["comparison_key", "created_at", "updated_at"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "category_type", "parent", "order", "is_active"]
    list_filter = ["category_type", "is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


admin.site.register(ProductVideo)
admin.site.register(ProductVariant)
admin.site.register(Favorite)
admin.site.register(SavedSearch)
    