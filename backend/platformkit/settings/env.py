"""Environment parsing helpers shared across backend products."""

import os


def env_flag(name: str, default: bool = False) -> bool:
    """Parse a boolean environment variable with a safe default."""
    return os.getenv(name, str(default).lower()).lower() == "true"
