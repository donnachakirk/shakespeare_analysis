from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Optional

import requests
from requests import HTTPError


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


def load_cache(path: Path) -> Dict[str, dict]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_cache(path: Path, cache: Dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, sort_keys=True))


def geocode_place(
    query: str,
    session: requests.Session,
    user_agent: str,
    email: str | None,
    cache: Dict[str, dict],
    sleep_s: float = 1.0,
) -> Optional[dict]:
    if query in cache:
        return cache[query]

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
    }
    if email:
        params["email"] = email
    headers = {"User-Agent": user_agent}

    resp = session.get(NOMINATIM_URL, params=params, headers=headers, timeout=30)
    try:
        resp.raise_for_status()
    except HTTPError:
        # Avoid aborting the whole pipeline on a single place lookup failure.
        cache[query] = None
        return None
    data = resp.json()

    if not data:
        cache[query] = None
        return None

    item = data[0]
    result = {
        "geocode_name": item.get("display_name"),
        "geocode_lat": float(item["lat"]),
        "geocode_lon": float(item["lon"]),
        "geocode_precision": item.get("type"),
        "geocode_class": item.get("class"),
        "geocode_id": f"{item.get('osm_type')}:{item.get('osm_id')}",
    }

    cache[query] = result
    time.sleep(sleep_s)
    return result
