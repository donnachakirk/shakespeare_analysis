import json
from pathlib import Path

import requests

from shakespeare_geo.geocode import geocode_place, load_cache, save_cache


class FakeResponse:
    def __init__(self, payload=None, status_error: Exception | None = None):
        self._payload = payload or []
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error:
            raise self._status_error

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        if isinstance(response, list):
            self.responses = response
        else:
            self.responses = [response]
        self._response_idx = 0
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        idx = min(self._response_idx, len(self.responses) - 1)
        self._response_idx += 1
        return self.responses[idx]


def test_cache_roundtrip(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    cache = {
        "Verona": {
            "geocode_name": "Verona, Veneto, Italy",
            "geocode_lat": 45.0,
            "geocode_lon": 10.9,
            "geocode_precision": "city",
            "geocode_addresstype": "city",
            "geocode_class": "place",
            "geocode_id": "relation:44874",
        }
    }
    save_cache(cache_file, cache)

    loaded = load_cache(cache_file)
    assert loaded == cache


def test_load_cache_normalizes_legacy_schema(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    cache_file.write_text(
        json.dumps(
            {
                "Verona": {
                    "geocode_name": "Verona, Veneto, Italy",
                    "geocode_lat": "45.4384",
                    "geocode_lon": "10.9916",
                    "geocode_type": "city",
                    "geocode_id": "relation:44874",
                }
            }
        )
    )

    loaded = load_cache(cache_file)
    assert loaded["Verona"]["geocode_precision"] == "city"
    assert loaded["Verona"]["geocode_lat"] == 45.4384
    assert loaded["Verona"]["geocode_addresstype"] is None


def test_geocode_place_success_and_cache():
    payload = [
        {
            "display_name": "Verona, Veneto, Italy",
            "lat": "45.4384",
            "lon": "10.9916",
            "type": "city",
            "class": "place",
            "osm_type": "relation",
            "osm_id": 44874,
        }
    ]
    session = FakeSession(FakeResponse(payload=payload))
    cache = {}

    result = geocode_place(
        query="Verona",
        session=session,
        user_agent="shakespeare-geo/0.1 (test@example.com)",
        email="test@example.com",
        cache=cache,
        sleep_s=0,
    )

    assert result["geocode_name"] == "Verona, Veneto, Italy"
    assert result["geocode_lat"] == 45.4384
    assert result["geocode_lon"] == 10.9916
    assert result["geocode_id"] == "relation:44874"
    assert cache["Verona"] == result
    assert session.calls[0]["params"]["email"] == "test@example.com"
    assert session.calls[0]["params"]["featuretype"] == "settlement"


def test_geocode_place_http_error_is_non_fatal():
    error = requests.HTTPError("403 Client Error")
    session = FakeSession(FakeResponse(status_error=error))
    cache = {}

    result = geocode_place(
        query="Capel's monument",
        session=session,
        user_agent="shakespeare-geo/0.1 (test@example.com)",
        email="test@example.com",
        cache=cache,
        sleep_s=0,
    )

    assert result is None
    assert cache["Capel's monument"] is None


def test_geocode_place_refreshes_stale_cached_administrative_entry():
    payload = [
        {
            "display_name": "Verona, Veneto, Italy",
            "lat": "45.4384",
            "lon": "10.9916",
            "type": "administrative",
            "addresstype": "city",
            "class": "boundary",
            "osm_type": "relation",
            "osm_id": 44874,
        }
    ]
    session = FakeSession(FakeResponse(payload=payload))
    cache = {
        "Verona": {
            "geocode_name": "Verona, Veneto, Italy",
            "geocode_lat": 45.4384,
            "geocode_lon": 10.9916,
            "geocode_precision": "administrative",
            "geocode_id": "relation:44874",
        }
    }

    result = geocode_place(
        query="Verona",
        session=session,
        user_agent="shakespeare-geo/0.1 (test@example.com)",
        email="test@example.com",
        cache=cache,
        sleep_s=0,
    )

    assert result["geocode_addresstype"] == "city"
    assert result["geocode_class"] == "boundary"
    assert len(session.calls) == 1


def test_geocode_place_falls_back_when_settlement_query_empty():
    settlement_empty = FakeResponse(payload=[])
    broad_success = FakeResponse(
        payload=[
            {
                "display_name": "Aurora, Illinois, United States",
                "lat": "41.7571701",
                "lon": "-88.3147539",
                "type": "administrative",
                "addresstype": "city",
                "class": "boundary",
                "osm_type": "relation",
                "osm_id": 124817,
            }
        ]
    )
    session = FakeSession([settlement_empty, broad_success])
    cache = {}

    result = geocode_place(
        query="Aurora",
        session=session,
        user_agent="shakespeare-geo/0.1 (test@example.com)",
        email="test@example.com",
        cache=cache,
        sleep_s=0,
    )

    assert result is not None
    assert result["geocode_name"].startswith("Aurora")
    assert len(session.calls) == 2
    assert session.calls[0]["params"]["featuretype"] == "settlement"
    assert "featuretype" not in session.calls[1]["params"]
