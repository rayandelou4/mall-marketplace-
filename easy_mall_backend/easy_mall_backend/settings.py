"""
Paramètres du projet Mall.

Philosophie : que `python manage.py runserver` fonctionne immédiatement en
local sans dépendance externe (Postgres, Redis) à installer d'abord — chaque
service optionnel a un repli sensé pour le développement, et bascule vers la
version "production" via une variable d'environnement. Voir `.env.example`.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))

# Supporte les deux emplacements courants :
# 1) /easy_mall_backend/.env
# 2) /site internet/.env
# Cela évite que Django ignore les variables d'environnement si le .env est
# placé à la racine du workspace plutôt qu'au niveau du projet Django.
backend_env_file = BASE_DIR / ".env"
workspace_env_file = BASE_DIR.parent / ".env"

env_file_to_read = backend_env_file if backend_env_file.exists() else workspace_env_file
if env_file_to_read.exists():
    environ.Env.read_env(env_file_to_read)

SECRET_KEY = env("SECRET_KEY", default="dev-secret-key-change-me-in-production")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")  # partagé par Celery et Channels
PAYMENTS_MODE = env("PAYMENTS_MODE", default="cash")

# --------------------------------------------------------------------------
# Apps
# --------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "daphne",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Tiers
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # requis par LogoutView (blacklist du refresh token)
    "django_filters",
    "corsheaders",
    "channels",
    "cloudinary",
    "cloudinary_storage",
    # Apps du projet
    "accounts",
    "catalog",
    "orders",
    "payments",
    "messaging",  # chat temps réel via WebSocket (Channels) — voir consumers.py
    "reviews",
    "moderation",
    "analytics",
    "notifications",
    "localization",
    "seller_verification",  # système de certification des vendeurs
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # doit précéder CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "easy_mall_backend.urls"
WSGI_APPLICATION = "easy_mall_backend.wsgi.application"
ASGI_APPLICATION = "easy_mall_backend.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,  # requis par l'admin Django
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Base de données — SQLite par défaut (zéro config pour démarrer), Postgres
# via DATABASE_URL en env (voir .env.example).
# --------------------------------------------------------------------------

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Internationalisation
# --------------------------------------------------------------------------

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"  # stockage en UTC ; conversion à l'affichage côté frontend
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# Fichiers statiques / médias
# --------------------------------------------------------------------------

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Cloudinary (upload direct côté frontend / stockage distant si activé plus tard)
CLOUDINARY_CLOUD_NAME = env("CLOUDINARY_CLOUD_NAME", default="")
CLOUDINARY_API_KEY = env("CLOUDINARY_API_KEY", default="")
CLOUDINARY_API_SECRET = env("CLOUDINARY_API_SECRET", default="")
CLOUDINARY_UPLOAD_PRESET = env("CLOUDINARY_UPLOAD_PRESET", default="easy_mall_unsigned")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {
    "default": (
        {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "easy-mall-local"}
        if DEBUG
        else {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}
    ),
}

# --------------------------------------------------------------------------
# Django REST Framework
# --------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",  # sûr par défaut ; chaque vue précise déjà le sien
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {
        # Scopes utilisés via ScopedRateThrottle dans accounts/views.py
        "register": "5/hour",
        "login": "10/hour",
        "otp": "5/hour",
        "password_reset": "5/hour",
        "email_resend": "5/hour",
        "message_send": "30/minute",
        "conversation_start": "5/hour",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=30)),
    # Rotation désactivée pour l'instant : le frontend actuel ne persiste que
    # l'access token reçu au refresh, pas un éventuel nouveau refresh token.
    # Activer ROTATE_REFRESH_TOKENS supposerait de mettre à jour
    # apiClient.js (refreshAccessToken) pour stocker `data.refresh` aussi.
    "ROTATE_REFRESH_TOKENS": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# --------------------------------------------------------------------------
# CORS — autoriser le frontend Vite à appeler cette API
# --------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)

# --------------------------------------------------------------------------
# Celery — en mode "eager" par défaut en dev : les tâches (envoi d'e-mail/SMS)
# s'exécutent en synchrone dans le process, sans worker Celery ni Redis à
# lancer. Mettre CELERY_TASK_ALWAYS_EAGER=False en production.
# --------------------------------------------------------------------------

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=DEBUG)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# --------------------------------------------------------------------------
# Channels — chat temps réel (apps.messaging). En dev, channel layer en
# mémoire (aucune dépendance externe) ; en production, Redis est nécessaire
# pour que plusieurs process/workers partagent les mêmes groupes de diffusion.
# --------------------------------------------------------------------------

CHANNEL_LAYERS = {
    "default": (
        {"BACKEND": "channels.layers.InMemoryChannelLayer"}
        if DEBUG
        else {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}}
    )
}

# --------------------------------------------------------------------------
# E-mail — console en dev (les e-mails s'affichent dans le terminal au lieu
# d'être envoyés). Remplacer par un vrai fournisseur (SendGrid, SES...) avant
# la mise en production — voir tasks.py dans l'app accounts.
# --------------------------------------------------------------------------

EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
# Utilisés seulement si EMAIL_BACKEND=...smtp.EmailBackend (voir .env.example
# pour un exemple de configuration avec un vrai fournisseur).
EMAIL_HOST = env("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@mall.local")

# URL du frontend, utilisée par les tâches d'e-mail (accounts/tasks.py) pour
# construire les liens de vérification/réinitialisation (ex. .../auth?token=...).
FRONTEND_URL = env("FRONTEND_URL", default="http://localhost:5173")

