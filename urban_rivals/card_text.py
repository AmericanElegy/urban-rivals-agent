"""Make official card text self-contained before parsing.

Printed abilities such as ``Versus : Power +2`` or Oculus abilities omit the
clan icons that decide them. The official per-card descriptions spell those
clans out; this module inlines them (``Versus(Leader|Oculus): Power +2``) and
pairs Day/Night variants, so the engine never guesses a hidden clan list.
"""
from functools import lru_cache
import json
from pathlib import Path
import re


@lru_cache(maxsize=1)
def _reference():
    path = Path(__file__).parent / "data" / "card_reference.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=1)
def _pages():
    return {p["url"]: p for p in _reference().get("official_evolution_pages", [])}


def _clan_list(raw):
    parts = re.split(r",\s*|\s+or\s+|\s+and\s+|\s*&\s*", raw.strip())
    return tuple(p.strip() for p in parts if p.strip())


_PATTERNS = {
    "versus": re.compile(r"if there's an? (.+?) in your opponent's hand", re.I),
    "after": re.compile(r"played an? (.+?) character in the previous round", re.I),
    "infiltrates": re.compile(r"only activates if .+? infiltrates (.+?)\.", re.I),
}


@lru_cache(maxsize=8192)
def clan_lists(url, field="ability"):
    """Clan lists named by a card's official descriptions, by condition kind.

    Bonus lists come only from the clan-bonus description and ability lists
    only from the others, so one never supplies the other's clans.
    """
    page = _pages().get(url) or {}
    found = {}
    for description in page.get("descriptions", []):
        if (description.get("kind") == "Clan Bonus") != (field == "bonus"):
            continue
        text = description.get("description", "")
        for kind, pattern in _PATTERNS.items():
            match = pattern.search(text)
            if match:
                clans = _clan_list(match[1])
                if found.get(kind, clans) != clans:
                    found[kind] = None  # contradictory descriptions: fail closed
                elif clans:
                    found[kind] = clans
    return {k: v for k, v in found.items() if v}


def _inline(text, kind, clans):
    label = kind.title() + "(" + "|".join(clans) + "):"
    return re.sub(r"\b" + kind + r"\s*:", label, text, flags=re.I)


def annotate(text, clan, url, field):
    """Return parser-ready official text for one ability or bonus."""
    text = (text or "").strip()
    if not text or " / " in text:
        return text
    reference = _reference()
    if field == "bonus":
        variants = reference.get("conditional_bonuses", {}).get(clan, {})
        if set(variants) == {"day", "night"} and re.match(r"(Day|Night)\s*:", text, re.I):
            return variants["day"]["text"] + " / " + variants["night"]["text"]
        lists = clan_lists(url, "bonus") if url else {}
        if "after" in lists:
            text = _inline(text, "after", lists["after"])
        return text
    variants = reference.get("conditional_abilities", {}).get(url, {})
    parts = [text]
    if set(variants) == {"day", "night"} and text in variants.values():
        parts = [variants["day"], variants["night"]]
    lists = clan_lists(url, "ability") if url else {}
    out = []
    for part in parts:
        for kind in ("versus", "after"):
            if kind in lists:
                part = _inline(part, kind, lists[kind])
        if (clan == "Oculus" and part.lower() not in {"no ability", "none"}
                and not part.startswith("Infiltrates(")):
            # Every Oculus ability depends on the clans it infiltrates. Without
            # the official list the empty gate is rejected by the parser.
            part = "Infiltrates(" + "|".join(lists.get("infiltrates", ())) + "): " + part
        out.append(part)
    return " / ".join(out)
