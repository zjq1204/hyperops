from django.conf import settings
from django.core.checks import Error, Warning, register
from django.db import OperationalError, ProgrammingError

from monitoring_stack.models import MonitoringSshCredential, MonitoringSshCredentialVersion
from monitoring_stack.services.credential_crypto import decrypt_secret


@register(deploy=True)
def check_monitoring_credential_encryption(app_configs, **kwargs):
    configured = bool(str(getattr(settings, "MONITORING_CREDENTIAL_ENCRYPTION_KEYS", "") or "").strip())
    try:
        versions = list(
            MonitoringSshCredentialVersion.objects.select_related("credential").only(
                "id",
                "credential_id",
                "credential__credential_type",
                "private_key_encrypted",
                "secret_encrypted",
                "passphrase_encrypted",
                "has_passphrase",
            )
        )
    except (OperationalError, ProgrammingError):
        return []
    try:
        credential_exists = MonitoringSshCredential.objects.exists()
    except (OperationalError, ProgrammingError):
        return []
    if not credential_exists and not configured:
        return [Warning("Monitoring credential encryption key ring is not configured.", id="monitoring_stack.W001")]
    affected = []
    for version in versions:
        try:
            if version.credential.credential_type == MonitoringSshCredential.TYPE_PASSWORD:
                decrypt_secret(version.secret_encrypted)
            else:
                decrypt_secret(version.private_key_encrypted)
                if version.has_passphrase:
                    decrypt_secret(version.passphrase_encrypted)
        except Exception:
            affected.append(version.credential_id)
    if affected:
        ids = ",".join(str(value) for value in sorted(set(affected)))
        return [Error("Retained monitoring credentials cannot be decrypted.", hint=f"Affected credential IDs: {ids}", id="monitoring_stack.E001")]
    return []
