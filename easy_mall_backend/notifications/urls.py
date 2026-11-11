"""
URLs de l'app `notifications`, montées sous `/api/v1/notifications/`.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "notifications"

router = DefaultRouter()
router.register("notifications", views.NotificationViewSet, basename="notification")

urlpatterns = [
    path("preferences/", views.NotificationPreferencesView.as_view(), name="preferences"),
    path("", include(router.urls)),
]

# GET  /notifications/                       liste des notifications de l'utilisateur
# GET  /notifications/unread_count/           nombre de non-lues
# POST /notifications/mark_all_read/          tout marquer comme lu
# POST /notifications/{id}/mark_read/         marquer une notification comme lue
