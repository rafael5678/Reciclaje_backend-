"""Claude Haiku 5.5 as a paid backup when Gemini is exhausted.

Uses the same EcoScan prompt and JSON shape. Does not poll Anthropic;
status only checks that ANTHROPIC_API_KEY is present.
"""

from __future__ import annotations

import json
import os
import threading
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

HAIKU = "claude-haiku-5-5"
MAX_OUTPUT_TOKENS = 320
TIMEOUT_S = 22


class _HaikuState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cool_until = 0.0
        self._last: dict = {}

    def available(self) -> bool:
        with self._lock:
            return self._cool_until <= time.time()

    def cool(self, seconds: float) -> None:
        with self._lock:
            self._cool_until = time.time() + seconds

    def cooling_until(self) -> float | None:
        with self._lock:
            until = self._cool_until
        return until if until > time.time() else None

    def remember(self, ok: bool, detail: str = "") -> None:
        with self._lock:
            self._last = {"model": HAIKU, "ok": ok, "detail": detail[:160], "at": int(time.time())}

    def last(self) -> dict:
        with self._lock:
            return dict(self._last)


state = _HaikuState()


def has_anthropic() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def model_name() -> str:
    return os.environ.get("ANTHROPIC_MODEL", HAIKU).strip() or HAIKU


def status() -> dict:
    until = state.cooling_until()
    return {
        "enabled": has_anthropic(),
        "model": model_name() if has_anthropic() else None,
        "available": has_anthropic() and until is None,
        "retry_at": int(until) if until else None,
        "last": state.last() or None,
    }


def classify(prompt: str, jpeg_b64: str, parse) -> dict | None:
    """Ask Haiku once. `parse` turns JSON text into an EcoScan hit."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or not state.available():
        return None
    model = model_name()
    started = time.perf_counter()
    try:
        raw = _ask(key, model, prompt, jpeg_b64)
        hit = parse(_text(raw))
        if not hit:
            state.remember(False, "sin codigo valido")
            print("[EcoScan Anthropic] respuesta sin codigo valido")
            return None
        state.remember(True)
        hit["inference_ms"] = round((time.perf_counter() - started) * 1000, 1)
        hit["engine"] = "anthropic"
        hit["model"] = model
        return hit
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="ignore")[:400]
        state.remember(False, f"{error.code}")
        print(f"[EcoScan Anthropic] HTTP {error.code}: {body[:200]}")
        if error.code == 429:
            state.cool(180)
        elif error.code in {401, 403}:
            state.cool(3600)
        else:
            state.cool(60)
        return None
    except Exception as error:
        state.remember(False, type(error).__name__)
        print(f"[EcoScan Anthropic] {type(error).__name__}: {error}")
        state.cool(60)
        return None


def _ask(key: str, model: str, prompt: str, jpeg_b64: str) -> dict:
    body = json.dumps(
        {
            "model": model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0.2,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": "image/jpeg", "data": jpeg_b64},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
    ).encode("utf-8")
    request = Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urlopen(request, timeout=TIMEOUT_S) as response:
        return json.loads(response.read().decode("utf-8"))


def _text(raw: dict) -> str:
    parts = raw.get("content") or []
    chunks = [str(part.get("text") or "") for part in parts if isinstance(part, dict) and part.get("type") == "text"]
    return "".join(chunks)
