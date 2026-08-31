from django.test import override_settings
from django.urls import clear_url_caches

from accounts.access import FEATURE_KEYS, FEATURE_DEFAULT_PATHS


def test_object_storage_module_is_disabled_by_default(settings):
    assert settings.ENABLE_OBJECT_STORAGE is False


def test_object_storage_urls_are_not_registered_when_disabled(client):
    response = client.get("/api/v1/object-storage/overview/")

    assert response.status_code == 404


def test_object_storage_features_are_registered():
    assert "object_storage" in FEATURE_KEYS
    assert "admin_object_storage" in FEATURE_KEYS
    assert FEATURE_DEFAULT_PATHS["object_storage"] == "/object-storage/overview"
    assert (
        FEATURE_DEFAULT_PATHS["admin_object_storage"]
        == "/management/object-storage/overview"
    )


@override_settings(ENABLE_OBJECT_STORAGE=True)
def test_meta_view_returns_object_storage_module_flag(client, django_user_model):
    clear_url_caches()
    user = django_user_model.objects.create_user(
        username="object-storage-meta-user",
        password="secret123",
    )
    client.force_login(user)

    response = client.get("/api/v1/meta/")

    assert response.status_code == 200
    body = response.json()
    payload = body.get("data", body)
    assert payload["enable_object_storage"] is True
