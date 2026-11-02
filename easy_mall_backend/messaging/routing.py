"""
Routes WebSocket de l'app `messaging` (montées dans config/asgi.py, pas
config/urls.py — Channels route en dehors du préfixe /api/v1/ classique).
"""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/messaging/(?P<conversation_id>[0-9a-fA-F-]+)/$", consumers.ConversationConsumer.as_asgi()),
]
