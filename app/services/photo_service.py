"""Análisis de fotos con MIRA, TrashNet y reglas de forma/color."""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import numpy as np
from PIL import Image

from app.models.catalog import BY_CODE
from app.services.guide import attach_guide

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent
UPLOADS = Path(os.environ.get("ECOSCAN_UPLOADS", BACKEND / "data" / "uploads"))


def _first_existing(paths: list[Path]) -> Path:
    for path in paths:
        if path and str(path) != "." and path.exists():
            return path
    return paths[-1]


MIRA_PATH = _first_existing(
    [
        Path(os.environ["MIRA_MODEL"]) if os.environ.get("MIRA_MODEL") else Path(),
        BACKEND / "models" / "mira_exp019.onnx",
        ROOT / "frontend" / "public" / "models" / "mira_exp019.onnx",
    ]
)
TRASH_PATH = _first_existing(
    [
        Path(os.environ["TRASHNET_MODEL"]) if os.environ.get("TRASHNET_MODEL") else Path(),
        BACKEND / "models" / "trashnet.json",
        ROOT / "frontend" / "public" / "models" / "trashnet.json",
    ]
)

MIRA_INPUT = 640
MIRA_MIN = 0.28
MIRA_NAMES = [
    {"object_name": "Vaso de vidrio", "code": "VID", "label": "glass"},
    {"object_name": "Lata de metal", "code": "MET", "label": "metal"},
    {"object_name": "Papel", "code": "PAP", "label": "paper"},
    {"object_name": "Plástico", "code": "PET", "label": "plastic"},
    {"object_name": "Basura", "code": "GEN", "label": "trash"},
]
TRASH_MAP = {
    "cardboard": ("PAP", "Caja de cartón"),
    "paper": ("PAP", "Hoja de papel"),
    "glass": ("VID", "Frasco de vidrio"),
    "metal": ("MET", "Lata de metal"),
    "plastic": ("PET", "Botella plástica"),
    "trash": ("GEN", "Residuo general"),
}
CODES = ["PET", "HDPE", "MLT", "PAP", "VID", "MET", "ORG", "GEN"]


