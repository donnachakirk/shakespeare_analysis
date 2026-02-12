from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List


_ACT_RE = re.compile(r"^ACT\s+[IVX]+\b", re.IGNORECASE)
_SCENE_RE = re.compile(r"^SCENE\s+[IVX]+\b", re.IGNORECASE)
_SPEAKER_RE = re.compile(r"^[A-Z][A-Z\s'\-]+\.$")


@dataclass
class LineContext:
    line_no: int
    start: int
    end: int
    text: str
    act: str | None
    scene: str | None
    speaker: str | None


def index_text_lines(text: str) -> List[LineContext]:
    contexts: List[LineContext] = []
    act = None
    scene = None
    speaker = None

    offset = 0
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if _ACT_RE.match(stripped):
            act = stripped
        elif _SCENE_RE.match(stripped):
            scene = stripped
        elif _SPEAKER_RE.match(stripped):
            speaker = stripped.rstrip(".")

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
