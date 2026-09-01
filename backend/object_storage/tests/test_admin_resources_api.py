import pytest

from object_storage.crypto import encrypt_secret

pytestmark = pytest.mark.django_db


def _payload(response):
    body = response.json()
    return body.get("data", body)


@pytest.fixture(autouse=True)
def stable_secret(settings):
    settings.SECRET_KEY = "admin-resource-api-contract-stable-secret"


@pytest.fixture
def admin_client(client, django_user_model):
    user = django_user_model.objects.create_superuser(
        username="storage-resource-admin", password="secret123"
    )
    client.force_login(user)
    return client, user


def _key(identity, number=1):
    from object_storage.models import AccessKey

    return AccessKey.objects.create(
        cloud_identity=identity,
        access_key_id_encrypted=encrypt_secret(f"LTAI-admin-{number}"),
        secret_access_key_encrypted=encrypt_secret(f"admin-secret-{number}"),
        access_key_fingerprint=f"admin-fingerprint-{number}",
        access_key_last_four=f"{number:04d}",
        local_state=AccessKey.LocalState.ACTIVE,
    )


def test_admin_resource_lists_and_details_are_platform_scoped_and_secret_free(
    admin_client,
    cloud_identity_factory,
    bucket_factory,
    application_batch_factory,
):
    client, _admin = admin_client
    identity = cloud_identity_factory(state="active")
    bucket = bucket_factory(cloud_identity=identity)
    key = _key(identity)
    batch = application_batch_factory(applicant=identity.user, item_count=1)

    urls = [
        "/api/v1/object-storage/management/cloud-identities/",
        "/api/v1/object-storage/management/buckets/",
        "/api/v1/object-storage/management/access-keys/",
        "/api/v1/object-storage/management/applications/",
        "/api/v1/object-storage/management/audit-events/",
        f"/api/v1/object-storage/management/cloud-identities/{identity.id}/",
        f"/api/v1/object-storage/management/buckets/{bucket.id}/",
        f"/api/v1/object-storage/management/access-keys/{key.id}/",
        f"/api/v1/object-storage/management/applications/{batch.id}/",
    ]
    responses = [client.get(url) for url in urls]
    serialized = " ".join(response.content.decode() for response in responses)

    assert all(response.status_code == 200 for response in responses)
    assert "LTAI-admin-1" not in serialized
    assert "admin-secret-1" not in serialized
    assert key.access_key_id_encrypted not in serialized
    assert key.secret_access_key_encrypted not in serialized
    assert "tenant_id" not in serialized


def test_admin_application_detail_includes_safe_attempt_diagnostics(
    admin_client, application_batch_factory
):
    from object_storage.models import ApplicationAttempt, ApplicationEvent

    client, _admin = admin_client
    batch = application_batch_factory(item_count=1)
    item = batch.items.get()
    attempt = ApplicationAttempt.objects.create(
        application_item=item,
        attempt_number=1,
        status=ApplicationAttempt.Status.FAILED,
        provider_request_id="safe-provider-request-id",
        error_code="PROVIDER_TIMEOUT",
    )
    ApplicationEvent.objects.create(
        application_item=item,
        attempt=attempt,
        stage="BUCKET_CREATING",
        result="failed",
        error_code="PROVIDER_TIMEOUT",
    )

    response = client.get(f"/api/v1/object-storage/management/applications/{batch.id}/")

    payload = _payload(response)
    assert response.status_code == 200
    assert payload["items"][0]["attempts"][0]["provider_request_id"] == (
        "safe-provider-request-id"
    )
    assert payload["items"][0]["events"][0]["stage"] == "BUCKET_CREATING"


