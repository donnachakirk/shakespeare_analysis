from __future__ import annotations

import re
import requests


_DRAMATIS_RE = re.compile(r"^dramatis person", re.IGNORECASE)
_PROLOGUE_RE = re.compile(r"^(?:the\s+)?prologue\b", re.IGNORECASE)
_ACT_I_RE = re.compile(r"^act\s+i\b", re.IGNORECASE)


def fetch_gutenberg_text(url: str, timeout_s: int = 30) -> str:
    response = requests.get(url, timeout=timeout_s)
    response.raise_for_status()
    return response.text


def trim_play_front_matter(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return text

    start_candidates = []
    prologue_indices = []
    act_i_indices = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if _PROLOGUE_RE.match(stripped):
            prologue_indices.append(i)
            start_candidates.append(i)
        elif _ACT_I_RE.match(stripped):
            act_i_indices.append(i)
            start_candidates.append(i)

    if not start_candidates:
        return text.strip()

    dramatis_idx = next(
        (i for i, line in enumerate(lines) if _DRAMATIS_RE.match(line.strip())),
        None,
    )
    if dramatis_idx is not None:
        after_dramatis = [i for i in start_candidates if i > dramatis_idx]
        if after_dramatis:
            return "\n".join(lines[min(after_dramatis) :]).strip()

    if len(act_i_indices) >= 2:
        second_act_i = act_i_indices[1]
        prologues_before = [i for i in prologue_indices if i < second_act_i]
        start_idx = max(prologues_before) if prologues_before else second_act_i
        return "\n".join(lines[start_idx:]).strip()

    return "\n".join(lines[start_candidates[0] :]).strip()


def strip_gutenberg_header_footer(text: str) -> str:
    lines = text.splitlines()
    start_idx = None
    end_idx = None

    for i, line in enumerate(lines):
        if line.startswith("*** START OF"):
            start_idx = i + 1
            break

    for i, line in enumerate(lines):
        if line.startswith("*** END OF"):
            end_idx = i
            break

    if start_idx is None or end_idx is None or start_idx >= end_idx:
        return text

    body = "\n".join(lines[start_idx:end_idx]).strip()
    return trim_play_front_matter(body)
