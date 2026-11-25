"""Official per-card ability descriptions (data/card_reference.json).

Some card texts leave out facts the official description states, such as
which clans an "After"/"Versus" condition names. annotate() writes those into
the text so the parser can model them.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from .engine import annotate_text


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", (text or "").casefold())
    return re.sub(r"[^a-z0-9]", "", text)


@lru_cache(maxsize=1)
def _index() -> dict[tuple[str, str], str]:
    path = Path(__file__).parent / "data" / "card_reference.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    index: dict[tuple[str, str], str] = {}
    for page in data.get("official_evolution_pages", []):
        names = {_norm(level.get("name", "")) for level in page.get("levels") or []}
        for entry in page.get("descriptions") or []:
            title = _norm(entry.get("title", ""))
            for name in names:
                index.setdefault((name, title), entry.get("description") or "")
            index.setdefault(("*", title), entry.get("description") or "")
    return index


def description(name: str, text: str) -> str:
    index = _index()
    return index.get((_norm(name), _norm(text))) or index.get(("*", _norm(text)), "")


def annotate(name: str, text: str) -> str:
    """Card text with clan lists from its official description, if any."""
    if not text or "[" in text:
        return text
    return annotate_text(text, description(name, text))
