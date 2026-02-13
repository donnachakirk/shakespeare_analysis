from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional

import requests
from requests import HTTPError


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
STALE_ADMIN_ADDRESSTYPES = {
    "",
    "administrative",
    "country",
    "state",
    "region",
    "province",
    "county",
    "continent",
}
CACHE_KEYS = (
    "geocode_name",
    "geocode_lat",
    "geocode_lon",
    "geocode_precision",
    "geocode_addresstype",
    "geocode_class",
    "geocode_id",
)


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_cached_result(value: object) -> tuple[dict | None, bool]:
    if value is None:
        return None, False
    if not isinstance(value, dict):
        return None, True

    normalized: dict[str, object] = {key: value.get(key) for key in CACHE_KEYS}
    if normalized["geocode_precision"] is None:
        normalized["geocode_precision"] = value.get("geocode_type")

    lat = _coerce_float(normalized["geocode_lat"])
    lon = _coerce_float(normalized["geocode_lon"])
    if lat is None or lon is None:
        return None, True

    normalized["geocode_lat"] = lat
    normalized["geocode_lon"] = lon

    is_stale = False
    if not normalized.get("geocode_name"):
        is_stale = True
    if not normalized.get("geocode_precision"):
        is_stale = True
    if not normalized.get("geocode_id"):
        is_stale = True

    # Old cache entries for city relations often lacked these fields and were
    # incorrectly rejected downstream as non-settlement.
    if (
        str(normalized.get("geocode_precision") or "").strip().lower() == "administrative"
        and str(normalized.get("geocode_addresstype") or "").strip().lower()
        in STALE_ADMIN_ADDRESSTYPES
    ):
        is_stale = True

    return normalized, is_stale


def _query_nominatim(
    query: str,
    session: requests.Session,
    user_agent: str,
    email: str | None,
    featuretype: str | None,
    sleep_s: float,
) -> tuple[dict | None, bool]:
    params = {
        "q": query,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": 1,
    }
    if featuretype:
        params["featuretype"] = featuretype
    if email:
        params["email"] = email
    headers = {"User-Agent": user_agent}

    resp = session.get(NOMINATIM_URL, params=params, headers=headers, timeout=30)
    try:
        resp.raise_for_status()
    except HTTPError:
        time.sleep(sleep_s)
        return None, True

    data = resp.json()
    time.sleep(sleep_s)
    if not data:
        return None, False

    item = data[0]
    lat = _coerce_float(item.get("lat"))
    lon = _coerce_float(item.get("lon"))
    if lat is None or lon is None:
        return None, False

    result = {
        "geocode_name": item.get("display_name"),
        "geocode_lat": lat,
        "geocode_lon": lon,
        "geocode_precision": item.get("type"),
        "geocode_addresstype": item.get("addresstype"),
        "geocode_class": item.get("class"),
        "geocode_id": f"{item.get('osm_type')}:{item.get('osm_id')}",
    }
    return result, False


def load_cache(path: Path) -> Dict[str, dict | None]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    cache: Dict[str, dict | None] = {}
    for key, value in raw.items():
        normalized, _ = normalize_cached_result(value)
        cache[key] = normalized
    return cache


def save_cache(path: Path, cache: Dict[str, dict | None]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True))


def geocode_place(
    query: str,
    session: requests.Session,
    user_agent: str,
    email: str | None,
    cache: Dict[str, dict | None],
    sleep_s: float = 1.0,
) -> Optional[dict]:
    if query in cache:
        normalized, is_stale = normalize_cached_result(cache.get(query))
        cache[query] = normalized
        if not is_stale:
            return normalized

    # Try settlement-focused query first to avoid broad administrative matches.
    for featuretype in ("settlement", None):
        result, had_http_error = _query_nominatim(
            query=query,
            session=session,
            user_agent=user_agent,
            email=email,
            featuretype=featuretype,
            sleep_s=sleep_s,
        )
        if had_http_error:
            # Avoid aborting the whole pipeline on a single place lookup failure.
            cache[query] = None
            return None
        if result is not None:
            cache[query] = result
            return result

    cache[query] = None
    return None