class PhotoService:
    def __init__(self) -> None:
        self._session = None
        self._trash = None
        self._ready = False

    def warmup(self) -> None:
        UPLOADS.mkdir(parents=True, exist_ok=True)
        self._load_mira()
        self._load_trash()
        self._ready = True

    def analyze(self, image: Image.Image) -> dict:
        started = time.perf_counter()
        rgb = image.convert("RGB")
        rgb.thumbnail((1280, 1280), Image.Resampling.BILINEAR)
        array = np.asarray(rgb, dtype=np.uint8)
        from app.services.vision_ai import classify as classify_gemini

        gemini = classify_gemini(rgb)
        if gemini:
            return gemini
        stick = self._lock_thin_object(array)
        if stick:
            stick["inference_ms"] = round((time.perf_counter() - started) * 1000, 1)
            stick["engine"] = "forma"
            return attach_guide(stick)
        mira = self._detect_mira(rgb)
        box = mira["bbox"] if mira else content_box(array)
        trash = self._classify_trash(array, box)
        lock = self._lock_object(array, box)
        hit = self._fuse(mira, trash, lock, box)
        hit["inference_ms"] = round((time.perf_counter() - started) * 1000, 1)
        hit["engine"] = "mira+trashnet"
        return attach_guide(hit)

    def _lock_thin_object(self, array: np.ndarray) -> dict | None:
        box = find_stick_box(array)
        if not box:
            return None
        stats = region_stats(array, box)
        if not stats:
            return make_hit("GEN", "Lapicero", 0.86, box)
        if looks_like_soda_bottle(stats) and box["w"] > 0.16:
            return None
        name = "Lápiz" if stats["wood"] > 0.16 and stats["pale"] < 0.28 else "Lapicero"
        return make_hit("GEN", name, 0.9, box)

    def save_upload(self, raw: bytes, filename: str, owner: str) -> Path:
        UPLOADS.mkdir(parents=True, exist_ok=True)
        stamp = str(int(time.time() * 1000))
        safe = "".join(ch for ch in Path(filename).name if ch.isalnum() or ch in ".-_")[:80] or "foto.jpg"
        path = UPLOADS / f"{owner}_{stamp}_{safe}"
        path.write_bytes(raw)
        return path

    def _load_mira(self):
        if self._session is not None:
            return self._session
        if not MIRA_PATH.exists():
            return None
        import onnxruntime as ort

        self._session = ort.InferenceSession(str(MIRA_PATH), providers=["CPUExecutionProvider"])
        return self._session

    def _load_trash(self):
        if self._trash is not None:
            return self._trash
        if not TRASH_PATH.exists():
            return None
        self._trash = json.loads(TRASH_PATH.read_text(encoding="utf-8"))
        return self._trash

    def _detect_mira(self, image: Image.Image) -> dict | None:
        session = self._load_mira()
        if session is None:
            return None
        tensor, scale, dx, dy = letterbox(image, MIRA_INPUT)
        name = session.get_inputs()[0].name
        output = session.run(None, {name: tensor})[0]
        detection = best_box(output, scale, dx, dy, image.width, image.height)
        if detection is None:
            return None
        known = MIRA_NAMES[detection["class_id"]]
        tall = detection["h"] / max(detection["w"], 0.01) >= 1.18
        code = "PET" if known["code"] == "PET" and tall else ("HDPE" if known["code"] == "PET" else known["code"])
        name = "Botella plástica" if code == "PET" else ("Envase de plástico" if code == "HDPE" else known["object_name"])
        return {
            "code": code,
            "object_name": name,
            "confidence": clamp(detection["score"], 0.0, 0.99),
            "bbox": {key: detection[key] for key in ("x", "y", "w", "h")},
            "label": known["label"],
        }

    def _classify_trash(self, array: np.ndarray, box: dict) -> dict | None:
        model = self._load_trash()
        if model is None:
            return None
        features = extract_crop(array, box, int(model["size"]), int(model["hueBins"]))
        mean = np.asarray(model["mean"], dtype=np.float32)
        std = np.asarray(model["std"], dtype=np.float32)
        z = (features - mean) / np.where(std == 0, 1, std)
        weights = np.asarray(model["weights"], dtype=np.float32)
        bias = np.asarray(model["bias"], dtype=np.float32)
        logits = weights @ z + bias
        proto = np.asarray(model["prototypes"], dtype=np.float32)
        labels = np.asarray(model["protoLabels"], dtype=np.int32)
        if len(proto):
            dist = np.sum((proto - z) ** 2, axis=1)
            nearest = np.argsort(dist)[:5]
            votes = np.zeros(len(model["classes"]), dtype=np.float32)
            for index in nearest:
                votes[int(labels[index])] += 1
            logits = logits + 0.45 * votes
        scores = softmax(logits)
        best = int(np.argmax(scores))
        label = model["classes"][best]
        table = {name: float(scores[i]) for i, name in enumerate(model["classes"])}
        return {"label": label, "confidence": clamp(float(scores[best]), 0.0, 0.99), "scores": table}

    def _lock_object(self, array: np.ndarray, box: dict) -> dict | None:
        stats = region_stats(array, box)
        if not stats:
            return None
        stick = looks_like_stick(stats, box)
        if stick:
            return stick
        if looks_like_soda_bottle(stats):
            return make_hit("PET", "Botella plástica PET", 0.92, box)
        if looks_like_food(stats):
            return make_hit("ORG", "Restos orgánicos", 0.84, box)
        if looks_like_sheet(stats, box):
            return make_hit("PAP", "Hoja de papel", 0.86, box)
        if looks_like_cardboard(stats):
            return make_hit("PAP", "Caja de cartón", 0.84, box)
        if looks_like_phone(stats, box):
            return make_hit("GEN", "Celular", 0.8, box)
        return None

    def _fuse(self, mira: dict | None, trash: dict | None, lock: dict | None, box: dict) -> dict:
        if lock and lock["object_name"] in {"Lápiz", "Lapicero", "Celular", "Botella plástica PET", "Restos orgánicos", "Hoja de papel"}:
            return lock
        if lock and lock.get("material_code") == "PAP" and lock["object_name"] == "Caja de cartón":
            if not mira or mira["code"] in {"PAP", "GEN"}:
                return lock
        if trash and trash["label"] == "plastic" and mira and mira["code"] == "MET":
            return refine_plastic(make_hit("PET", "Botella plástica", max(0.78, trash["confidence"]), mira["bbox"]))
        if mira and trash and same_family(mira["code"], TRASH_MAP[trash["label"]][0]):
            code, name = TRASH_MAP[trash["label"]]
            if code in {"PET", "HDPE"}:
                return refine_plastic(make_hit(code, name, clamp(0.58 + 0.22 * mira["confidence"] + 0.22 * trash["confidence"], 0.66, 0.98), mira["bbox"]))
            if code == "PAP":
                name = "Caja de cartón" if trash["label"] == "cardboard" else "Hoja de papel"
            return make_hit(code, name, clamp(0.58 + 0.22 * mira["confidence"] + 0.22 * trash["confidence"], 0.66, 0.98), mira["bbox"])
        if trash and trash["confidence"] >= 0.6 and (not mira or mira["confidence"] < 0.58):
            code, name = TRASH_MAP[trash["label"]]
            hit = make_hit(code, name, trash["confidence"], mira["bbox"] if mira else box)
            return refine_plastic(hit) if code in {"PET", "HDPE"} else hit
        if lock and (not mira or mira["confidence"] < 0.58):
            return lock
        if mira:
            return refine_plastic(mira) if mira["code"] in {"PET", "HDPE"} else make_hit(mira["code"], mira["object_name"], mira["confidence"], mira["bbox"])
        if trash:
            code, name = TRASH_MAP[trash["label"]]
            hit = make_hit(code, name, trash["confidence"], box)
            return refine_plastic(hit) if code in {"PET", "HDPE"} else hit
        if lock:
            return lock
        return make_hit("GEN", "Residuo general", 0.42, box)


