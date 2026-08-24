import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from monitoring_stack.models import (
    MonitoringCredentialAudit,
    MonitoringHost,
    MonitoringSshCredential,
    MonitoringSshCredentialVersion,
)
from monitoring_stack.services.credential_crypto import decrypt_secret, encrypt_secret


@pytest.fixture
def api_client(db):
    user = get_user_model().objects.create_superuser(
        username="credential-admin",
        email="credential-admin@example.com",
        password="password123",
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_audit_records_are_immutable():
    record = MonitoringCredentialAudit.objects.create(action="create", status="success", credential_id_snapshot=1)
    record.status = "failed"
    with pytest.raises(ValidationError):
        record.save()


@pytest.mark.django_db
def test_referenced_credential_cannot_be_archived():
    from monitoring_stack.services.credential_lifecycle import CredentialReferenceConflict, archive_credential
    user = get_user_model().objects.create_user(username="api-user")
    credential = MonitoringSshCredential.objects.create(name="prod", created_by=user)
    MonitoringHost.objects.create(hostname="host-a", address="127.0.0.1", ssh_key_credential=credential)
    with pytest.raises(CredentialReferenceConflict):
        archive_credential(credential_id=credential.id)


@pytest.mark.django_db
def test_password_credential_api_never_returns_secret(api_client):
    response = api_client.post(
        "/api/v1/monitoring/credentials/",
        {
            "name": "shared-password",
            "credential_type": "password",
            "password": "top-secret-value",
            "password_confirm": "top-secret-value",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["credential_type"] == "password"
    assert "password" not in response.data
    assert "secret_encrypted" not in response.data
    credential = MonitoringSshCredential.objects.get(name="shared-password")
    version = credential.versions.get(version=1)
    assert decrypt_secret(version.secret_encrypted) == "top-secret-value"
    assert version.private_key_encrypted == ""


@pytest.mark.django_db
def test_password_credential_requires_confirmation(api_client):
    response = api_client.post(
        "/api/v1/monitoring/credentials/",
        {
            "name": "mismatch",
            "credential_type": "password",
            "password": "first-value",
            "password_confirm": "second-value",
        },
        format="json",
    )

    assert response.status_code == 400
    assert "password_confirm" in response.data


@pytest.mark.django_db
def test_host_can_reference_password_credential(api_client):
    credential = MonitoringSshCredential.objects.create(
        name="host-password",
        credential_type="password",
    )
    version = MonitoringSshCredentialVersion.objects.create(
        credential=credential,
        version=1,
        secret_encrypted=encrypt_secret("host-secret"),
        algorithm="password",
        validation_status=MonitoringSshCredentialVersion.VALIDATION_VALID,
    )
    credential.active_version = version
    credential.save(update_fields=["active_version"])

    response = api_client.post(
        "/api/v1/monitoring/hosts/",
        {
            "hostname": "password-host",
            "address": "10.0.0.20",
            "ssh_user": "root",
            "ssh_auth_type": "password",
            "ssh_credential_id": credential.id,
        },
        format="json",
    )

    assert response.status_code == 201
    host = MonitoringHost.objects.get(hostname="password-host")
    assert host.ssh_key_credential_id == credential.id
    assert host.ssh_password == ""
