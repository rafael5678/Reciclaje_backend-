"""Gemini ve la foto y la clasifica con el catálogo de EcoScan.

Cada escaneo hace una sola petición. Si el modelo principal se agota (429),
se usa el de respaldo, y nunca se pasa de GEMINI_RPM peticiones por minuto.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
import time
from collections import OrderedDict, deque
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from app.models.catalog import BY_CODE
from app.services.guide import attach_guide

DEFAULT_MODELS = "gemini-3.1-flash-lite,gemini-3-flash-preview"
CODES = ["PET", "HDPE", "MLT", "PAP", "VID", "MET", "ORG", "GEN"]
# Con resolución baja la foto cuesta unos 280 tokens en lugar de ~1100.
IMAGE_SIDE = 384
MAX_OUTPUT_TOKENS = 320
CACHE_SIZE = 64
PROMPT = """Clasificador de EcoScan. Di QUÉ objeto hay en la foto (ignora mesa, mano y fondo).

Código:
PET botella plástica transparente de bebida (amarillo)
HDPE envase opaco de champú, detergente o yogur (amarillo)
MLT caja Tetra Pak de leche o jugo (amarillo)
PAP hoja de papel o caja de cartón (azul)
VID frasco o botella de vidrio (verde)
MET lata de metal (gris)
ORG restos de comida, cáscaras, fruta (marrón)
GEN no reciclable: lapicero, lápiz, celular, control, papel higiénico, servilleta sucia, bolsa de snack (negro)

Un lapicero o lápiz es GEN aunque sea plástico transparente.

Responde SOLO este JSON, en español, hablando de ESE objeto:
{"code":"GEN","object_name":"Control remoto","confidence":0.95,"meaning":"2 frases","destination":"contenedor y color","actions":["paso","paso","paso"],"tip":"advertencia corta"}"""


def _models() -> list[str]:
    raw = os.environ.get("GEMINI_MODELS", DEFAULT_MODELS)
    return [name.strip() for name in raw.split(",") if name.strip()]


def _per_minute() -> int:
    try:
        return max(1, int(os.environ.get("GEMINI_RPM", "6")))
    except ValueError:
        return 6


class _Budget:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._calls: deque[float] = deque()
        self._cool: dict[str, float] = {}
        self._last: dict = {}

    def _trim(self, now: float) -> None:
        while self._calls and now - self._calls[0] >= 60:
            self._calls.popleft()

    def take(self) -> bool:
        now = time.time()
        with self._lock:
            self._trim(now)
            if len(self._calls) >= _per_minute():
                return False
            self._calls.append(now)
            return True

    def used(self) -> int:
        with self._lock:
            self._trim(time.time())
            return len(self._calls)

    def cool(self, model: str, seconds: float) -> None:
        with self._lock:
            self._cool[model] = time.time() + seconds

    def available(self, model: str) -> bool:
        with self._lock:
            return self._cool.get(model, 0) <= time.time()

    def cooling_until(self, model: str) -> float | None:
        with self._lock:
            until = self._cool.get(model, 0)
        return until if until > time.time() else None

    def remember(self, model: str, ok: bool, detail: str = "") -> None:
        with self._lock:
            self._last = {"model": model, "ok": ok, "detail": detail[:160], "at": int(time.time())}

    def last(self) -> dict:
        with self._lock:
            return dict(self._last)


budget = _Budget()
_cache: OrderedDict[str, dict] = OrderedDict()
_cache_lock = threading.Lock()


def has_gemini() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def status() -> dict:
    models = []
    for name in _models():
        until = budget.cooling_until(name)
        models.append({"name": name, "available": until is None, "retry_at": int(until) if until else None})
    return {
        "enabled": has_gemini(),
        "models": models,
        "per_minute": _per_minute(),
        "used_last_minute": budget.used(),
        "last": budget.last() or None,
    }


def classify(image: Image.Image) -> dict | None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    payload, digest = _image_part(image)
    cached = _cached(digest)
    if cached:
        return cached
    started = time.perf_counter()
    for model in _models():
        if not budget.available(model):
            continue
        if not budget.take():
            print("Gemini: límite por minuto alcanzado, uso los modelos locales")
            return None
        try:
            hit = _parse(_ask(key, model, payload))
        except HTTPError as error:
            body = error.read().decode("utf-8", errors="ignore")[:600]
            budget.remember(model, False, f"{error.code}")
            print(f"Gemini {model}: {error.code} {body[:200]}")
            if error.code == 429:
                budget.cool(model, _cooldown(body))
                continue
            if error.code in (404, 503):
                budget.cool(model, 60)
                continue
            return None
        except (URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, ValueError, OSError) as error:
            budget.remember(model, False, type(error).__name__)
            print(f"Gemini {model}: {error}")
            return None
        if not hit:
            budget.remember(model, False, "respuesta sin código")
            return None
        budget.remember(model, True)
        hit["inference_ms"] = round((time.perf_counter() - started) * 1000, 1)
        hit["engine"] = "gemini"
        hit["model"] = model
        _store(digest, hit)
        return hit
    return None


def _cooldown(body: str) -> float:
    if re.search(r"per ?day|PerDay", body, re.IGNORECASE):
        return 60 * 60
    match = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"', body)
    if match:
        return max(5.0, float(match.group(1)))
    return 60.0


def _image_part(image: Image.Image) -> tuple[dict, str]:
    rgb = image.convert("RGB")
    rgb.thumbnail((IMAGE_SIDE, IMAGE_SIDE), Image.Resampling.BILINEAR)
    buffer = BytesIO()
    rgb.save(buffer, format="JPEG", quality=85)
    data = buffer.getvalue()
    part = {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(data).decode("ascii")}}
    return part, hashlib.sha1(data).hexdigest()


def _cached(digest: str) -> dict | None:
    with _cache_lock:
        hit = _cache.get(digest)
        if hit is None:
            return None
        _cache.move_to_end(digest)
        return json.loads(json.dumps(hit))


def _store(digest: str, hit: dict) -> None:
    with _cache_lock:
        _cache[digest] = json.loads(json.dumps(hit))
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)


def _ask(key: str, model: str, image_part: dict) -> dict:
    config = {
        "temperature": 0.2,
        "maxOutputTokens": MAX_OUTPUT_TOKENS,
        "responseMimeType": "application/json",
        "mediaResolution": "MEDIA_RESOLUTION_LOW",
    }
    if model.startswith("gemini-3"):
        config["thinkingConfig"] = {"thinkingLevel": "minimal"}
    body = json.dumps({"contents": [{"parts": [{"text": PROMPT}, image_part]}], "generationConfig": config}).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    with urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse(raw: dict) -> dict | None:
    text = raw["candidates"][0]["content"]["parts"][0]["text"]
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
    data = json.loads(cleaned)
    code = str(data.get("code", "")).upper().strip()
    if code not in BY_CODE:
        return None
    material = BY_CODE[code]
    name = str(data.get("object_name") or material["object_name"])[:80]
    confidence = max(0.4, min(0.98, float(data.get("confidence") or 0.86)))
    hit = {
        "material_code": code,
        "object_name": name,
        "confidence": confidence,
        "bbox": {"x": 0.18, "y": 0.08, "w": 0.64, "h": 0.84},
        "scores": [{"code": item, "score": max(confidence, 0.5) if item == code else 0.04} for item in CODES],
        "container": material["container"],
        "full_name": material["full_name"],
    }
    return attach_guide(hit, data)