photo_service = PhotoService()


def make_hit(code: str, object_name: str, confidence: float, bbox: dict) -> dict:
    material = BY_CODE[code]
    return attach_guide(
        {
            "material_code": code,
            "object_name": object_name,
            "confidence": clamp(confidence, 0.35, 0.98),
            "bbox": bbox,
            "scores": [{"code": item, "score": max(confidence, 0.5) if item == code else 0.04} for item in CODES],
            "container": material["container"],
            "full_name": material["full_name"],
        }
    )


def refine_plastic(hit: dict) -> dict:
    box = hit["bbox"]
    tall = box["h"] / max(box["w"], 0.01) >= 1.18
    code = "PET" if tall else "HDPE"
    name = "Botella plástica PET" if tall else "Envase de plástico"
    return make_hit(code, name, hit["confidence"], box)


def same_family(a: str, b: str) -> bool:
    if a == b:
        return True
    return {a, b} <= {"PET", "HDPE"}


def letterbox(image: Image.Image, size: int):
    scale = min(size / image.width, size / image.height)
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    dx = (size - width) // 2
    dy = (size - height) // 2
    canvas = Image.new("RGB", (size, size), (114, 114, 114))
    resized = image.resize((width, height), Image.Resampling.BILINEAR)
    canvas.paste(resized, (dx, dy))
    pixels = np.asarray(canvas, dtype=np.float32) / 255.0
    tensor = np.transpose(pixels, (2, 0, 1))[None, ...]
    return tensor, scale, dx, dy


def best_box(output: np.ndarray, scale: float, dx: int, dy: int, frame_w: int, frame_h: int) -> dict | None:
    data = np.asarray(output, dtype=np.float32)
    dims = data.shape
    if data.ndim == 3:
        a, b = dims[-2], dims[-1]
        if a <= 16 and b > a:
            rows, cols, channel_first = b, a, True
            data = data.reshape(a, b)
        else:
            rows, cols, channel_first = a, b, False
            data = data.reshape(a, b)
    else:
        return None

    found = []
    for index in range(rows):
        def value(column: int, i=index) -> float:
            return float(data[column, i] if channel_first else data[i, column])

        score = 0.0
        class_id = 0
        if cols == 6:
            score = value(4)
            class_id = int(round(value(5)))
        else:
            for column in range(4, cols):
                next_score = value(column)
                if next_score > score:
                    score = next_score
                    class_id = column - 4
        if score < MIRA_MIN or class_id < 0 or class_id >= len(MIRA_NAMES):
            continue
        width = value(2)
        height = value(3)
        x = (value(0) - width / 2 - dx) / scale / frame_w
        y = (value(1) - height / 2 - dy) / scale / frame_h
        w = width / scale / frame_w
        h = height / scale / frame_h
        if w < 0.03 or h < 0.03 or w > 0.96 or h > 0.96 or w * h > 0.72:
            continue
        found.append(
            {
                "x": clamp(x, 0, 1),
                "y": clamp(y, 0, 1),
                "w": clamp(w, 0, 1),
                "h": clamp(h, 0, 1),
                "score": score,
                "class_id": class_id,
            }
        )
    found.sort(key=lambda item: item["score"], reverse=True)
    return found[0] if found else None


