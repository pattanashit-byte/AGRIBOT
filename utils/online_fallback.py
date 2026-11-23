"""
Optional "second opinion" from an online crop-disease model
(Kindwise crop.health).

Used ONLY when the local CNN is not confident, so Agribot never has to show a
wrong disease name. Disabled automatically if no API key is configured.

Setup:  add  KINDWISE_API_KEY=your_key  to your .env file
        (get one at https://admin.kindwise.com - it is a paid API with
        limited trial credits, so check their pricing page).
"""
import base64
import logging
import os
import threading
import time

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

log = logging.getLogger(__name__)

API_URL = os.getenv(
    "KINDWISE_API_URL", "https://crop.kindwise.com/api/v1/identification"
)
TIMEOUT_SECONDS = float(os.getenv("KINDWISE_TIMEOUT", "25"))
DETAILS = os.getenv("KINDWISE_DETAILS", "description,treatment")

# Protects your credits: at most this many online calls per hour.
MAX_CALLS_PER_HOUR = int(os.getenv("KINDWISE_MAX_CALLS_PER_HOUR", "30"))

_recent_calls = []
_lock = threading.Lock()


def is_enabled():
    return bool(os.getenv("KINDWISE_API_KEY", "").strip())


def _allow_call():
    now = time.time()
    with _lock:
        while _recent_calls and now - _recent_calls[0] > 3600:
            _recent_calls.pop(0)
        if len(_recent_calls) >= MAX_CALLS_PER_HOUR:
            return False
        _recent_calls.append(now)
        return True


def _request(image_b64, details):
    return requests.post(
        API_URL,
        params={"details": details} if details else None,
        headers={"Api-Key": os.getenv("KINDWISE_API_KEY", "").strip()},
        json={"images": [image_b64]},
        timeout=TIMEOUT_SECONDS,
    )


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------

def _text(value):
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("value") or value.get("text")
    value = str(value).strip() if value is not None else ""
    return value or None


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, (list, tuple)):
        items = []
        for entry in value:
            items.extend(_as_list(entry))
        return items
    return [str(value)]


def _treatment_sections(treatment):
    sections = []
    if isinstance(treatment, dict):
        for key, value in treatment.items():
            items = _as_list(value)
            if items:
                sections.append(
                    {"title": str(key).replace("_", " ").capitalize(), "items": items}
                )
    else:
        items = _as_list(treatment)
        if items:
            sections.append({"title": "Treatment", "items": items})
    return sections


def _pretty(name):
    name = str(name or "").strip()
    return name.title() if name.islower() else name


def _parse(data):
    result = (data or {}).get("result") or {}

    diseases = sorted(
        (result.get("disease") or {}).get("suggestions") or [],
        key=lambda s: s.get("probability", 0),
        reverse=True,
    )
    crops = sorted(
        (result.get("crop") or {}).get("suggestions") or [],
        key=lambda s: s.get("probability", 0),
        reverse=True,
    )

    if not diseases:
        return {"ok": False, "reason": "no_suggestions"}

    top = diseases[0]
    details = top.get("details") or {}
    name = _pretty(top.get("name"))

    is_healthy = (
        name.lower() in {"healthy", "healthy plant", "healthy crop"}
        or (result.get("is_healthy") or {}).get("binary") is True
    )

    return {
        "ok": True,
        "disease_name": name,
        "probability": float(top.get("probability") or 0),
        "is_healthy": bool(is_healthy),
        "description": _text(details.get("description")),
        "treatment_sections": _treatment_sections(details.get("treatment")),
        "crop_name": _pretty(crops[0].get("name")) if crops else None,
        "crop_probability": float(crops[0].get("probability") or 0) if crops else None,
        "alternatives": [
            {
                "name": _pretty(s.get("name")),
                "probability": float(s.get("probability") or 0),
            }
            for s in diseases[1:4]
            if float(s.get("probability") or 0) >= 0.10
        ],
    }


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def diagnose_online(image_path):
    """
    Returns {"ok": True, ...normalised result...} or {"ok": False, "reason": ...}.
    Never raises, so the caller can always fall back gracefully.
    """
    if not is_enabled():
        return {"ok": False, "reason": "disabled"}

    if not _allow_call():
        return {"ok": False, "reason": "rate_limited"}

    try:
        with open(image_path, "rb") as handle:
            image_b64 = base64.b64encode(handle.read()).decode("ascii")

        response = _request(image_b64, DETAILS)

        # An unknown "details" name gives HTTP 400: retry without details.
        if response.status_code == 400 and DETAILS:
            response = _request(image_b64, None)

        if response.status_code not in (200, 201):
            log.warning("Online model returned HTTP %s", response.status_code)
            return {"ok": False, "reason": f"http_{response.status_code}"}

        return _parse(response.json())

    except requests.Timeout:
        log.warning("Online model timed out")
        return {"ok": False, "reason": "timeout"}
    except (requests.RequestException, ValueError) as exc:
        log.warning("Online model request failed: %s", exc)
        return {"ok": False, "reason": "network_error"}