from __future__ import annotations

import os
from pathlib import Path


_ENV_LOADED = False


def load_environment(env_path: Path | str = ".env") -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return

    path = Path(env_path)
    if not path.exists():
        _ENV_LOADED = True
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

    _ENV_LOADED = True


def get_bool_env(name: str, default: bool = False) -> bool:
    load_environment()
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int) -> int:
    load_environment()
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default
