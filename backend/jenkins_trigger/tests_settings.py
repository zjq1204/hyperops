"""Minimal Django settings for jenkins_trigger tests."""

from datetime import timedelta

SECRET_KEY = "test-secret"
DEBUG = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "rest_framework",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "accounts",
    "gitlab_resource",
    "jenkins_trigger",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ROOT_URLCONF = "jenkins_trigger.tests_urls"

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

USE_TZ = True
SITE_ID = 1

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English")]

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",
)

LDAP_CONFIG_ENCRYPTION_KEY = "test-ldap-config-key"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"