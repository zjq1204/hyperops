"""Tests for core.views.PlatformMetaView using accounts.tests.settings."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.test import override_settings


pytestmark = pytest.mark.django_db


@pytest.fixture
def authed_client(db):
    user = get_user_model().objects.create_user(
        username="meta-user", password="testpass123"
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@override_settings(ROOT_URLCONF="core.tests_meta_urls_accounts_settings")
def test_meta_view_returns_module_flags(settings, authed_client):
    settings.ENABLE_NOTIFIER = True
    settings.ENABLE_AGENTCORE_TASK = False
    settings.ENABLE_AGENTCORE_METERING = True
    settings.ENABLE_MONITORING = True
    response = authed_client.get("/")
    assert response.status_code == 200
    body = response.json()
    payload = body["data"] if isinstance(body, dict) and "data" in body else body
    assert payload == {
        "enable_notifier": True,
        "enable_agentcore_task": False,
        "enable_agentcore_metering": True,
        "enable_monitoring": True,
    }


@override_settings(ROOT_URLCONF="core.tests_meta_urls_accounts_settings")
def test_meta_view_anonymous_unauthorized():
    client = APIClient()
    response = client.get("/")
    assert response.status_code in (401, 403)
