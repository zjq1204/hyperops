"""Minimal Django settings for accounts API tests."""

from datetime import timedelta

SECRET_KEY = "test-secret"
DEBUG = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "rest_framework",
    "dj_rest_auth",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "accounts",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ROOT_URLCONF = "accounts.tests.urls"

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

USE_TZ = True
SITE_ID = 1
LANGUAGE_CODE = "zh-CN"
LANGUAGES = [
    ("en-US", "English"),
    ("zh-CN", "简体中文"),
    ("es", "Español"),
]
LANGUAGE_CODE_MAPPING = {
    "en": "en-US",
    "en-us": "en-US",
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "es-es": "es",
}

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

REST_AUTH = {
    "USE_JWT": True,
    "TOKEN_MODEL": None,
    "JWT_AUTH_HTTPONLY": False,
    "SESSION_LOGIN": False,
    "USER_DETAILS_SERIALIZER": "accounts.serializers.UserDetailsSerializer",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

AUTHENTICATION_BACKENDS = (
    "accounts.auth_backends.DirectoryAwareBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
)

LDAP_CONFIG_ENCRYPTION_KEY = "test-ldap-config-key"
