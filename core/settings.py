"""
Django settings for AcePrep project.
"""

from pathlib import Path
from decouple import config
import os
import tempfile

# ----------------------------
# BASE
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config(
    "SECRET_KEY",
    default="django-insecure-^z2)4q#x5)k-qkzg4i%y-=6a%71f_44%8pbegpur82ic1f=pr=",
)

DEBUG = config("DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = [
    "*",
    "marshall-cooling-clause-buffalo.trycloudflare.com",
    "https://total-mobility-ability-schemes.trycloudflare.com",
]

CSRF_TRUSTED_ORIGINS = [
    "https://marshall-cooling-clause-buffalo.trycloudflare.com",
    "https://total-mobility-ability-schemes.trycloudflare.com",
]

# ----------------------------
# APPLICATIONS
# ----------------------------
INSTALLED_APPS = [
    "daphne",  # Must be first for ASGI support
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party apps
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "django_extensions",
    "channels",
    # Local apps
    "accounts",
    "profiles",
    "interviews",
    "companies",
    "forums",
    "ai_feedback",
    "resumes",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
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

WSGI_APPLICATION = "core.wsgi.application"
ASGI_APPLICATION = "core.asgi.application"

# Channels configuration
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# ----------------------------
# DATABASE
# ----------------------------
if os.environ.get("CI"):  # Use SQLite in Travis CI
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
    # Use a temporary directory for file uploads
    MEDIA_ROOT = tempfile.mkdtemp()
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": "team2db",
            "USER": "team2user",
            "PASSWORD": "team2pass",
            "HOST": "localhost",
            "PORT": "5432",
        }
    }
    MEDIA_ROOT = BASE_DIR / "media"

# ----------------------------
# AUTHENTICATION
# ----------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"

# ----------------------------
# INTERNATIONALIZATION
# ----------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ----------------------------
# STATIC FILES
# ----------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# ----------------------------
# MEDIA FILES
# ----------------------------
MEDIA_URL = "/media/"

# ----------------------------
# REST FRAMEWORK
# ----------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# ----------------------------
# CORS
# ----------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# ----------------------------
# CELERY
# ----------------------------
CELERY_BROKER_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# ----------------------------
# AI/ML
# ----------------------------
OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
GEMINI_API_KEY = config("GEMINI_API_KEY", default="")

# ----------------------------
# FILE UPLOADS
# ----------------------------
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # 5MB

# ----------------------------
# EMAIL
# ----------------------------
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ----------------------------
# LOGIN/LOGOUT
# ----------------------------
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/accounts/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# ----------------------------
# DEFAULT PK
# ----------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
