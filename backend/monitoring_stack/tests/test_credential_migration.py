import json

import pytest
from django.core.management import call_command

from monitoring_stack.models import MonitoringSshCredential
from monitoring_stack.tests.ssh_key_fixtures import generate_private_key


@pytest.mark.django_db
def test_legacy_migration_dry_run_is_json_and_does_not_write(tmp_path, settings, capsys):
    settings.MONITORING_SSH_DIR = str(tmp_path)
    credential = MonitoringSshCredential.objects.create(name="legacy", legacy_file_name="legacy.pem")
    (tmp_path / "legacy.pem").write_text(generate_private_key(tmp_path).replace("\n", "\r\n"), encoding="utf-8")
    call_command("migrate_monitoring_ssh_credentials", dry_run=True)
    credential.refresh_from_db()
    assert credential.active_version_id is None
    assert json.loads(capsys.readouterr().out)["result"] == "migratable"