def extract_crop(array: np.ndarray, box: dict, size: int, hue_bins: int) -> np.ndarray:
    height, width = array.shape[:2]
    x0 = max(0, int(box["x"] * width))
    y0 = max(0, int(box["y"] * height))
    x1 = min(width, int(math.ceil((box["x"] + box["w"]) * width)))
    y1 = min(height, int(math.ceil((box["y"] + box["h"]) * height)))
    crop = array[y0:max(y0 + 1, y1), x0:max(x0 + 1, x1)]
    small = np.asarray(Image.fromarray(crop).resize((size, size), Image.Resampling.BILINEAR), dtype=np.float32)
    red, green, blue = small[..., 0], small[..., 1], small[..., 2]
    hsv = rgb_to_hsv(red, green, blue)
    hue, sat, val = hsv
    hues = np.zeros(hue_bins, dtype=np.float32)
    mask = (sat > 0.12) & (val > 0.15)
    if np.any(mask):
        bins = np.minimum(hue_bins - 1, np.floor(hue[mask] / (360 / hue_bins)).astype(np.int32))
        hues = np.bincount(bins, minlength=hue_bins).astype(np.float32)
        hues /= max(float(mask.sum()), 1.0)
    white = float(np.mean((val > 0.78) & (sat < 0.14)))
    brown = float(np.mean((hue >= 12) & (hue <= 48) & (sat > 0.22) & (val > 0.18) & (val < 0.82)))
    green_n = float(np.mean((hue >= 75) & (hue <= 165) & (sat > 0.22) & (val > 0.2)))
    blue_n = float(np.mean((hue >= 175) & (hue <= 255) & (sat > 0.1) & (val > 0.45)))
    yellow = float(np.mean((hue >= 40) & (hue <= 75) & (sat > 0.28) & (val > 0.4)))
    gray = float(np.mean((sat < 0.12) & (val > 0.22) & (val < 0.78)))
    reds = float(np.mean((red > 115) & (red > green * 1.28) & (red > blue * 1.28)))
    dark = float(np.mean(val < 0.25))
    object_n = 1.0 - white
    lum = red + green + blue
    edges = float(np.mean(np.abs(np.diff(lum, axis=1)) > 48))
    mid = size // 2
    quads = [
        small[:mid, :mid],
        small[:mid, mid:],
        small[mid:, :mid],
        small[mid:, mid:],
    ]
    quad_means = [q.mean(axis=(0, 1)) / 255.0 if q.size else np.zeros(3) for q in quads]
    features = [
        *hues.tolist(),
        float(sat.mean()),
        float(val.mean()),
        float(val.std()),
        white,
        brown,
        green_n,
        blue_n,
        yellow,
        gray,
        reds,
        dark,
        object_n,
        edges / 2,
        float(red.mean() / 255),
        float(green.mean() / 255),
        float(blue.mean() / 255),
        float(red.std() / 255),
        float(green.std() / 255),
        float(blue.std() / 255),
        float(sat.std()),
        float(np.mean(val > 0.9)),
        *np.concatenate(quad_means).tolist(),
    ]
    return np.asarray(features, dtype=np.float32)


