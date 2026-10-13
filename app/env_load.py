"""Carga GEMINI_API_KEY desde .env sin dependencias extra."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    for path in (ROOT / ".env", APP_DIR / ".env"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")
