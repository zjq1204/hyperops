import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from monitoring_stack.models import MonitoringCredentialAudit, MonitoringHost, MonitoringSshCredential


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
