"""Minimal Django settings for monitoring_stack tests."""

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
    "monitoring_stack",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

ROOT_URLCONF = "monitoring_stack.tests_urls"

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
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
}

AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)

LDAP_CONFIG_ENCRYPTION_KEY = "test-ldap-config-key"
MONITORING_ADMIN_TOKEN = "monitor-secret"
MONITORING_CREDENTIAL_ENCRYPTION_KEYS = (
    "test-primary:a1xYkQ9g7TCNCwOu5hQG1WsNC8ftDRqMtPUmBrAIE08="
)
MONITORING_CREDENTIAL_MAX_UPLOAD_BYTES = 65536
MONITORING_CREDENTIAL_SECRET_RETENTION_DAYS = 30
MONITORING_CREDENTIAL_AGENT_TIMEOUT_SECONDS = 10
MONITORING_STACK_ROOT = "/tmp/hyperops-monitoring-tests"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
