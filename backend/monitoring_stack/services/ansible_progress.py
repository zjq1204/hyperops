import re
import queue
import subprocess
import threading
import time
from dataclasses import dataclass

from django.utils import timezone

from monitoring_stack.models import AnsibleInstallJob

STAGES = {
    "queued": (1, 0),
    "preparing": (2, 20),
    "connecting": (3, 40),
    "installing": (4, 60),
    "verifying": (5, 85),
    "completed": (6, 100),
    "failed": (6, 100),
}


@dataclass
class StreamResult:
    returncode: int
    timed_out: bool
    lines: list[str]


_STREAM_EOF = object()


def build_progress(stage, *, current_host="", reason_code="", message=""):
    current, percent = STAGES[stage]
    return {
        "stage": stage,
        "current": current,
        "total": 6,
        "percent": percent,
        "reason_code": reason_code or message or stage,
        "current_host": current_host,
        "updated_at": timezone.now().isoformat(),
    }


def normalize_progress(progress, status="queued"):
    if isinstance(progress, dict) and progress.get("stage") in STAGES:
        return progress
    terminal = "completed" if status == AnsibleInstallJob.STATUS_SUCCESS else status
    return build_progress(terminal if terminal in STAGES else "queued")


def progress_stage_for_line(line):
    stripped = str(line or "").strip()
    if stripped.startswith("TASK ["):
        return "installing"
    if stripped.startswith("PLAY RECAP"):
        return "verifying"
    return None


def current_host_for_line(line):
    match = re.match(
        r"^(?:ok|changed|fatal|skipping|unreachable):\s*\[([^]]+)]",
        str(line or "").strip(),
        re.IGNORECASE,
    )
    return match.group(1) if match else ""


def failure_reason_code(logs, *, timed_out=False):
    if timed_out:
        return "timeout"
    output = "\n".join(str(line or "") for line in logs).lower()
    if "error in libcrypto" in output or "invalid format" in output:
        return "ssh_key_invalid"
    if "permission denied" in output or "authentication failed" in output:
        return "ssh_auth_failed"
    if "unreachable!" in output or "ssh_unreachable" in output:
        return "ssh_unreachable"
    return "ansible_failed"


def _read_process_lines(stream, output_queue):
    try:
        while True:
            line = stream.readline()
            if line == "":
                break
            output_queue.put(line)
    finally:
        output_queue.put(_STREAM_EOF)


def stream_process_output(process, *, timeout_seconds, on_flush):
    output_queue = queue.Queue()
    reader = threading.Thread(
        target=_read_process_lines,
        args=(process.stdout, output_queue),
        daemon=True,
    )
    reader.start()
    deadline = time.monotonic() + timeout_seconds
    all_lines = []
    buffered = []
    buffered_stage = None
    last_flush = time.monotonic()
    timed_out = False

    def flush():
        nonlocal buffered, buffered_stage, last_flush
        if buffered:
            on_flush(buffered, buffered_stage)
            buffered = []
            buffered_stage = None
            last_flush = time.monotonic()

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        try:
            item = output_queue.get(timeout=min(0.25, remaining))
        except queue.Empty:
            continue
        if item is _STREAM_EOF:
            break
        line = item.strip()
        if not line:
            continue
        stage = progress_stage_for_line(line)
        if stage:
            flush()
            buffered_stage = stage
        buffered.append(line)
        all_lines.append(line)
        if stage or len(buffered) >= 10 or time.monotonic() - last_flush >= 1:
            flush()

    flush()
    if timed_out:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return StreamResult(returncode=124, timed_out=True, lines=all_lines)
    return StreamResult(
        returncode=process.wait(),
        timed_out=False,
        lines=all_lines,
    )
