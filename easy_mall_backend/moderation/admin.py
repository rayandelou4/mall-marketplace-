from django.contrib import admin
from django.utils import timezone

from .models import Dispute


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "raised_by", "status", "handled_by", "created_at", "resolved_at"]
    list_filter = ["status"]
    search_fields = ["order__id", "raised_by__username", "reason"]
    readonly_fields = ["order", "raised_by", "reason", "created_at"]
    actions = ["mark_resolved", "mark_closed"]

    @admin.action(description="Marquer comme résolu")
    def mark_resolved(self, request, queryset):
        queryset.update(status=Dispute.Status.RESOLVED, resolved_at=timezone.now(), handled_by=request.user)

    @admin.action(description="Clôturer")
    def mark_closed(self, request, queryset):
        queryset.update(status=Dispute.Status.CLOSED)
