"""Gemini ve la foto y la clasifica con el catálogo de EcoScan."""

from __future__ import annotations

import base64
import json
import os
import time
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from app.models.catalog import BY_CODE
from app.services.guide import attach_guide

MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]
CODES = ["PET", "HDPE", "MLT", "PAP", "VID", "MET", "ORG", "GEN"]
PROMPT = """Eres el clasificador de EcoScan. Mira la foto y di QUÉ objeto es, no de qué material está hecho el fondo.

Elige exactamente un código:
PET = botella plástica transparente de agua, gaseosa o jugo. Contenedor amarillo.
HDPE = envase opaco de champú, detergente o yogur. Amarillo.
MLT = caja de leche o jugo tipo Tetra Pak. Amarillo.
PAP = hoja de papel o caja de cartón. Azul.
VID = frasco o botella de vidrio. Verde.
MET = lata de metal. Gris.
ORG = restos de comida, cáscaras, fruta. Marrón.
GEN = no se recicla: lapicero, bolígrafo, pluma, lápiz, celular, control remoto, papel higiénico, servilleta sucia, bolsa de snack.

Reglas estrictas:
- Un bolígrafo, lapicero o pluma (aunque sea de plástico transparente) es GEN, nunca PET ni HDPE.
- Un lápiz es GEN.
- Una botella de gaseosa o agua es PET.
- Ignora la mesa, la mano, la ropa y el fondo.
- Si hay duda entre envase y útil de escribir, gana el útil de escribir.

También explica EN ESPAÑOL, como a un vecino, qué es ESE objeto y qué hacer con ÉL. No copies un texto genérico del material: habla del objeto de la foto (control, lapicero, papel higiénico, botella, etc.).

Responde SOLO JSON:
{
  "code":"GEN",
  "object_name":"Control remoto",
  "confidence":0.95,
  "meaning":"Qué es y por qué se recicla o no de esa forma (2 o 3 frases).",
  "destination":"A qué contenedor o punto va, con el color. Si hay pilas o RAEE, dilo.",
  "actions":["Paso concreto 1","Paso concreto 2","Paso concreto 3"],
  "tip":"Una advertencia corta para no contaminar el resto del reciclaje."
}
"""


def has_gemini() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def classify(image: Image.Image) -> dict | None:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    started = time.perf_counter()
    payload = _image_part(image)
    for model in MODELS:
        try:
            raw = _ask(key, model, payload)
            hit = _parse(raw)
            if hit:
                hit["inference_ms"] = round((time.perf_counter() - started) * 1000, 1)
                hit["engine"] = "gemini"
                return hit
        except HTTPError as error:
            last = error.read().decode("utf-8", errors="ignore")[:300]
            print(f"Gemini {model}: {error.code} {last}")
            if error.code == 503:
                time.sleep(0.8)
            continue
        except (URLError, TimeoutError, json.JSONDecodeError, KeyError, ValueError, OSError) as error:
            print(f"Gemini {model}: {error}")
            continue
    return None


def _image_part(image: Image.Image) -> dict:
    rgb = image.convert("RGB")
    rgb.thumbnail((1024, 1024), Image.Resampling.BILINEAR)
    buffer = BytesIO()
    rgb.save(buffer, format="JPEG", quality=88)
    return {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}}


def _ask(key: str, model: str, image_part: dict) -> dict:
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": PROMPT}, image_part]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        }
    ).encode("utf-8")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
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
