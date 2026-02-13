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
from shakespeare_geo.filtering import (
    build_character_lexicon,
    llm_settlement_rejection_reason,
    parse_bool,
    postfilter_rejection_reason,
    prefilter_rejection_reason,
)
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
    character_lexicon = build_character_lexicon(ctx.speaker for ctx in contexts)

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
        entity_kind = attrs.get("entity_kind")
        place_granularity = (
            attrs.get("place_granularity")
            or attrs.get("place_type")
            or attrs.get("normalized_type")
        )
        is_real_world = attrs.get("is_real_world")
        if is_real_world is None and attrs.get("is_fictional") is not None:
            is_fictional = parse_bool(attrs.get("is_fictional"))
            if is_fictional is not None:
                is_real_world = not is_fictional
        should_keep_llm = attrs.get("should_keep")

        llm_rejection_reason = llm_settlement_rejection_reason(
            entity_kind=entity_kind,
            place_granularity=place_granularity,
            is_real_world=is_real_world,
            should_keep=should_keep_llm,
        )

        pre_rejection_reason = None
        if llm_rejection_reason is None:
            pre_rejection_reason = prefilter_rejection_reason(
                mention_text=extraction_text,
                normalized_place=normalized_place,
                character_lexicon=character_lexicon,
            )

        rejection_reason = llm_rejection_reason or pre_rejection_reason
        keep = rejection_reason is None

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
                "entity_kind": entity_kind,
                "place_granularity": place_granularity,
                "is_real_world": is_real_world,
                "should_keep_llm": should_keep_llm,
                "extract_confidence": getattr(extraction, "confidence", None),
                "geocode_query": normalized_place,
                "geocode_name": None,
                "geocode_lat": None,
                "geocode_lon": None,
                "geocode_precision": None,
                "geocode_addresstype": None,
                "geocode_class": None,
                "geocode_id": None,
                "keep": keep,
                "rejected_reason": rejection_reason,
                "source_url": args.gutenberg_url,
                "model_name": args.model,
                "run_id": run_id,
            }
        )

    cache_path = Path("data/geocode_cache.json")
    cache = load_cache(cache_path)

    session = requests.Session()
    geocode_results = {}

    geocode_candidates = sorted(
        {
            m["geocode_query"]
            for m in mentions
            if m.get("keep") is True and m.get("geocode_query")
        }
    )

    for place in geocode_candidates:
        result = geocode_place(
            query=place,
            session=session,
            user_agent=args.user_agent,
            email=args.nominatim_email,
            cache=cache,
        )
        geocode_results[place] = result

    save_cache(cache_path, cache)

    for mention in mentions:
        if mention.get("keep") is not True:
            continue

        result = geocode_results.get(mention.get("geocode_query"))
        if result is None:
            mention["keep"] = False
            mention["rejected_reason"] = "geocode_not_found"
            continue

        mention.update(result)

        post_rejection_reason = postfilter_rejection_reason(
            geocode_class=mention.get("geocode_class"),
            geocode_type=mention.get("geocode_precision"),
            geocode_addresstype=mention.get("geocode_addresstype"),
        )
        if post_rejection_reason is not None:
            mention["keep"] = False
            mention["rejected_reason"] = post_rejection_reason

    mentions_df = pd.DataFrame(mentions)
    kept_mentions_df = mentions_df[mentions_df["keep"] == True].copy()
    rejected_mentions_df = mentions_df[mentions_df["keep"] != True].copy()

    mentions_csv = output_dir / f"{args.play_id}_mentions.csv"
    mentions_df.to_csv(mentions_csv, index=False)

    rejections_csv = output_dir / f"{args.play_id}_rejections.csv"
    rejected_mentions_df.to_csv(rejections_csv, index=False)

    if kept_mentions_df.empty:
        places_df = pd.DataFrame(
            columns=[
                "normalized_place",
                "geocode_name",
                "geocode_lat",
                "geocode_lon",
                "geocode_precision",
                "geocode_addresstype",
                "geocode_class",
                "geocode_id",
                "mention_count",
            ]
        )
    else:
        group_key = kept_mentions_df["geocode_id"].fillna(kept_mentions_df["normalized_place"])
        places_df = (
            kept_mentions_df.assign(group_key=group_key)
            .groupby("group_key", dropna=False)
            .agg(
                normalized_place=("normalized_place", "first"),
                geocode_name=("geocode_name", "first"),
                geocode_lat=("geocode_lat", "first"),
                geocode_lon=("geocode_lon", "first"),
                geocode_precision=("geocode_precision", "first"),
                geocode_addresstype=("geocode_addresstype", "first"),
                geocode_class=("geocode_class", "first"),
                geocode_id=("geocode_id", "first"),
                mention_count=("mention_text", "count"),
            )
            .reset_index(drop=True)
        )

    places_csv = output_dir / f"{args.play_id}_places.csv"
    places_df.to_csv(places_csv, index=False)

    cog_lat, cog_lon = center_of_gravity(
        kept_mentions_df.assign(weight=1.0).to_dict(orient="records")
    )

    map_path = output_dir / f"{args.play_id}_map.html"
    build_map(cog_lat, cog_lon, places_df.to_dict(orient="records"), str(map_path))

    print(f"Mentions:   {mentions_csv}")
    print(f"Rejections: {rejections_csv}")
    print(f"Places:     {places_csv}")
    print(f"Map:        {map_path}")
    print(f"Kept:       {len(kept_mentions_df)}")
    print(f"Rejected:   {len(rejected_mentions_df)}")
    print(f"CoG:        {cog_lat:.4f}, {cog_lon:.4f}")


if __name__ == "__main__":
    main()
