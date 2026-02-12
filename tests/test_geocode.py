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
        self.response = response
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return self.response


def test_cache_roundtrip(tmp_path: Path):
    cache_file = tmp_path / "cache.json"
    cache = {"Verona": {"geocode_lat": 45.0, "geocode_lon": 10.9}}
    save_cache(cache_file, cache)

    loaded = load_cache(cache_file)
    assert loaded == cache


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
