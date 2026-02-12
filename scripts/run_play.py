from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from shakespeare_geo.aggregate import center_of_gravity
from shakespeare_geo.config import DEFAULT_GUTENBERG_URL, DEFAULT_MODEL, DEFAULT_USER_AGENT
from shakespeare_geo.extract import extract_places
from shakespeare_geo.geocode import geocode_place, load_cache, save_cache
from shakespeare_geo.gutenberg import fetch_gutenberg_text, strip_gutenberg_header_footer
from shakespeare_geo.map import build_map
from shakespeare_geo.parser import find_context_for_span, index_text_lines


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract and map placenames from a play.")
    parser.add_argument("--play-id", required=True, help="Short identifier, e.g. romeo_juliet")
    parser.add_argument("--title", required=True, help="Display title for the play")
    parser.add_argument("--gutenberg-url", default=DEFAULT_GUTENBERG_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    parser.add_argument("--nominatim-email", default=os.environ.get("NOMINATIM_EMAIL"))
    parser.add_argument("--output-dir", default="outputs")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    if "you@example.com" in args.user_agent and not args.nominatim_email:
        raise ValueError(
            "Set a real --user-agent and/or NOMINATIM_EMAIL for Nominatim requests."
        )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    play_path = Path("data/plays") / f"{args.play_id}.txt"
    play_path.parent.mkdir(parents=True, exist_ok=True)

    if play_path.exists():
        text = play_path.read_text()
    else:
        raw = fetch_gutenberg_text(args.gutenberg_url)
        text = strip_gutenberg_header_footer(raw)
        play_path.write_text(text)

    contexts = index_text_lines(text)

    extractions = extract_places(text=text, model_id=args.model)

    mentions = []
    for extraction in extractions:
        attrs = extraction.attributes or {}
        extraction_text = getattr(extraction, "extraction_text", None) or getattr(
            extraction, "text", None
        )
        span_start = getattr(extraction, "char_start", None) or getattr(
            extraction, "start", None
        )
        span_end = getattr(extraction, "char_end", None) or getattr(
            extraction, "end", None
        )
        normalized_place = attrs.get("normalized_place") or extraction_text
        normalized_type = attrs.get("place_type") or attrs.get("normalized_type")
        is_fictional = attrs.get("is_fictional")

        ctx = find_context_for_span(contexts, span_start or 0)

        mentions.append(
            {
                "play_id": args.play_id,
                "play_title": args.title,
                "act": ctx.act if ctx else None,
                "scene": ctx.scene if ctx else None,
                "line": ctx.line_no if ctx else None,
                "speaker": ctx.speaker if ctx else None,
                "mention_text": extraction_text,
                "span_start": span_start,
                "span_end": span_end,
                "normalized_place": normalized_place,
                "normalized_type": normalized_type,
                "is_fictional": is_fictional,
                "extract_confidence": getattr(extraction, "confidence", None),
                "geocode_query": normalized_place,
                "source_url": args.gutenberg_url,
                "model_name": args.model,
                "run_id": run_id,
            }
        )

    mentions_df = pd.DataFrame(mentions)

    cache_path = Path("data/geocode_cache.json")
    cache = load_cache(cache_path)

    session = requests.Session()
    geocode_results = {}

    for place in sorted(mentions_df["geocode_query"].dropna().unique()):
        result = geocode_place(
            query=place,
            session=session,
            user_agent=args.user_agent,
            email=args.nominatim_email,
            cache=cache,
        )
        geocode_results[place] = result

    save_cache(cache_path, cache)

    for place, result in geocode_results.items():
        if result is None:
            continue
        mask = mentions_df["geocode_query"] == place
        for key, value in result.items():
            mentions_df.loc[mask, key] = value

    mentions_csv = output_dir / f"{args.play_id}_mentions.csv"
    mentions_df.to_csv(mentions_csv, index=False)

    group_key = mentions_df["geocode_id"].fillna(mentions_df["normalized_place"])
    places_df = (
        mentions_df.assign(group_key=group_key)
        .groupby("group_key", dropna=False)
        .agg(
            normalized_place=("normalized_place", "first"),
            geocode_name=("geocode_name", "first"),
            geocode_lat=("geocode_lat", "first"),
            geocode_lon=("geocode_lon", "first"),
            geocode_precision=("geocode_precision", "first"),
            geocode_class=("geocode_class", "first"),
            geocode_id=("geocode_id", "first"),
            mention_count=("mention_text", "count"),
        )
        .reset_index(drop=True)
    )

    places_csv = output_dir / f"{args.play_id}_places.csv"
    places_df.to_csv(places_csv, index=False)

    cog_lat, cog_lon = center_of_gravity(
        mentions_df.assign(weight=1.0).to_dict(orient="records")
    )

    map_path = output_dir / f"{args.play_id}_map.html"
    build_map(cog_lat, cog_lon, places_df.to_dict(orient="records"), str(map_path))

    print(f"Mentions: {mentions_csv}")
    print(f"Places:   {places_csv}")
    print(f"Map:      {map_path}")
    print(f"CoG:      {cog_lat:.4f}, {cog_lon:.4f}")


if __name__ == "__main__":
    main()
