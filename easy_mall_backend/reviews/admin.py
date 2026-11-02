from django.contrib import admin

from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["reviewer", "reviewed_user", "rating", "moderation_status", "created_at"]
    list_filter = ["moderation_status", "rating"]
    search_fields = ["reviewer__username", "reviewed_user__username", "comment"]
    actions = ["approve_reviews", "reject_reviews"]

    @admin.action(description="Approuver les avis sélectionnés")
    def approve_reviews(self, request, queryset):
        queryset.update(moderation_status=Review.ModerationStatus.APPROVED)

    @admin.action(description="Rejeter les avis sélectionnés")
    def reject_reviews(self, request, queryset):
        queryset.update(moderation_status=Review.ModerationStatus.REJECTED)
