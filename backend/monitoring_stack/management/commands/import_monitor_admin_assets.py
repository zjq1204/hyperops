import os
import shutil
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from monitoring_stack.services.core import (
    installer_dir,
    monitoring_root,
    rules_dir,
    ssh_dir,
    template_dir,
)


class Command(BaseCommand):
    help = "Copy legacy monitor-admin file assets into monitoring_stack storage."

    ASSET_DIRS = {
        "installer": installer_dir,
        "templates": template_dir,
        "rules": rules_dir,
        "ssh": ssh_dir,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "monitor_admin_root",
            help="Path to the legacy monitor-admin root",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            help="Do not overwrite files that already exist in monitoring_stack storage.",
        )

    def handle(self, *args, **options):
        legacy_root = Path(options["monitor_admin_root"]).resolve()
        if not legacy_root.exists():
            raise CommandError(f"monitor-admin root not found: {legacy_root}")

        copied = {}
        for name, destination_factory in self.ASSET_DIRS.items():
            source = legacy_root / name
            destination = destination_factory()
            copied[name] = self._copy_tree(
                source,
                destination,
                options["skip_existing"],
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Copied monitor-admin assets to {monitoring_root()}: {copied}"
            )
        )

    def _copy_tree(self, source: Path, destination: Path, skip_existing: bool) -> int:
        if not source.exists():
            return 0
        if not source.is_dir():
            raise CommandError(f"asset path is not a directory: {source}")

        count = 0
        for item in source.rglob("*"):
            relative_path = item.relative_to(source)
            target = destination / relative_path
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if skip_existing and target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            if destination == ssh_dir():
                os.chmod(target, 0o600)
            count += 1
        return count
