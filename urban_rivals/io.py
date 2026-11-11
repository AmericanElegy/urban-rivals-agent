"""Strict JSON state loading; source card text is never executable code."""
import json
from pathlib import Path
from .engine import Card, Player, State, parse_effect


def load_state(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return state_from_dict(data)


def state_from_dict(data):
    players = []
    for raw in data["players"]:
        cards = []
        for card in raw["hand"]:
            card = dict(card)
            for key in ("ability", "bonus"):
                card[key] = parse_effect(card.get(key, ""))
            cards.append(Card(**card))
        players.append(Player(tuple(cards), raw.get("life", 14), raw.get("pillz", 12),
                              tuple(raw.get("used", ())), raw.get("last_won")))
    return State(tuple(players), data.get("leader", 0), data.get("round", 1), data.get("day"))
