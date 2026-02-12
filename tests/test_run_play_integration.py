from __future__ import annotations

import argparse
import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd


class FakeExtraction:
    def __init__(self, text: str, start: int, end: int, normalized: str):
        self.extraction_text = text
        self.char_start = start
        self.char_end = end
        self.attributes = {"normalized_place": normalized, "place_type": "city"}
        self.confidence = 0.9


def load_run_play_module(repo_root: Path):
    if "langextract" not in sys.modules:
        fake_lx = types.SimpleNamespace(
            data=types.SimpleNamespace(ExampleData=object, Extraction=object),
            extract=lambda **kwargs: None,
        )
        sys.modules["langextract"] = fake_lx

    script_path = repo_root / "scripts" / "run_play.py"
    spec = importlib.util.spec_from_file_location("run_play_module", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_run_play_main_writes_outputs(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    run_play = load_run_play_module(repo_root)

    play_text = "ACT I\nSCENE I\nVerona\nMantua\nVerona\n"

    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(
        play_id="romeo_juliet",
        title="Romeo and Juliet",
        gutenberg_url="https://example.org/romeo.txt",
        model="gpt-4o-mini",
        user_agent="shakespeare-geo/0.1 (test@example.com)",
        nominatim_email="test@example.com",
        output_dir="outputs",
    )
    monkeypatch.setattr(run_play, "parse_args", lambda: args)
    monkeypatch.setattr(run_play, "fetch_gutenberg_text", lambda url: play_text)
    monkeypatch.setattr(run_play, "strip_gutenberg_header_footer", lambda text: text)

    def fake_extract_places(text: str, model_id: str):
        assert text == play_text
        assert model_id == "gpt-4o-mini"
        return [
            FakeExtraction("Verona", 15, 21, "Verona"),
            FakeExtraction("Mantua", 22, 28, "Mantua"),
            FakeExtraction("Verona", 29, 35, "Verona"),
        ]

    geocode_lookup = {
        "Verona": {
            "geocode_name": "Verona, Veneto, Italy",
            "geocode_lat": 45.4384,
            "geocode_lon": 10.9916,
            "geocode_precision": "city",
            "geocode_class": "place",
            "geocode_id": "relation:44874",
        },
        "Mantua": {
            "geocode_name": "Mantua, Lombardia, Italy",
            "geocode_lat": 45.1564,
            "geocode_lon": 10.7914,
            "geocode_precision": "city",
            "geocode_class": "place",
            "geocode_id": "relation:44550",
        },
    }

    monkeypatch.setattr(run_play, "extract_places", fake_extract_places)
    monkeypatch.setattr(
        run_play,
        "geocode_place",
        lambda query, session, user_agent, email, cache: geocode_lookup.get(query),
    )

    def fake_build_map(center_lat, center_lon, places, output_path):
        Path(output_path).write_text(f"center={center_lat:.4f},{center_lon:.4f}")

    monkeypatch.setattr(run_play, "build_map", fake_build_map)

    run_play.main()

    mentions_csv = tmp_path / "outputs" / "romeo_juliet_mentions.csv"
    places_csv = tmp_path / "outputs" / "romeo_juliet_places.csv"
    map_html = tmp_path / "outputs" / "romeo_juliet_map.html"

    assert mentions_csv.exists()
    assert places_csv.exists()
    assert map_html.exists()

    mentions_df = pd.read_csv(mentions_csv)
    places_df = pd.read_csv(places_csv)

    assert len(mentions_df) == 3
    assert sorted(mentions_df["normalized_place"].tolist()) == ["Mantua", "Verona", "Verona"]

    verona_row = places_df[places_df["normalized_place"] == "Verona"].iloc[0]
    mantua_row = places_df[places_df["normalized_place"] == "Mantua"].iloc[0]
    assert int(verona_row["mention_count"]) == 2
    assert int(mantua_row["mention_count"]) == 1


def test_run_play_requires_real_nominatim_identity(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    run_play = load_run_play_module(repo_root)

    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(
        play_id="romeo_juliet",
        title="Romeo and Juliet",
        gutenberg_url="https://example.org/romeo.txt",
        model="gpt-4o-mini",
        user_agent="shakespeare-geo/0.1 (contact: you@example.com)",
        nominatim_email=None,
        output_dir="outputs",
    )
    monkeypatch.setattr(run_play, "parse_args", lambda: args)

    try:
        run_play.main()
        assert False, "Expected ValueError for placeholder Nominatim identity"
    except ValueError as exc:
        assert "NOMINATIM_EMAIL" in str(exc)