@pytest.mark.parametrize("action", ["disable", "enable", "rotate", "revoke"])
def test_admin_key_actions_target_one_key(
    admin_client, cloud_identity_factory, monkeypatch, action
):
    client, admin = admin_client
    identity = cloud_identity_factory(state="active")
    key = _key(identity)
    sibling = _key(identity, 2)
    calls = []

    def operation(**kwargs):
        calls.append(kwargs)
        return key

    monkeypatch.setattr(
        f"object_storage.views_admin.{action}_access_key_action", operation
    )
    response = client.post(
        f"/api/v1/object-storage/management/access-keys/{key.id}/{action}/",
        {"reason": "support action"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=f"admin-key-{action}-1",
    )

    sibling.refresh_from_db()
    assert response.status_code == 200
    assert calls[0]["access_key"].id == key.id
    assert calls[0]["actor"] == admin
    assert sibling.local_state == "active"


def test_admin_reveal_requires_reason_is_no_store_and_audited(
    admin_client, cloud_identity_factory
):
    from object_storage.models import AuditEvent

    client, admin = admin_client
    identity = cloud_identity_factory()
    key = _key(identity, 7)
    url = f"/api/v1/object-storage/management/access-keys/{key.id}/reveal/"
    missing = client.post(
        url,
        {},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="reveal-missing-reason",
    )
    revealed = client.post(
        url,
        {"reason": "incident investigation"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="reveal-key-7",
    )

    event = AuditEvent.objects.get(action="storage.credential.revealed")
    assert missing.status_code == 400
    assert revealed.status_code == 200
    assert revealed["Cache-Control"] == "no-store"
    assert _payload(revealed)["access_key_id"] == "LTAI-admin-7"
    assert event.actor == admin
    assert event.reason == "incident investigation"
    assert "secret" not in str(event.safe_metadata).lower()


def test_admin_key_action_replays_same_payload_and_rejects_reuse(
    admin_client, cloud_identity_factory, monkeypatch
):
    client, _admin = admin_client
    identity = cloud_identity_factory()
    key = _key(identity)
    calls = []

    def operation(**kwargs):
        calls.append(kwargs)
        return key

    monkeypatch.setattr(
        "object_storage.views_admin.disable_access_key_action", operation
    )
    url = f"/api/v1/object-storage/management/access-keys/{key.id}/disable/"
    first = client.post(
        url,
        {"reason": "first reason"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="admin-action-replay",
    )
    replay = client.post(
        url,
        {"reason": "first reason"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="admin-action-replay",
    )
    reused = client.post(
        url,
        {"reason": "different reason"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="admin-action-replay",
    )

    assert first.status_code == 200
    assert replay.json() == first.json()
    assert reused.status_code == 409
    assert len(calls) == 1


@pytest.mark.parametrize("action", ["release", "recover", "delete", "retry-delete"])
def test_admin_bucket_lifecycle_actions_are_separate(
    admin_client, bucket_factory, monkeypatch, action
):
    client, admin = admin_client
    bucket = bucket_factory(state="active")
    calls = []

    def operation(**kwargs):
        calls.append(kwargs)
        return bucket

    function_name = action.replace("-", "_") + "_bucket"
    monkeypatch.setattr(f"object_storage.views_admin.{function_name}", operation)
    response = client.post(
        f"/api/v1/object-storage/management/buckets/{bucket.id}/{action}/",
        {"bucket_name": bucket.name, "confirmed": True, "reason": "admin cleanup"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY=f"bucket-{action}-1",
    )

    assert response.status_code in {200, 202}
    assert calls[0]["bucket"].id == bucket.id
    assert calls[0]["actor"] == admin


def test_bucket_configuration_update_and_retry_are_fixed_actions(
    admin_client, bucket_factory, monkeypatch
):
    client, _admin = admin_client
    bucket = bucket_factory(state="active")
    calls = []

    def update(**kwargs):
        calls.append(("update", kwargs))
        return bucket

    def retry(**kwargs):
        calls.append(("retry", kwargs))
        return bucket

    monkeypatch.setattr(
        "object_storage.views_admin.update_bucket_configuration", update
    )
    monkeypatch.setattr("object_storage.views_admin.retry_bucket_configuration", retry)
    body = {
        "desired": {
            "acl": "public_read",
            "storage_class": "Standard",
            "encryption": "AES256",
            "versioning": False,
            "lifecycle": {},
        },
        "bucket_name": bucket.name,
        "confirmed": True,
        "reason": "publish static assets",
    }
    updated = client.patch(
        f"/api/v1/object-storage/management/buckets/{bucket.id}/configuration/",
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="bucket-config-1",
    )
    retried = client.post(
        f"/api/v1/object-storage/management/buckets/{bucket.id}/configuration/retry/",
        {"bucket_name": bucket.name, "confirmed": True, "reason": "retry config"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="bucket-config-retry-1",
    )

    assert updated.status_code == 202
    assert retried.status_code == 202
    assert [kind for kind, _kwargs in calls] == ["update", "retry"]


def test_only_admin_can_observe_and_acknowledge_uncertain_bucket(
    admin_client, client, user_factory, bucket_factory, monkeypatch
):
    admin_api, _admin = admin_client
    bucket = bucket_factory(state="deletion_blocked")
    bucket.action_owner_token = "frozen-operation-token"
    bucket.action_type = "release"
    bucket.action_generation = 3
    bucket.deletion_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    bucket.save()
    monkeypatch.setattr(
        "object_storage.views_admin.reconcile_bucket_action_uncertainty",
        lambda **kwargs: bucket,
    )
    monkeypatch.setattr(
        "object_storage.views_admin.acknowledge_bucket_action_uncertainty",
        lambda **kwargs: bucket,
    )
    observe_url = (
        f"/api/v1/object-storage/management/buckets/{bucket.id}/uncertainty/observe/"
    )
    acknowledge_url = f"/api/v1/object-storage/management/buckets/{bucket.id}/uncertainty/acknowledge/"
    observed = admin_api.post(
        observe_url,
        {"reason": "inspect frozen operation"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="observe-uncertain-1",
    )
    acknowledged = admin_api.post(
        acknowledge_url,
        {
            "reason": "verified in cloud console",
            "bucket_name": bucket.name,
            "confirmed": True,
            "operation_type": "release",
            "operation_generation": 3,
            "operation_token": "frozen-operation-token",
            "resolved_state": "active",
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="ack-uncertain-1",
    )
    ordinary = user_factory()
    client.force_login(ordinary)
    denied = client.post(
        observe_url,
        {"reason": "not allowed"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="observe-uncertain-denied",
    )

    assert observed.status_code == 200
    assert acknowledged.status_code == 200
    assert denied.status_code == 403


def test_uncertainty_operations_do_not_persist_tokens_and_are_not_replayable(
    admin_client, bucket_factory, monkeypatch
):
    from object_storage.models import ApiIdempotencyRecord

    client, _admin = admin_client
    bucket = bucket_factory(state="deletion_blocked")
    bucket.action_owner_token = "frozen-operation-token"
    bucket.action_type = "release"
    bucket.action_generation = 3
    bucket.deletion_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    bucket.save()
    monkeypatch.setattr(
        "object_storage.views_admin.reconcile_bucket_action_uncertainty",
        lambda **kwargs: bucket,
    )
    url = f"/api/v1/object-storage/management/buckets/{bucket.id}/uncertainty/observe/"
    first = client.post(
        url,
        {"reason": "inspect frozen operation"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="uncertain-observe-sensitive",
    )
    replay = client.post(
        url,
        {"reason": "inspect frozen operation"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="uncertain-observe-sensitive",
    )

    record = ApiIdempotencyRecord.objects.get(
        actor=_admin, idempotency_key="uncertain-observe-sensitive"
    )
    assert first.status_code == 200
    assert first["Cache-Control"] == "no-store"
    assert replay.status_code == 409
    assert replay["Cache-Control"] == "no-store"
    assert replay.json()["data"]["error_code"] == "IDEMPOTENCY_RESULT_NOT_REPLAYABLE"
    assert record.response_body is None
    assert "frozen-operation-token" not in str(record.__dict__)
    assert "generation" not in str(record.__dict__)


def test_bucket_uncertainty_acknowledgements_call_real_services_without_500(
    admin_client, bucket_factory
):
    from object_storage.models import Bucket

    client, _admin = admin_client
    action_bucket = bucket_factory(state=Bucket.State.DELETION_BLOCKED)
    action_bucket.action_generation = 4
    action_bucket.action_owner_token = "frozen-delete-token"
    action_bucket.action_type = "delete"
    action_bucket.deletion_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    action_bucket.save()
    action_url = (
        f"/api/v1/object-storage/management/buckets/{action_bucket.id}"
        "/uncertainty/acknowledge/"
    )
    false_confirmation = client.post(
        action_url,
        {
            "reason": "not actually confirmed",
            "bucket_name": action_bucket.name,
            "confirmed": False,
            "operation_type": "delete",
            "operation_generation": 4,
            "operation_token": "frozen-delete-token",
            "resolved_state": Bucket.State.RELEASED,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="real-action-ack-false",
    )
    action_response = client.post(
        action_url,
        {
            "reason": "bucket absence confirmed in cloud console",
            "bucket_name": action_bucket.name,
            "confirmed": True,
            "operation_type": "delete",
            "operation_generation": 4,
            "operation_token": "frozen-delete-token",
            "resolved_state": Bucket.State.RELEASED,
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="real-action-ack",
    )

    config_bucket = bucket_factory(state=Bucket.State.ACTIVE)
    config_bucket.desired_config_snapshot = {"acl": "private"}
    config_bucket.config_state = Bucket.ConfigurationState.UNKNOWN
    config_bucket.config_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    config_bucket.configuration_generation = 7
    config_bucket.configuration_operation_token = "frozen-config-token"
    config_bucket.save()
    config_url = (
        f"/api/v1/object-storage/management/buckets/{config_bucket.id}"
        "/configuration/uncertainty/acknowledge/"
    )
    config_response = client.post(
        config_url,
        {
            "reason": "configuration verified in cloud console",
            "bucket_name": config_bucket.name,
            "confirmed": True,
            "operation_type": "configuration",
            "operation_generation": 7,
            "operation_token": "frozen-config-token",
            "resolution": "desired",
        },
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="real-config-ack",
    )

    action_bucket.refresh_from_db()
    config_bucket.refresh_from_db()
    assert false_confirmation.status_code == 400
    assert action_response.status_code == 200
    assert config_response.status_code == 200
    assert action_response["Cache-Control"] == "no-store"
    assert config_response["Cache-Control"] == "no-store"
    assert action_bucket.action_owner_token == ""
    assert config_bucket.configuration_operation_token == ""


def test_all_uncertainty_observe_responses_are_no_store(
    admin_client, bucket_factory, cloud_identity_factory, monkeypatch
):
    client, _admin = admin_client
    action_bucket = bucket_factory(state="deletion_blocked")
    action_bucket.action_owner_token = "action-observe-token"
    action_bucket.action_type = "delete"
    action_bucket.action_generation = 2
    action_bucket.save()
    config_bucket = bucket_factory(state="active")
    config_bucket.configuration_operation_token = "config-observe-token"
    config_bucket.configuration_generation = 3
    config_bucket.save()
    identity = cloud_identity_factory(state="error")
    identity.credential_operation_token = "credential-observe-token"
    identity.credential_operation_type = "rotate"
    identity.credential_operation_generation = 4
    identity.save()
    monkeypatch.setattr(
        "object_storage.views_admin.reconcile_bucket_action_uncertainty",
        lambda **kwargs: action_bucket,
    )
    monkeypatch.setattr(
        "object_storage.views_admin.reconcile_bucket_configuration_uncertainty",
        lambda **kwargs: config_bucket,
    )
    monkeypatch.setattr(
        "object_storage.views_admin.reconcile_credential_operation_uncertainty",
        lambda **kwargs: identity,
    )
    monkeypatch.setattr(
        "object_storage.views_admin.build_aliyun_provider", lambda _pool: object()
    )

    responses = [
        client.post(
            f"/api/v1/object-storage/management/buckets/{action_bucket.id}/uncertainty/observe/",
            {"reason": "inspect action"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="observe-action-header",
        ),
        client.post(
            f"/api/v1/object-storage/management/buckets/{config_bucket.id}/configuration/uncertainty/observe/",
            {"reason": "inspect configuration"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="observe-config-header",
        ),
        client.post(
            f"/api/v1/object-storage/management/cloud-identities/{identity.id}/uncertainty/observe/",
            {"reason": "inspect credential"},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="observe-credential-header",
        ),
    ]

    assert all(response.status_code == 200 for response in responses)
    assert all(response["Cache-Control"] == "no-store" for response in responses)


def test_admin_operation_token_details_are_no_store(
    admin_client, bucket_factory, cloud_identity_factory
):
    client, _admin = admin_client
    bucket = bucket_factory(state="deletion_blocked")
    bucket.action_owner_token = "bucket-detail-token"
    bucket.action_type = "delete"
    bucket.action_generation = 2
    bucket.save()
    identity = cloud_identity_factory(state="error")
    identity.credential_operation_token = "identity-detail-token"
    identity.credential_operation_type = "rotate"
    identity.credential_operation_generation = 3
    identity.save()

    bucket_response = client.get(
        f"/api/v1/object-storage/management/buckets/{bucket.id}/"
    )
    identity_response = client.get(
        f"/api/v1/object-storage/management/cloud-identities/{identity.id}/"
    )

    assert bucket_response.status_code == 200
    assert identity_response.status_code == 200
    assert bucket_response["Cache-Control"] == "no-store"
    assert identity_response["Cache-Control"] == "no-store"
    assert "bucket-detail-token" in bucket_response.content.decode()
    assert "identity-detail-token" in identity_response.content.decode()


def test_uncertainty_acknowledgement_requires_strict_boolean_and_all_fields(
    admin_client, cloud_identity_factory
):
    client, _admin = admin_client
    identity = cloud_identity_factory(state="error")
    identity.credential_operation_token = "credential-frozen-token"
    identity.credential_operation_type = "rotate"
    identity.credential_operation_generation = 4
    identity.credential_operation_error_code = "CLOUD_MUTATION_OUTCOME_UNKNOWN"
    identity.save()
    url = (
        f"/api/v1/object-storage/management/cloud-identities/{identity.id}"
        "/uncertainty/acknowledge/"
    )
    body = {
        "reason": "verified in cloud console",
        "identity_name": identity.ram_user_name,
        "operation_type": "rotate",
        "operation_generation": 4,
        "operation_token": "credential-frozen-token",
        "cloud_console_resolved": "false",
        "observation_summary": "cloud console checked",
        "resolved_state": "error",
    }
    string_false = client.post(
        url,
        body,
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="credential-ack-string-false",
    )
    missing = client.post(
        url,
        {"reason": "missing fields"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="credential-ack-missing",
    )

    assert string_false.status_code == 400
    assert missing.status_code == 400
    assert string_false.json()["data"]["error_code"] == "VALIDATION_ERROR"
    assert missing.json()["data"]["error_code"] == "VALIDATION_ERROR"


def test_audit_query_rejects_invalid_filters_instead_of_silently_ignoring(admin_client):
    client, _admin = admin_client
    invalid_actor = client.get(
        "/api/v1/object-storage/management/audit-events/?actor_id=not-an-int"
    )
    invalid_since = client.get(
        "/api/v1/object-storage/management/audit-events/?since=not-a-date"
    )
    invalid_result = client.get(
        "/api/v1/object-storage/management/audit-events/?result=not-valid"
    )

    assert invalid_actor.status_code == 400
    assert invalid_since.status_code == 400
    assert invalid_result.status_code == 400
    assert all(
        response.json()["data"]["error_code"] == "VALIDATION_ERROR"
        for response in (invalid_actor, invalid_since, invalid_result)
    )


def test_admin_suspend_and_reactivate_user_resources(
    admin_client, cloud_identity_factory, monkeypatch
):
    client, admin = admin_client
    identity = cloud_identity_factory(state="active")
    calls = []

    def suspend(**kwargs):
        calls.append(("suspend", kwargs))
        return identity

    def reactivate(**kwargs):
        calls.append(("reactivate", kwargs))
        return identity

    monkeypatch.setattr("object_storage.views_admin.suspend_user_resources", suspend)
    monkeypatch.setattr(
        "object_storage.views_admin.reactivate_user_resources", reactivate
    )
    suspended = client.post(
        f"/api/v1/object-storage/management/users/{identity.user_id}/suspend/",
        {"reason": "employee departure"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="suspend-user-1",
    )
    reactivated = client.post(
        f"/api/v1/object-storage/management/users/{identity.user_id}/reactivate/",
        {"reason": "employee returned"},
        content_type="application/json",
        HTTP_IDEMPOTENCY_KEY="reactivate-user-1",
    )

    assert suspended.status_code == 202
    assert reactivated.status_code == 200
    assert all(call[1]["actor"] == admin for call in calls)
