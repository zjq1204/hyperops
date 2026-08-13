import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from monitoring_stack.models import MonitoringSshCredential
from monitoring_stack.services.credential_crypto import decrypt_secret
from monitoring_stack.services.credential_ingestion import (
    PrivateKeyValidationError,
    create_credential_version,
    inspect_private_key,
)


class Command(BaseCommand):
    help = "Encrypt and verify staged file-backed monitoring SSH credentials."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--credential-id", type=int)
        parser.add_argument("--remove-verified-plaintext", action="store_true")

    def handle(self, *args, **options):
        queryset = MonitoringSshCredential.objects.select_related("active_version").order_by("id")
        if options["credential_id"]:
            queryset = queryset.filter(pk=options["credential_id"])
        for credential in queryset.iterator():
            report = self._process(credential, **options)
            self.stdout.write(json.dumps(report, sort_keys=True, separators=(",", ":")))

    def _process(self, credential, **options):
        base = {"credential_id": credential.id, "name": credential.name}
        path = credential.storage_path
        if credential.active_version_id:
            try:
                parsed = inspect_private_key(
                    decrypt_secret(credential.active_version.private_key_encrypted),
                    decrypt_secret(credential.active_version.passphrase_encrypted)
                    if credential.active_version.has_passphrase else "",
                )
                if parsed.public_key_fingerprint != credential.active_version.public_key_fingerprint:
                    raise PrivateKeyValidationError("FINGERPRINT_MISMATCH")
            except Exception:
                return {**base, "result": "verification_failed", "plaintext_action": "retained"}
            plaintext_action = "retained"
            if options["remove_verified_plaintext"] and path and path.exists() and not options["dry_run"]:
                with transaction.atomic():
                    path.unlink()
                    credential.legacy_file_name = None
                    credential.save(update_fields=["legacy_file_name", "updated_at"])
                plaintext_action = "removed"
            return {**base, "result": "already_migrated", "fingerprint": parsed.public_key_fingerprint, "plaintext_action": plaintext_action}
        if not path or not path.is_file():
            if not options["dry_run"]:
                credential.status = credential.STATUS_NEEDS_REUPLOAD
                credential.save(update_fields=["status", "updated_at"])
            return {**base, "result": "needs_reupload", "error_code": "LEGACY_FILE_MISSING", "plaintext_action": "retained"}
        try:
            raw = path.read_bytes()
            parsed = inspect_private_key(raw)
        except (OSError, PrivateKeyValidationError) as exc:
            if not options["dry_run"]:
                credential.status = credential.STATUS_NEEDS_REUPLOAD
                credential.save(update_fields=["status", "updated_at"])
            return {**base, "result": "needs_reupload", "error_code": getattr(exc, "code", "LEGACY_FILE_UNREADABLE"), "plaintext_action": "retained"}
        if options["dry_run"]:
            return {**base, "result": "migratable", "fingerprint": parsed.public_key_fingerprint, "plaintext_action": "retained"}
        with transaction.atomic():
            locked = MonitoringSshCredential.objects.select_for_update().get(pk=credential.pk)
            if locked.active_version_id:
                return {**base, "result": "already_migrated", "fingerprint": locked.active_version.public_key_fingerprint, "plaintext_action": "retained"}
            version = create_credential_version(
                credential=locked, private_key=parsed.normalized_private_key,
                passphrase=parsed.passphrase, allow_duplicate=True,
            )
            verified = inspect_private_key(
                decrypt_secret(version.private_key_encrypted),
                decrypt_secret(version.passphrase_encrypted) if version.has_passphrase else "",
            )
            if verified.public_key_fingerprint != version.public_key_fingerprint:
                raise PrivateKeyValidationError("FINGERPRINT_MISMATCH")
            version.validation_status = version.VALIDATION_VALID
            version.activated_at = timezone.now()
            version.save(update_fields=["validation_status", "activated_at"])
            locked.active_version = version
            locked.status = locked.STATUS_ACTIVE
            locked.save(update_fields=["active_version", "status", "updated_at"])
        plaintext_action = "retained"
        if options["remove_verified_plaintext"]:
            with transaction.atomic():
                path.unlink()
                locked.legacy_file_name = None
                locked.save(update_fields=["legacy_file_name", "updated_at"])
            plaintext_action = "removed"
        return {**base, "result": "migrated", "fingerprint": version.public_key_fingerprint, "plaintext_action": plaintext_action}
