"""
Middleware Channels pour l'authentification WebSocket.

Un navigateur ne peut pas poser d'en-tête `Authorization` personnalisé à
l'ouverture d'une connexion WebSocket (contrairement à `fetch`) — le JWT
voyage donc en paramètre de requête (`wss://.../ws/messaging/<id>/?token=...`).
Équivalent, pour les WebSockets, de `JWTAuthentication` côté REST.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _get_user_from_token(token):
    User = get_user_model()
    try:
        validated = AccessToken(token)
        return User.objects.get(pk=validated["user_id"])
    except (InvalidToken, TokenError, User.DoesNotExist):
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = parse_qs(scope.get("query_string", b"").decode())
        token = query_string.get("token", [None])[0]
        scope["user"] = await _get_user_from_token(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
