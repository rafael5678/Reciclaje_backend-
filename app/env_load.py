"""Load GEMINI_API_KEY from .env without extra dependencies."""

from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[2]


class EnvLoader:
    def __init__(self, paths: tuple[Path, ...] | None = None) -> None:
        self.paths = paths or (ROOT / ".env", APP_DIR / ".env")

    def load(self) -> None:
        for path in self.paths:
            if not path.exists():
                continue
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip().strip('"').strip("'")


def load_env() -> None:
    EnvLoader().load()
