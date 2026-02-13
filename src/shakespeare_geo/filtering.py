from __future__ import annotations

import re
from typing import Iterable, Optional


SETTLEMENT_GRANULARITIES = {
    "city",
    "town",
    "village",
    "hamlet",
    "municipality",
}

EXCLUDED_GRANULARITIES = {
    "country",
    "region",
    "state",
    "province",
    "continent",
    "landmark",
    "monument",
    "building",
    "address",
    "person",
    "deity",
    "organization",
    "fictional_place",
}

SETTLEMENT_GEOCODE_TYPES = {
    "city",
    "town",
    "village",
    "hamlet",
    "municipality",
    "suburb",
    "borough",
    "quarter",
    "neighbourhood",
    "neighborhood",
}

EXCLUDED_GEOCODE_TYPES = {
    "country",
    "state",
    "region",
    "province",
    "county",
    "continent",
    "island",
    "archipelago",
    "monument",
    "building",
    "church",
    "cemetery",
    "memorial",
    "administrative",
}

PERSON_TITLES = {
    "friar",
    "lord",
    "lady",
    "sir",
    "nurse",
    "father",
    "mother",
    "brother",
    "sister",
    "prince",
    "duke",
    "count",
    "countess",
}

DEITY_TERMS = {
    "god",
    "jesus",
    "christ",
}

_POSSESSIVE_LANDMARK_RE = re.compile(
    r"\b\w+'s\s+(?:monument|tomb|house|vault|church|cell|palace|castle)\b",
    re.IGNORECASE,
)
_TITLE_PERSON_RE = re.compile(
    r"^(?:friar|lord|lady|sir|nurse|father|mother|brother|sister|prince|duke|count|countess)\s+[A-Za-z]",
    re.IGNORECASE,
)
_WS_RE = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return _WS_RE.sub(" ", value.strip().lower())


def parse_bool(value: object) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None

    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def build_character_lexicon(speakers: Iterable[str | None]) -> set[str]:
    lexicon: set[str] = set()
    for speaker in speakers:
        norm = normalize_text(speaker)
        if norm:
            lexicon.add(norm)
    return lexicon


def llm_settlement_rejection_reason(
    entity_kind: str | None,
    place_granularity: str | None,
    is_real_world: object,
    should_keep: object,
) -> str | None:
    should_keep_bool = parse_bool(should_keep)
    if should_keep_bool is False:
        return "llm_marked_reject"

    entity = normalize_text(entity_kind)
    if entity and entity != "place":
        return "llm_not_place"

    real_world = parse_bool(is_real_world)
    if real_world is False:
        return "llm_not_real_world"

    granularity = normalize_text(place_granularity)
    if granularity in EXCLUDED_GRANULARITIES:
        return "llm_not_settlement"
    if granularity and granularity not in SETTLEMENT_GRANULARITIES:
        return "llm_not_settlement"

    return None


def prefilter_rejection_reason(
    mention_text: str | None,
    normalized_place: str | None,
    character_lexicon: set[str],
) -> str | None:
    mention = mention_text or normalized_place or ""
    norm_mention = normalize_text(mention)
    norm_place = normalize_text(normalized_place)

    if not norm_mention and not norm_place:
        return "pre_empty_candidate"

    if norm_mention in character_lexicon or norm_place in character_lexicon:
        return "pre_character_name"

    if norm_mention in DEITY_TERMS or norm_place in DEITY_TERMS:
        return "pre_deity"

    if _TITLE_PERSON_RE.match(mention):
        return "pre_person_title"

    if _POSSESSIVE_LANDMARK_RE.search(mention):
        return "pre_possessive_landmark"

    return None


def postfilter_rejection_reason(
    geocode_class: str | None,
    geocode_type: str | None,
    geocode_addresstype: str | None,
) -> str | None:
    geocode_class_norm = normalize_text(geocode_class)
    geocode_type_norm = normalize_text(geocode_type)
    geocode_addresstype_norm = normalize_text(geocode_addresstype)

    if not geocode_type_norm and not geocode_addresstype_norm:
        return "geocode_missing_type"

    # Allow settlement addresstypes even when type is "administrative"
    # (common for city relations in Nominatim).
    if (
        geocode_type_norm in SETTLEMENT_GEOCODE_TYPES
        or geocode_addresstype_norm in SETTLEMENT_GEOCODE_TYPES
    ):
        return None

    if geocode_class_norm == "place" and geocode_type_norm == "administrative":
        return None

    if (
        geocode_type_norm in EXCLUDED_GEOCODE_TYPES
        or geocode_addresstype_norm in EXCLUDED_GEOCODE_TYPES
    ):
        return "post_not_settlement_type"

    if geocode_class_norm == "place" and geocode_type_norm in SETTLEMENT_GEOCODE_TYPES:
        return None

    return "post_not_settlement_type"
