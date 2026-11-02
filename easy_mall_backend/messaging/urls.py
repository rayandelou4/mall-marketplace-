"""
URLs de l'app `messaging`, montées sous `/api/v1/messaging/` (voir config/urls.py).
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "messaging"

router = DefaultRouter()
router.register("conversations", views.ConversationViewSet, basename="conversation")

urlpatterns = [
    path("", include(router.urls)),
]

# Routes générées automatiquement, pour référence :
#   GET  /conversations/                     liste des conversations de l'utilisateur
#   POST /conversations/start/                démarre (ou réutilise) une conversation + 1er message
#   GET  /conversations/{id}/messages/        fil de la conversation (marque les messages reçus comme lus)
#   POST /conversations/{id}/messages/        envoyer un message
