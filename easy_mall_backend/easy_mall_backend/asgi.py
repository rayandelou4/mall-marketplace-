import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "easy_mall_backend.settings")

# get_asgi_application() DOIT être appelé avant tout import qui touche aux
# modèles Django (routing/middleware ci-dessous) : c'est lui qui déclenche
# django.setup() et peuple le registre des apps.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from accounts.middleware import JWTAuthMiddleware  # noqa: E402
from messaging.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
    }
)
