"""Mode-aware strategy policy for Training, EFC, and Tourney matches."""
from __future__ import annotations

from dataclasses import dataclass
import math
from .engine import Move, State
from .solver import advise

VALID_MODES = ("training", "efc", "tourney")


@dataclass(frozen=True)
class ModeConfig:
    mode: str
    iterations: int
    allow_fury: bool
    fury_min_pillz: int
    fury_prob_threshold: float


MODE_CONFIGS: dict[str, ModeConfig] = {
    "training": ModeConfig(
        mode="training",
        iterations=150,
        allow_fury=True,
        fury_min_pillz=0,
        fury_prob_threshold=0.25,
    ),
    "efc": ModeConfig(
        mode="efc",
        iterations=200,
        allow_fury=True,
        fury_min_pillz=1,
        fury_prob_threshold=0.35,
    ),
    "tourney": ModeConfig(
        mode="tourney",
        iterations=200,
        allow_fury=True,
        fury_min_pillz=0,
        fury_prob_threshold=0.20,
    ),
}


@dataclass(frozen=True)
class Recommendation:
    card_index: int
    card_name: str
    stars: int
    power: int
    damage: int
    pillz: int
    fury: bool
    win_prob: float
    value: float
    mode: str
    reason: str

    def to_dict(self) -> dict:
        return {
            "card_index": self.card_index,
            "card_name": self.card_name,
            "stars": self.stars,
            "power": self.power,
            "damage": self.damage,
            "pillz": self.pillz,
            "fury": self.fury,
            "win_prob": round(self.win_prob, 3),
            "value": round(self.value, 4),
            "mode": self.mode,
            "reason": self.reason,
        }


# engine.evaluate() returns a life/pillz heuristic (about -15..+15) or +/-10000
# when the match is decided; it is not a [-1, 1] score. A logistic squash keeps
# the HUD from pinning at 0%/100%. Rough estimate until whole-match search
# produces real probabilities.
WIN_PROB_SLOPE = 0.35


def value_to_win_prob(value: float) -> float:
    if value >= 1000:
        return 1.0
    if value <= -1000:
        return 0.0
    return 1.0 / (1.0 + math.exp(-WIN_PROB_SLOPE * value))


def recommend_move(
    state: State,
    side: int = 0,
    observed_card: int | None = None,
    mode: str = "training",
    allow_fury: bool | None = None,
) -> Recommendation:
    """Compute the best move for Training, EFC, or Tourney under a fast turn budget."""
    if mode not in MODE_CONFIGS:
        raise ValueError(f"Unsupported mode: {mode!r}; expected one of {VALID_MODES}")
    cfg = MODE_CONFIGS[mode]
    player = state.players[side]
    use_fury = cfg.allow_fury if allow_fury is None else allow_fury
    allow_fury_flag = use_fury and player.pillz >= 3

    advice = advise(
        state,
        side=side,
        observed_card=observed_card,
        iterations=cfg.iterations,
        allow_fury=allow_fury_flag,
    )

    best_idx = max(range(len(advice.moves)), key=lambda i: advice.probabilities[i])
    best_move: Move = advice.moves[best_idx]
    best_prob = advice.probabilities[best_idx]

    # In EFC, avoid spending Fury on low-confidence splits when a non-fury move is close.
    if mode == "efc" and best_move.fury and best_prob < cfg.fury_prob_threshold:
        non_fury = [
            (i, m, advice.probabilities[i])
            for i, m in enumerate(advice.moves)
            if not m.fury and m.card == best_move.card
        ]
        if non_fury:
            alt_i, alt_m, alt_p = max(non_fury, key=lambda item: item[2])
            if alt_p >= best_prob * 0.7:
                best_move = alt_m
                best_prob = alt_p

    card = player.hand[best_move.card]
    stars = card.stars or 1
    win_prob = value_to_win_prob(advice.value)
    fury_label = " + Fury" if best_move.fury else ""
    reason = f"[{mode.upper()}] {card.name} ({stars}★) with {best_move.pillz} Pillz{fury_label}"

    return Recommendation(
        card_index=best_move.card,
        card_name=card.name,
        stars=stars,
        power=card.power,
        damage=card.damage,
        pillz=best_move.pillz,
        fury=best_move.fury,
        win_prob=win_prob,
        value=advice.value,
        mode=mode,
        reason=reason,
    )
