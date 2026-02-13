from __future__ import annotations

import argparse
import importlib.util
import sys
import types
from pathlib import Path

import pandas as pd


class FakeExtraction:
    def __init__(
        self,
        text: str,
        start: int,
        end: int,
        normalized: str,
        place_granularity: str = "city",
    ):
        self.extraction_text = text
        self.char_start = start
        self.char_end = end
        self.attributes = {
            "normalized_place": normalized,
            "entity_kind": "place",
            "place_granularity": place_granularity,
            "is_real_world": "true",
            "should_keep": "true",
        }
        self.confidence = 0.9


class FakeExtractionNoSpan:
    def __init__(self, text: str, normalized: str, place_granularity: str = "city"):
        self.extraction_text = text
        self.attributes = {
            "normalized_place": normalized,
            "entity_kind": "place",
            "place_granularity": place_granularity,
            "is_real_world": "true",
            "should_keep": "true",
        }
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


def find_span(text: str, needle: str, start_at: int = 0) -> tuple[int, int]:
    start = text.find(needle, start_at)
    assert start >= 0, f"Needle not found: {needle}"
    return start, start + len(needle)


def test_run_play_main_writes_outputs(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    run_play = load_run_play_module(repo_root)

    play_text = "ACT I\nSCENE I\nROMEO.\nVerona.\nBENVOLIO.\nMantua.\nROMEO.\nVerona.\n"

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
        assert text.rstrip() == play_text.rstrip()
        assert model_id == "gpt-4o-mini"
        cursor = 0
        start_verona_1, end_verona_1 = find_span(text, "Verona", start_at=cursor)
        cursor = end_verona_1
        start_mantua, end_mantua = find_span(text, "Mantua", start_at=cursor)
        cursor = end_mantua
        start_verona_2, end_verona_2 = find_span(text, "Verona", start_at=cursor)
        return [
            FakeExtraction("Verona", start_verona_1, end_verona_1, "Verona"),
            FakeExtraction("Mantua", start_mantua, end_mantua, "Mantua"),
            FakeExtraction("Verona", start_verona_2, end_verona_2, "Verona"),
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
    rejections_csv = tmp_path / "outputs" / "romeo_juliet_rejections.csv"
    places_csv = tmp_path / "outputs" / "romeo_juliet_places.csv"
    map_html = tmp_path / "outputs" / "romeo_juliet_map.html"

    assert mentions_csv.exists()
    assert rejections_csv.exists()
    assert places_csv.exists()
    assert map_html.exists()

    mentions_df = pd.read_csv(mentions_csv)
    rejections_df = pd.read_csv(rejections_csv)
    places_df = pd.read_csv(places_csv)

    assert len(mentions_df) == 3
    assert sorted(mentions_df["normalized_place"].tolist()) == ["Mantua", "Verona", "Verona"]
    assert "mention_sentence" in mentions_df.columns
    assert "spatial_usable" in mentions_df.columns
    assert mentions_df["mention_sentence"].fillna("").str.len().min() > 0

    verona_row = places_df[places_df["normalized_place"] == "Verona"].iloc[0]
    mantua_row = places_df[places_df["normalized_place"] == "Mantua"].iloc[0]
    assert int(verona_row["mention_count"]) == 2
    assert int(mantua_row["mention_count"]) == 1
    assert "mention_sentence" in places_df.columns
    assert str(verona_row["mention_sentence"]).strip() != ""
    assert len(rejections_df) == 0


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


def test_run_play_rejects_country_and_person_like_mentions(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    run_play = load_run_play_module(repo_root)

    play_text = "ACT I\nSCENE I\nROMEO.\nFriar John went from Italy to Verona.\n"

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
        assert text.rstrip() == play_text.rstrip()
        assert model_id == "gpt-4o-mini"
        start_friar_john, end_friar_john = find_span(text, "Friar John")
        start_italy, end_italy = find_span(text, "Italy", start_at=end_friar_john)
        start_verona, end_verona = find_span(text, "Verona", start_at=end_italy)
        return [
            FakeExtraction(
                "Friar John",
                start_friar_john,
                end_friar_john,
                "Friar John",
                place_granularity="city",
            ),
            FakeExtraction("Italy", start_italy, end_italy, "Italy", place_granularity="country"),
            FakeExtraction("Verona", start_verona, end_verona, "Verona", place_granularity="city"),
        ]

    geocode_lookup = {
        "Verona": {
            "geocode_name": "Verona, Veneto, Italy",
            "geocode_lat": 45.4384,
            "geocode_lon": 10.9916,
            "geocode_precision": "city",
            "geocode_addresstype": "city",
            "geocode_class": "place",
            "geocode_id": "relation:44874",
        },
    }

    monkeypatch.setattr(run_play, "extract_places", fake_extract_places)
    monkeypatch.setattr(
        run_play,
        "geocode_place",
        lambda query, session, user_agent, email, cache: geocode_lookup.get(query),
    )
    monkeypatch.setattr(
        run_play,
        "build_map",
        lambda center_lat, center_lon, places, output_path: Path(output_path).write_text("ok"),
    )

    run_play.main()

    mentions_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_mentions.csv")
    rejections_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_rejections.csv")
    places_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_places.csv")

    assert len(mentions_df) == 3
    assert len(rejections_df) == 2
    assert sorted(rejections_df["mention_text"].tolist()) == ["Friar John", "Italy"]
    assert places_df["normalized_place"].tolist() == ["Verona"]


def test_run_play_infers_span_context_when_extraction_offsets_missing(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    run_play = load_run_play_module(repo_root)

    play_text = (
        "ACT I\nSCENE I.\nROMEO.\nVerona appears here.\n"
        "ACT II\nSCENE I.\nBENVOLIO.\nMantua appears here.\n"
    )

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
    monkeypatch.setattr(
        run_play,
        "extract_places",
        lambda text, model_id: [
            FakeExtractionNoSpan("Verona", "Verona"),
            FakeExtractionNoSpan("Mantua", "Mantua"),
        ],
    )
    monkeypatch.setattr(
        run_play,
        "geocode_place",
        lambda query, session, user_agent, email, cache: {
            "geocode_name": f"{query}, Italy",
            "geocode_lat": 45.0 if query == "Verona" else 45.1,
            "geocode_lon": 10.9 if query == "Verona" else 10.8,
            "geocode_precision": "city",
            "geocode_addresstype": "city",
            "geocode_class": "boundary",
            "geocode_id": f"relation:{query}",
        },
    )
    monkeypatch.setattr(
        run_play,
        "build_map",
        lambda center_lat, center_lon, places, output_path: Path(output_path).write_text("ok"),
    )

    run_play.main()

    mentions_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_mentions.csv")
    verona = mentions_df[mentions_df["normalized_place"] == "Verona"].iloc[0]
    mantua = mentions_df[mentions_df["normalized_place"] == "Mantua"].iloc[0]

    assert int(verona["line"]) == 4
    assert verona["act"] == "ACT I"
    assert verona["scene"] == "SCENE I."
    assert int(mantua["line"]) == 8
    assert mantua["act"] == "ACT II"
    assert mantua["scene"] == "SCENE I."


def test_run_play_skips_scene_instruction_mentions(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    run_play = load_run_play_module(repo_root)

    play_text = "ACT I\nSCENE I. Verona.\nROMEO.\nI travel to Mantua tonight.\n"

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
        start_verona, end_verona = find_span(text, "Verona")
        start_mantua, end_mantua = find_span(text, "Mantua")
        return [
            FakeExtraction("Verona", start_verona, end_verona, "Verona"),
            FakeExtraction("Mantua", start_mantua, end_mantua, "Mantua"),
        ]

    monkeypatch.setattr(run_play, "extract_places", fake_extract_places)
    monkeypatch.setattr(
        run_play,
        "geocode_place",
        lambda query, session, user_agent, email, cache: {
            "geocode_name": f"{query}, Italy",
            "geocode_lat": 45.0 if query == "Verona" else 45.1,
            "geocode_lon": 10.9 if query == "Verona" else 10.8,
            "geocode_precision": "city",
            "geocode_addresstype": "city",
            "geocode_class": "boundary",
            "geocode_id": f"relation:{query}",
        },
    )
    monkeypatch.setattr(
        run_play,
        "build_map",
        lambda center_lat, center_lon, places, output_path: Path(output_path).write_text("ok"),
    )

    run_play.main()

    mentions_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_mentions.csv")
    places_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_places.csv")
    rejections_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_rejections.csv")

    assert mentions_df["normalized_place"].tolist() == ["Mantua"]
    assert places_df["normalized_place"].tolist() == ["Mantua"]
    assert len(rejections_df) == 0


def test_run_play_trims_front_matter_before_context_mapping(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    run_play = load_run_play_module(repo_root)

    play_text = (
        "Contents\nACT V\nScene III. A churchyard.\n"
        "Dramatis Personae\nCHORUS.\nCitizens of Verona.\n\n"
        "THE PROLOGUE\nCHORUS.\nIn fair Verona, where we lay our scene,\n"
    )

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
        start_verona, end_verona = find_span(text, "Verona")
        return [FakeExtraction("Verona", start_verona, end_verona, "Verona")]

    monkeypatch.setattr(run_play, "extract_places", fake_extract_places)
    monkeypatch.setattr(
        run_play,
        "geocode_place",
        lambda query, session, user_agent, email, cache: {
            "geocode_name": "Verona, Veneto, Italy",
            "geocode_lat": 45.4384,
            "geocode_lon": 10.9916,
            "geocode_precision": "city",
            "geocode_addresstype": "city",
            "geocode_class": "boundary",
            "geocode_id": "relation:44874",
        },
    )
    monkeypatch.setattr(
        run_play,
        "build_map",
        lambda center_lat, center_lon, places, output_path: Path(output_path).write_text("ok"),
    )

    run_play.main()

    mentions_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_mentions.csv")
    assert len(mentions_df) == 1
    assert mentions_df.iloc[0]["act"] == "PROLOGUE"
    assert mentions_df.iloc[0]["scene"] == "PROLOGUE"


def test_run_play_rejects_subtoken_spans_like_rome_inside_romeo(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    run_play = load_run_play_module(repo_root)

    play_text = "ACT I\nSCENE I.\nBENVOLIO.\nO Romeo, Romeo, brave Mercutio's dead.\n"

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
        start_rome, end_rome = find_span(text, "Rome")
        start_romeo, end_romeo = find_span(text, "Romeo")
        return [
            FakeExtraction("Rome", start_rome, end_rome, "Rome"),
            FakeExtraction("Romeo", start_romeo, end_romeo, "Romeo", place_granularity="other"),
        ]

    monkeypatch.setattr(run_play, "extract_places", fake_extract_places)
    monkeypatch.setattr(
        run_play,
        "geocode_place",
        lambda query, session, user_agent, email, cache: {
            "geocode_name": "Roma, Roma Capitale, Lazio, Italia",
            "geocode_lat": 41.8933203,
            "geocode_lon": 12.4829321,
            "geocode_precision": "administrative",
            "geocode_addresstype": "city",
            "geocode_class": "boundary",
            "geocode_id": "relation:41485",
        },
    )
    monkeypatch.setattr(
        run_play,
        "build_map",
        lambda center_lat, center_lon, places, output_path: Path(output_path).write_text("ok"),
    )

    run_play.main()

    mentions_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_mentions.csv")
    rejections_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_rejections.csv")
    places_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_places.csv")

    rome_row = mentions_df[mentions_df["mention_text"] == "Rome"].iloc[0]
    assert rome_row["keep"] == False
    assert rome_row["rejected_reason"] == "pre_subtoken_span"
    assert len(places_df) == 0
    assert "pre_subtoken_span" in rejections_df["rejected_reason"].tolist()


def test_run_play_geocode_failure_does_not_flip_semantic_keep(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[1]
    run_play = load_run_play_module(repo_root)

    play_text = "ACT I\nSCENE I.\nROMEO.\nI go to Mantua.\n"

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
    monkeypatch.setattr(
        run_play,
        "extract_places",
        lambda text, model_id: [
            FakeExtraction("Mantua", *find_span(text, "Mantua"), "Mantua"),
        ],
    )
    monkeypatch.setattr(
        run_play,
        "geocode_place",
        lambda query, session, user_agent, email, cache: None,
    )
    monkeypatch.setattr(
        run_play,
        "build_map",
        lambda center_lat, center_lon, places, output_path: Path(output_path).write_text("ok"),
    )

    run_play.main()

    mentions_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_mentions.csv")
    rejections_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_rejections.csv")
    places_df = pd.read_csv(tmp_path / "outputs" / "romeo_juliet_places.csv")

    assert len(mentions_df) == 1
    assert mentions_df.iloc[0]["keep"] == True
    assert mentions_df.iloc[0]["spatial_usable"] == False
    assert mentions_df.iloc[0]["spatial_blocked_reason"] == "geocode_not_found"
    assert len(rejections_df) == 0
    assert len(places_df) == 0
