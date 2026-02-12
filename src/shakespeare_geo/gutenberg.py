from __future__ import annotations

import re
import requests


def fetch_gutenberg_text(url: str, timeout_s: int = 30) -> str:
    response = requests.get(url, timeout=timeout_s)
    response.raise_for_status()
    return response.text


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

    body = "\n".join(lines[start_idx:end_idx])
    return body.strip()
