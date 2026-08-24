import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from monitoring_stack.models import MonitoringSshCredential, MonitoringSshCredentialVersion
from monitoring_stack.services.credential_crypto import (
    decrypt_secret,
    encrypt_secret,
    envelope_key_id,
    configured_key_ring,
)
from monitoring_stack.services.credential_ingestion import inspect_private_key


class Command(BaseCommand):
    help = "Re-encrypt retained monitoring credential versions with the primary key."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=100)
        parser.add_argument("--resume-after-id", type=int, default=0)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        batch_size = max(1, options["batch_size"])
        primary_id = configured_key_ring()[0][0]
        versions = MonitoringSshCredentialVersion.objects.select_related("credential").filter(
            id__gt=options["resume_after_id"]
        ).order_by("id")[:batch_size]
        summary = {"processed": 0, "reencrypted": 0, "already_primary": 0, "failed": 0, "last_id": options["resume_after_id"], "remaining_old_key_envelopes": 0}
        for version in versions:
            summary["processed"] += 1
            summary["last_id"] = version.id
            try:
                if version.credential.credential_type == MonitoringSshCredential.TYPE_PASSWORD:
                    secret = decrypt_secret(version.secret_encrypted)
                    is_primary = envelope_key_id(version.secret_encrypted) == primary_id
                    if is_primary:
                        summary["already_primary"] += 1
                        continue
                    if not options["dry_run"]:
                        secret_envelope = encrypt_secret(secret)
                        if decrypt_secret(secret_envelope) != secret:
                            raise ValueError("post-encryption password mismatch")
                        MonitoringSshCredentialVersion.objects.filter(pk=version.pk).update(
                            secret_encrypted=secret_envelope
                        )
                    summary["reencrypted"] += 1
                    continue
                private_key = decrypt_secret(version.private_key_encrypted)
                passphrase = decrypt_secret(version.passphrase_encrypted) if version.has_passphrase else ""
                parsed = inspect_private_key(private_key, passphrase)
                if parsed.public_key_fingerprint != version.public_key_fingerprint:
                    raise ValueError("fingerprint mismatch")
                is_primary = envelope_key_id(version.private_key_encrypted) == primary_id and (
                    not version.has_passphrase or envelope_key_id(version.passphrase_encrypted) == primary_id
                )
                if is_primary:
                    summary["already_primary"] += 1
                    continue
                if not options["dry_run"]:
                    private_envelope = encrypt_secret(private_key)
                    passphrase_envelope = (
                        encrypt_secret(passphrase) if version.has_passphrase else ""
                    )
                    verified = inspect_private_key(
                        decrypt_secret(private_envelope),
                        decrypt_secret(passphrase_envelope)
                        if version.has_passphrase else "",
                    )
                    if verified.public_key_fingerprint != version.public_key_fingerprint:
                        raise ValueError("post-encryption fingerprint mismatch")
                    with transaction.atomic():
                        MonitoringSshCredentialVersion.objects.filter(pk=version.pk).update(
                            private_key_encrypted=private_envelope,
                            passphrase_encrypted=passphrase_envelope,
                        )
                summary["reencrypted"] += 1
            except Exception:
                summary["failed"] += 1
        for credential_type, private_envelope, secret_envelope, passphrase_envelope, has_passphrase in MonitoringSshCredentialVersion.objects.values_list("credential__credential_type", "private_key_encrypted", "secret_encrypted", "passphrase_encrypted", "has_passphrase"):
            try:
                if credential_type == MonitoringSshCredential.TYPE_PASSWORD:
                    old_envelope = envelope_key_id(secret_envelope) != primary_id
                else:
                    old_envelope = envelope_key_id(private_envelope) != primary_id or (has_passphrase and envelope_key_id(passphrase_envelope) != primary_id)
                if old_envelope:
                    summary["remaining_old_key_envelopes"] += 1
            except Exception:
                summary["remaining_old_key_envelopes"] += 1
        self.stdout.write(json.dumps(summary, sort_keys=True, separators=(",", ":")))
        if summary["failed"]:
            raise CommandError("credential re-encryption failed")
