"""
URLs de l'app `moderation`, montées sous `/api/v1/moderation/` (voir config/urls.py).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "moderation"

router = DefaultRouter()
router.register("reports", views.ProductReportViewSet, basename="report")
router.register("disputes", views.DisputeViewSet, basename="dispute")
router.register("message-reports", views.MessageReportViewSet, basename="message-report")
router.register("accounts", views.AccountModerationViewSet, basename="account-moderation")

urlpatterns = [
    path("", include(router.urls)),
]
