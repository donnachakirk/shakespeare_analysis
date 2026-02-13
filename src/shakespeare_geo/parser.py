from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List


_ACT_RE = re.compile(r"^ACT\s+[IVX]+\b", re.IGNORECASE)
_SCENE_RE = re.compile(r"^SCENE\s+[IVX]+\b", re.IGNORECASE)
_PROLOGUE_RE = re.compile(r"^(?:THE\s+)?PROLOGUE\b", re.IGNORECASE)
_SPEAKER_RE = re.compile(r"^[A-Z][A-Z\s'\-]+\.$")
_STAGE_DIRECTION_RE = re.compile(
    r"^(?:\[_?.*|_?\[.*|enter\b|exit\b|exeunt\b|re-enter\b|flourish\b|alarum\b)",
    re.IGNORECASE,
)
_WS_RE = re.compile(r"\s+")


@dataclass
class LineContext:
    line_no: int
    start: int
    end: int
    text: str
    act: str | None
    scene: str | None
    speaker: str | None
    is_dialogue: bool


def index_text_lines(text: str) -> List[LineContext]:
    contexts: List[LineContext] = []
    act = None
    scene = None
    speaker = None
    in_play_body = False

    offset = 0
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        is_act = bool(_ACT_RE.match(stripped))
        is_scene = bool(_SCENE_RE.match(stripped))
        is_prologue = bool(_PROLOGUE_RE.match(stripped))
        is_speaker = bool(_SPEAKER_RE.match(stripped))
        is_stage_direction = bool(_STAGE_DIRECTION_RE.match(stripped))

        if is_act:
            act = stripped
            scene = None
            speaker = None
            in_play_body = True
        elif is_prologue:
            act = "PROLOGUE"
            scene = "PROLOGUE"
            speaker = None
            in_play_body = True
        elif is_scene:
            scene = stripped
            speaker = None
        elif is_speaker:
            speaker = stripped.rstrip(".")

        is_dialogue = (
            in_play_body
            and bool(stripped)
            and bool(speaker)
            and not is_act
            and not is_scene
            and not is_prologue
            and not is_speaker
            and not is_stage_direction
        )

        start = offset
        end = start + len(line)
        contexts.append(
            LineContext(
                line_no=line_no,
                start=start,
                end=end,
                text=line,
                act=act,
                scene=scene,
                speaker=speaker,
                is_dialogue=is_dialogue,
            )
        )
        offset = end + 1  # account for newline

    return contexts


def find_context_for_span(contexts: List[LineContext], span_start: int) -> LineContext | None:
    # Simple linear scan; OK for a single play.
    for ctx in contexts:
        if ctx.start <= span_start <= ctx.end:
            return ctx
    return None


def find_span_for_text(
    text: str,
    candidate_text: str | None,
    start_at: int = 0,
) -> tuple[int | None, int | None, int]:
    candidate = (candidate_text or "").strip()
    if not candidate:
        return None, None, max(start_at, 0)

    clamped_start = min(max(start_at, 0), len(text))
    idx = text.find(candidate, clamped_start)
    if idx < 0 and clamped_start > 0:
        idx = text.find(candidate)
    if idx < 0:
        return None, None, clamped_start

    end = idx + len(candidate)
    return idx, end, end


def extract_sentence_for_span(
    text: str,
    span_start: int | None,
    span_end: int | None,
) -> str | None:
    if span_start is None:
        return None
    if not text:
        return None

    start = min(max(span_start, 0), max(len(text) - 1, 0))
    end = start if span_end is None else min(max(span_end, start), len(text))

    left_punct = max(text.rfind(".", 0, start), text.rfind("?", 0, start), text.rfind("!", 0, start))
    left_newline = text.rfind("\n", 0, start)
    left = max(left_punct, left_newline)
    left = 0 if left < 0 else left + 1

    right_candidates = [text.find(".", end), text.find("?", end), text.find("!", end)]
    right_punct = min((pos for pos in right_candidates if pos >= 0), default=-1)
    right_newline = text.find("\n", end)
    if right_punct >= 0 and right_newline >= 0:
        right = min(right_punct, right_newline)
    elif right_punct >= 0:
        right = right_punct
    elif right_newline >= 0:
        right = right_newline
    else:
        right = len(text)

    raw = text[left:right]
    sentence = _WS_RE.sub(" ", raw).strip()
    return sentence or None
