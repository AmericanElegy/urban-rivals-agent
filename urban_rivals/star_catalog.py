"""Full per-star-level card catalog built from official_evolution_pages.

Accounts for every character's stats, clan bonus, and ability at each star
level (1..max_stars), including characters that unlock or change abilities
before their maximum star level. Falls back gracefully to a neutral Card
wrapper when an ability uses mechanics not yet modeled by engine.parse_effect.
"""
from __future__ import annotations

from dataclasses import dataclass
import difflib
import json
from pathlib import Path
import re
import unicodedata

from .engine import Card, Effect, parse_effect


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return re.sub(r"[^a-z0-9]", "", text)


def _safe_parse_effects(text: str) -> tuple[tuple[Effect, ...], bool]:
    """Return (effects, fully_parsed). Never raises on unmodeled card text."""
    cleaned = (text or "").strip()
    if not cleaned or cleaned.lower() in {"none", "no ability", "no bonus", "-"}:
        return (), True
    try:
        return parse_effect(cleaned), True
    except ValueError:
        return (), False


@dataclass(frozen=True)
class StarEvolution:
    name: str
    norm_name: str
    level: int
    max_level: int
    power: int
    damage: int
    clan: str
    ability_text: str
    bonus_text: str
    ability_unlock_level: int | None
    ability_unlocked: bool
    ability_parsed: bool
    bonus_parsed: bool
    card: Card


class StarCatalog:
    """Per-star-level catalog covering all 2,507+ official Urban Rivals cards."""

    def __init__(self, reference_path: str | Path | None = None):
        path = (
            Path(reference_path)
            if reference_path is not None
            else Path(__file__).resolve().parent / "data" / "card_reference.json"
        )
        raw = json.loads(path.read_text(encoding="utf-8"))
        pages = raw.get("official_evolution_pages", [])
        self._by_name: dict[str, list[StarEvolution]] = {}
        self._by_name_level: dict[tuple[str, int], StarEvolution] = {}

        for page in pages:
            levels = page.get("levels") or []
            if not levels:
                continue
            max_level = max(int(lvl.get("level", 1)) for lvl in levels)
            for lvl in levels:
                name = str(lvl.get("name", "")).strip()
                if not name:
                    continue
                norm = _normalize(name)
                level = int(lvl["level"])
                power = int(lvl["power"])
                damage = int(lvl["damage"])
                clan = str(lvl.get("clan", "")).strip()
                raw_ability = str(lvl.get("ability") or "").strip()
                bonus_text = str(lvl.get("bonus") or "").strip()
                unlock_lvl = lvl.get("ability_unlock_level")
                if unlock_lvl is not None:
                    unlock_lvl = int(unlock_lvl)

                # An ability is active at this star level if it has text and
                # either no unlock_level is specified or level >= unlock_level.
                ability_unlocked = bool(
                    raw_ability
                    and raw_ability.lower() not in {"none", "no ability", "-"}
                    and (unlock_lvl is None or level >= unlock_lvl)
                )
                active_ability_text = raw_ability if ability_unlocked else ""
                from .descriptions import annotate
                ability_effects, ability_parsed = _safe_parse_effects(annotate(name, active_ability_text))
                bonus_effects, bonus_parsed = _safe_parse_effects(annotate(name, bonus_text))

                card = Card(
                    name=name,
                    power=power,
                    damage=damage,
                    clan=clan,
                    ability=ability_effects,
                    bonus=bonus_effects,
                    stars=level,
                )
                evo = StarEvolution(
                    name=name,
                    norm_name=norm,
                    level=level,
                    max_level=max_level,
                    power=power,
                    damage=damage,
                    clan=clan,
                    ability_text=active_ability_text,
                    bonus_text=bonus_text,
                    ability_unlock_level=unlock_lvl,
                    ability_unlocked=ability_unlocked,
                    ability_parsed=ability_parsed,
                    bonus_parsed=bonus_parsed,
                    card=card,
                )
                self._by_name.setdefault(norm, []).append(evo)
                self._by_name_level[(norm, level)] = evo

        for norm, evos in self._by_name.items():
            evos.sort(key=lambda e: e.level)

    def __len__(self) -> int:
        return len(self._by_name)

    def evolutions(self, name: str) -> list[StarEvolution]:
        return list(self._by_name.get(_normalize(name), ()))

    def resolve(
        self,
        name: str,
        stars: int | None = None,
        power: int | None = None,
        damage: int | None = None,
    ) -> StarEvolution | None:
        """Resolve exact active star level using stars and/or (power, damage)."""
        norm = _normalize(name)
        evos = self._by_name.get(norm)
        if not evos and norm:
            # Handle OCR confusions like 0/O (X-ODUS -> X-0DUS), 1/I/l, etc.
            close = difflib.get_close_matches(norm, self._by_name.keys(), n=5, cutoff=0.78)
            for cand_norm in close:
                cand_evos = self._by_name[cand_norm]
                if power is not None and damage is not None:
                    if any(e.power == power and e.damage == damage for e in cand_evos):
                        norm = cand_norm
                        evos = cand_evos
                        break
            if not evos and close:
                norm = close[0]
                evos = self._by_name[norm]
        if not evos:
            return None

        # 1. Exact star level match (cross-checked with stats if provided).
        if stars is not None and (norm, stars) in self._by_name_level:
            cand = self._by_name_level[(norm, stars)]
            if (power is None or cand.power == power) and (damage is None or cand.damage == damage):
                return cand

        # 2. Match by (power, damage) if star count was misread or omitted.
        if power is not None and damage is not None:
            stat_matches = [e for e in evos if e.power == power and e.damage == damage]
            if len(stat_matches) == 1:
                return stat_matches[0]
            if stat_matches:
                # If multiple levels share identical base stats, prefer closest to read stars or max.
                if stars is not None:
                    return min(stat_matches, key=lambda e: abs(e.level - stars))
                return stat_matches[-1]

        # 3. Fallback to star level even if OCR stat had a transient mismatch.
        if stars is not None and (norm, stars) in self._by_name_level:
            return self._by_name_level[(norm, stars)]

        # 4. Default to max star level if only the card name was read.
        return evos[-1]