def rgb_to_hsv(red: np.ndarray, green: np.ndarray, blue: np.ndarray):
    r, g, b = red / 255.0, green / 255.0, blue / 255.0
    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    delta = maxc - minc
    hue = np.zeros_like(maxc)
    mask = delta != 0
    rmask = mask & (maxc == r)
    gmask = mask & (maxc == g)
    bmask = mask & (maxc == b)
    hue[rmask] = np.mod((g[rmask] - b[rmask]) / delta[rmask], 6)
    hue[gmask] = (b[gmask] - r[gmask]) / delta[gmask] + 2
    hue[bmask] = (r[bmask] - g[bmask]) / delta[bmask] + 4
    hue = hue * 60
    hue[hue < 0] += 360
    sat = np.divide(delta, maxc, out=np.zeros_like(maxc), where=maxc != 0)
    return hue, sat, maxc


def region_stats(array: np.ndarray, box: dict) -> dict | None:
    height, width = array.shape[:2]
    x0 = max(0, int(box["x"] * width))
    y0 = max(0, int(box["y"] * height))
    x1 = min(width, int(math.ceil((box["x"] + box["w"]) * width)))
    y1 = min(height, int(math.ceil((box["y"] + box["h"]) * height)))
    crop = array[y0:max(y0 + 1, y1), x0:max(x0 + 1, x1)]
    if crop.size == 0:
        return None
    step = max(1, crop.shape[0] * crop.shape[1] // 12000)
    sample = crop[::step, ::step]
    red = sample[..., 0].astype(np.float32)
    green = sample[..., 1].astype(np.float32)
    blue = sample[..., 2].astype(np.float32)
    hue, sat, val = rgb_to_hsv(red, green, blue)
    return {
        "pale": float(np.mean((val > 0.62) & (sat < 0.22))),
        "red_print": float(np.mean(((hue <= 10) | (hue >= 348)) & (sat > 0.38) & (val > 0.28))),
        "gray": float(np.mean((sat < 0.12) & (val > 0.28) & (val < 0.68))),
        "white": float(np.mean((val > 0.78) & (sat < 0.14))),
        "brown": float(np.mean((hue >= 12) & (hue <= 48) & (sat > 0.22) & (val > 0.18) & (val < 0.82))),
        "green": float(np.mean((hue >= 75) & (hue <= 165) & (sat > 0.22) & (val > 0.2))),
        "yellow": float(np.mean((hue >= 40) & (hue <= 75) & (sat > 0.28) & (val > 0.4))),
        "dark": float(np.mean(val < 0.25)),
        "ink": float(np.mean((val < 0.35) & (sat < 0.45))),
        "wood": float(np.mean((hue >= 18) & (hue <= 50) & (sat > 0.22) & (val > 0.25) & (val < 0.9))),
        "food": float(np.mean(((hue >= 8) & (hue <= 70) & (sat > 0.28) & (val > 0.25)) | ((hue >= 75) & (hue <= 150) & (sat > 0.25)))),
        "black": float(np.mean(val < 0.18)),
        "ratio": box["h"] / max(box["w"], 0.01),
        "wide": box["w"] / max(box["h"], 0.01),
        "area": box["w"] * box["h"],
    }


def find_stick_box(array: np.ndarray) -> dict | None:
    """Busca un trazo fino vertical u horizontal: lapicero, lápiz, pluma."""
    height, width = array.shape[:2]
    gray = array.mean(axis=2)
    vertical = _band_box(gray, axis=0, length=width, other=height)
    horizontal = _band_box(gray, axis=1, length=height, other=width)
    candidates = [item for item in (vertical, horizontal) if item]
    if not candidates:
        return None
    best = min(candidates, key=lambda item: item["w"] * item["h"])
    thin = best["h"] / max(best["w"], 0.01) >= 2.8 or best["w"] / max(best["h"], 0.01) >= 2.8
    if not thin or best["w"] * best["h"] > 0.28:
        return None
    return best


def _band_box(gray: np.ndarray, axis: int, length: int, other: int) -> dict | None:
    delta = np.abs(np.diff(gray, axis=1 - axis, prepend=np.take(gray, [0], axis=1 - axis)))
    energy = delta.mean(axis=axis)
    if energy.size < 8:
        return None
    win = np.ones(5) / 5
    smooth = np.convolve(energy, win, mode="same")
    peak = float(smooth.max())
    if peak < 3.2:
        return None
    active = np.where(smooth >= peak * 0.38)[0]
    if len(active) < 3:
        return None
    span = (int(active[-1]) - int(active[0]) + 1) / max(length, 1)
    if span > 0.16 or span < 0.008:
        return None
    start = max(0, int(active[0]) - 3)
    end = min(length, int(active[-1]) + 4)
    if axis == 0:
        band = delta[:, start:end]
        along = band.mean(axis=1)
        rows = np.where(along >= max(float(along.max()) * 0.18, 1.2))[0]
        if len(rows) < 8:
            return None
        y0 = max(0, int(rows[0]) - 4) / other
        y1 = min(other, int(rows[-1]) + 4) / other
        return {"x": start / length, "y": y0, "w": max(0.02, (end - start) / length), "h": max(0.08, y1 - y0)}
    band = delta[start:end, :]
    along = band.mean(axis=0)
    cols = np.where(along >= max(float(along.max()) * 0.18, 1.2))[0]
    if len(cols) < 8:
        return None
    x0 = max(0, int(cols[0]) - 4) / other
    x1 = min(other, int(cols[-1]) + 4) / other
    return {"x": x0, "y": start / length, "w": max(0.08, x1 - x0), "h": max(0.02, (end - start) / length)}


def content_box(array: np.ndarray) -> dict:
    height, width = array.shape[:2]
    corners = np.concatenate(
        [
            array[:10, :10].reshape(-1, 3),
            array[:10, -10:].reshape(-1, 3),
            array[-10:, :10].reshape(-1, 3),
            array[-10:, -10:].reshape(-1, 3),
        ]
    ).astype(np.float32)
    background = corners.mean(axis=0)
    distance = np.linalg.norm(array.astype(np.float32) - background, axis=2)
    ys, xs = np.where(distance > 16)
    if len(xs) < 80:
        return {"x": 0.12, "y": 0.12, "w": 0.76, "h": 0.76}
    pad_x = max(4, width // 40)
    pad_y = max(4, height // 40)
    x0 = max(0, int(xs.min()) - pad_x) / width
    y0 = max(0, int(ys.min()) - pad_y) / height
    x1 = min(width, int(xs.max()) + pad_x) / width
    y1 = min(height, int(ys.max()) + pad_y) / height
    return {"x": x0, "y": y0, "w": max(0.04, x1 - x0), "h": max(0.04, y1 - y0)}


def looks_like_soda_bottle(stats: dict) -> bool:
    if stats["wood"] >= 0.18 or stats["gray"] >= 0.55:
        return False
    has_label = stats["red_print"] > 0.02
    has_body = stats["pale"] > 0.16
    tall = stats["ratio"] >= 1.08
    return has_label and has_body and (tall or stats["red_print"] > 0.08)


def looks_like_stick(stats: dict, box: dict) -> dict | None:
    thin = stats["ratio"] >= 3.1 or stats["wide"] >= 3.1
    if not thin or stats["area"] > 0.34:
        return None
    name = "Lápiz" if stats["wood"] > 0.1 else "Lapicero"
    return make_hit("GEN", name, 0.88, box)


def looks_like_food(stats: dict) -> bool:
    return stats["food"] > 0.22 and stats["pale"] < 0.35 and stats["area"] < 0.7 and stats["ratio"] < 2.6


def looks_like_sheet(stats: dict, box: dict) -> bool:
    rectangular = 0.62 <= stats["wide"] <= 1.7
    compact = box["w"] < 0.94 and box["h"] < 0.94
    return stats["white"] > 0.38 and rectangular and compact and stats["red_print"] < 0.08 and stats["food"] < 0.2


def looks_like_cardboard(stats: dict) -> bool:
    return stats["brown"] > 0.28 and stats["white"] < 0.22 and stats["red_print"] < 0.08


def looks_like_phone(stats: dict, box: dict) -> bool:
    return 1.5 <= stats["ratio"] <= 2.4 and stats["black"] > 0.28 and stats["area"] < 0.35 and box["w"] < 0.55


def softmax(values: np.ndarray) -> np.ndarray:
    shift = values - np.max(values)
    exp = np.exp(shift)
    return exp / max(float(exp.sum()), 1e-6)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
