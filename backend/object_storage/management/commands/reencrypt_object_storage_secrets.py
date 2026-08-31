import getpass
import json

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from object_storage.crypto import (
    SecretCryptoError,
    _decrypt_secret_with_root,
    _encrypt_secret_with_root,
    _validate_root_secret,
)

SECRET_FIELD_TARGETS = (
    ("FeishuAppConfig", ("app_secret_encrypted",)),
    (
        "StorageResourcePool",
        (
            "management_access_key_encrypted",
            "management_secret_key_encrypted",
        ),
    ),
    (
        "StorageAccessKey",
        ("access_key_id_encrypted", "secret_access_key_encrypted"),
    ),
)


class Command(BaseCommand):
    help = "Re-encrypt all object-storage secrets under a new Django root secret."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--batch-size", type=int, default=100)

    def get_secret_field_targets(self):
        targets = []
        for model_name, field_names in SECRET_FIELD_TARGETS:
            try:
                model = apps.get_model("object_storage", model_name)
            except LookupError as exc:
                raise CommandError(
                    f"Object storage model is unavailable: {model_name}"
                ) from exc
            targets.append((f"object_storage.{model_name}", model, field_names))
        return tuple(targets)

    def handle(self, *args, **options):
        if not options.get("confirm"):
            raise CommandError("Pass --confirm to re-encrypt object-storage secrets")

        batch_size = max(1, options.get("batch_size", 100))
        old_root = getpass.getpass("Current Django root secret: ")
        new_root = getpass.getpass("New Django root secret: ")
        try:
            _validate_root_secret(old_root)
            _validate_root_secret(new_root)
        except SecretCryptoError as exc:
            raise CommandError("A valid old and new root secret is required") from exc
        if old_root == new_root:
            raise CommandError("Old and new root secrets must differ")

        updated_rows = 0
        updated_fields = 0
        target_counts = {}
        try:
            with transaction.atomic():
                staged_updates = []
                for label, model, field_names in self.get_secret_field_targets():
                    target_count = 0
                    records = (
                        model.objects.select_for_update()
                        .only("pk", *field_names)
                        .order_by("pk")
                        .iterator(chunk_size=batch_size)
                    )
                    for record in records:
                        changes = {}
                        for field_name in field_names:
                            envelope = getattr(record, field_name)
                            if envelope in (None, ""):
                                continue
                            plaintext = _decrypt_secret_with_root(envelope, old_root)
                            replacement = _encrypt_secret_with_root(plaintext, new_root)
                            if (
                                _decrypt_secret_with_root(replacement, new_root)
                                != plaintext
                            ):
                                raise SecretCryptoError("Secret verification failed")
                            changes[field_name] = replacement
                        if changes:
                            staged_updates.append((record, changes))
                            target_count += len(changes)
                    target_counts[label] = target_count

                for record, changes in staged_updates:
                    for field_name, replacement in changes.items():
                        setattr(record, field_name, replacement)
                    record.save(update_fields=tuple(changes))
                    updated_rows += 1
                    updated_fields += len(changes)
        except Exception as exc:
            raise CommandError(
                "Object storage secret re-encryption aborted; no rows were changed"
            ) from exc

        self.stdout.write(
            json.dumps(
                {
                    "targets": target_counts,
                    "updated_fields": updated_fields,
                    "updated_rows": updated_rows,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
