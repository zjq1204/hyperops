import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from monitoring_stack.models import MonitoringHost, MonitoringProfile, ProbeTarget
from monitoring_stack.services.core import (
    clean_labels,
    clean_ssh_key,
    clean_string_list,
)


class Command(BaseCommand):
    help = "Import legacy monitor-admin JSON state into monitoring_stack models."

    def add_arguments(self, parser):
        parser.add_argument("data_dir", help="Path to monitor-admin/data")

    def handle(self, *args, **options):
        data_dir = Path(options["data_dir"])
        if not data_dir.exists():
            raise CommandError(f"data directory not found: {data_dir}")

        imported = {
            "probe_targets": self._import_targets(data_dir / "probe-targets.json"),
            "hosts": self._import_hosts(data_dir / "hosts.json"),
            "profiles": self._import_profiles(data_dir / "profiles.json"),
        }
        self.stdout.write(
            self.style.SUCCESS(f"Imported monitor-admin state: {imported}")
        )

    def _read_json(self, path):
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []

    def _import_targets(self, path):
        count = 0
        for item in self._read_json(path):
            external_id = str(item.get("id") or "").strip() or None
            ProbeTarget.objects.update_or_create(
                external_id=external_id,
                defaults={
                    "type": item.get("type"),
                    "target": str(item.get("target") or "").strip(),
                    "enabled": bool(item.get("enabled", True)),
                    "labels": clean_labels(item.get("labels") or {}),
                },
            )
            count += 1
        return count

    def _import_hosts(self, path):
        count = 0
        for item in self._read_json(path):
            external_id = str(item.get("id") or "").strip() or None
            MonitoringHost.objects.update_or_create(
                external_id=external_id,
                defaults={
                    "hostname": str(item.get("hostname") or "").strip(),
                    "address": str(item.get("address") or "").strip(),
                    "ssh_user": str(item.get("ssh_user") or "root").strip(),
                    "ssh_port": int(item.get("ssh_port") or 22),
                    "ssh_key": clean_ssh_key(item.get("ssh_key")),
                    "profiles": clean_string_list(item.get("profiles") or []),
                    "labels": clean_labels(item.get("labels") or {}),
                    "params": clean_labels(item.get("params") or {}),
                    "enabled": bool(item.get("enabled", True)),
                },
            )
            count += 1
        return count

    def _import_profiles(self, path):
        count = 0
        for item in self._read_json(path):
            profile_id = str(item.get("id") or "").strip()
            if not profile_id:
                continue
            MonitoringProfile.objects.update_or_create(
                id=profile_id,
                defaults={
                    "name": str(item.get("name") or profile_id).strip(),
                    "category": str(item.get("category") or "").strip(),
                    "description": str(item.get("description") or "").strip(),
                    "plugins": clean_string_list(item.get("plugins") or []),
                    "is_builtin": True,
                },
            )
            count += 1
        return count
