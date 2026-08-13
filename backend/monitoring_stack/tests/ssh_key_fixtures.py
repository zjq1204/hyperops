import shutil
import subprocess

import pytest


def generate_private_key(tmp_path, *, algorithm="ed25519", passphrase=""):
    if not shutil.which("ssh-keygen"):
        pytest.skip("ssh-keygen is unavailable")
    path = tmp_path / f"{algorithm}.key"
    command = ["ssh-keygen", "-q", "-t", algorithm, "-N", passphrase, "-f", str(path)]
    if algorithm == "rsa":
        command[4:4] = ["-b", "2048"]
    subprocess.run(command, check=True)
    return path.read_text(encoding="utf-8")
