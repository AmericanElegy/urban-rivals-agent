"""Immutable deterministic classic-game core; unsupported effects fail closed.

Pillz in Move are *paid* pillz. The free pill is added only to attack.
Original hands are retained so played cards continue to count for clan bonuses.
"""
from dataclasses import dataclass, replace
import re
from functools import lru_cache


@dataclass(frozen=True)
class Effect:
    stat: str
    amount: int
    opponent: bool = False
    minimum: int = 0
    maximum: int = 10000
    condition: str = "always"
    multiplier: str = "none"

    def __post_init__(self):
        if self.stat not in {"power", "damage", "attack", "life", "pillz", "stop_ability"}:
            raise ValueError(f"Unsupported effect stat: {self.stat}")
        if self.condition not in {"always", "courage", "reprisal", "confidence", "revenge", "defeat", "victory or defeat", "day", "night", "unison", "disunion", "symmetry", "asymmetry"}:
            raise ValueError(f"Unsupported condition: {self.condition}")
        if self.multiplier not in {"none", "support", "brawl", "growth", "degrowth", "equalizer"}:
            raise ValueError(f"Unsupported multiplier: {self.multiplier}")
        if self.minimum < 0 or self.maximum < self.minimum:
            raise ValueError("Invalid effect bounds")


def parse_effect(text: str) -> tuple[Effect, ...]:
    """Parse a deliberately small, auditable subset of English card text."""
    text = text.strip().rstrip(".")
    if text.lower() in ("", "none", "no ability", "no bonus"):
        return ()
    condition, multiplier = "always", "none"
    if ":" in text:
        prefix, text = text.split(":", 1)
        condition = prefix.strip().lower()
        if condition in {"support", "brawl", "growth", "degrowth", "equalizer"}:
            multiplier, condition = condition, "always"
        if condition not in {"always", "courage", "reprisal", "confidence", "revenge", "defeat", "victory or defeat", "day", "night", "unison", "disunion", "symmetry", "asymmetry"}:
            raise ValueError(f"Unsupported condition: {prefix}")
        text = text.strip()
    if re.fullmatch(r"Stop\s+Opp\.?\s+Ability", text, re.I):
        return (Effect("stop_ability", 0, True, condition=condition),)
    patterns = (
        r"(?P<stat>(?:Power|Damage|Attack|Life|Pillz)(?:\s+And\s+(?:Power|Damage|Attack|Life|Pillz))?)\s*(?P<amount>[+-]\s*\d+)",
        r"(?P<amount>[+-]\s*\d+)\s*(?P<opp>Opp\.?\s*)?(?P<stat>(?:Power|Damage|Attack|Life|Pillz)(?:\s+And\s+(?:Power|Damage|Attack|Life|Pillz))?)",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern + r"(?:,?\s*(?P<bound>Min|Max)\.?\s*(?P<limit>\d+))?", text, re.I)
        if match:
            values = match.groupdict()
            stats = re.split(r"\s+and\s+", values["stat"].lower())
            if condition in {"defeat", "victory or defeat"} and any(stat not in {"life", "pillz"} for stat in stats):
                raise ValueError("Post-round conditions require life or pillz effects")
            return tuple(Effect(stat, int(values["amount"].replace(" ", "")),
                           bool(values.get("opp")),
                           int(values["limit"]) if (values["bound"] or "").lower() == "min" else 0,
                           int(values["limit"]) if (values["bound"] or "").lower() == "max" else 10000,
                           condition, multiplier) for stat in stats)
    raise ValueError(f"Unsupported effect: {text!r}")


@dataclass(frozen=True)
class Card:
    name: str
    power: int
    damage: int
    stars: int
    clan: str
    ability: tuple[Effect, ...] = ()
    bonus: tuple[Effect, ...] = ()

    def __post_init__(self):
        if not self.name or not self.clan or not 1 <= self.stars <= 5 or self.power < 1 or self.damage < 0:
            raise ValueError("Invalid card stats")


@dataclass(frozen=True)
class Player:
    hand: tuple[Card, ...]
    life: int = 14
    pillz: int = 12
    used: tuple[int, ...] = ()
    last_won: bool | None = None

    def __post_init__(self):
        if not 1 <= len(self.hand) <= 4 or self.life < 0 or self.pillz < 0:
            raise ValueError("Invalid player resources or hand size")
        if len(set(self.used)) != len(self.used) or any(i not in range(len(self.hand)) for i in self.used):
            raise ValueError("Invalid used-card indices")


@dataclass(frozen=True)
class Move:
    card: int
    pillz: int
    fury: bool = False


@dataclass(frozen=True)
class State:
    players: tuple[Player, Player]
    leader: int = 0
    round: int = 1
    day: bool | None = None

    def __post_init__(self):
        if len(self.players) != 2 or self.leader not in (0, 1) or not 1 <= self.round <= 5:
            raise ValueError("Invalid state")
        if len(self.players[0].hand) != len(self.players[1].hand):
            raise ValueError("Both hands must have equal size")
        for p in self.players:
            if len(p.used) != self.round - 1:
                raise ValueError("Used cards must match the round number")

    @property
    def terminal(self):
        return any(p.life == 0 or len(p.used) == len(p.hand) for p in self.players)


@lru_cache(maxsize=4096)
def legal_moves(state: State, side: int, card: int | None = None) -> tuple[Move, ...]:
    if side not in (0, 1):
        raise ValueError("Side must be 0 or 1")
    if state.terminal:
        return ()
    p = state.players[side]
    return tuple(Move(i, n, fury) for i in range(len(p.hand))
                 if i not in p.used and (card is None or i == card)
                 for fury in (False, True)
                 for n in range(p.pillz - 3 * fury + 1))


def is_legal(state: State, side: int, move: Move) -> bool:
    p = state.players[side]
    return (not state.terminal and type(move.card) is int and type(move.pillz) is int
            and type(move.fury) is bool and 0 <= move.card < len(p.hand)
            and move.card not in p.used and move.pillz >= 0
            and move.pillz + 3 * move.fury <= p.pillz)


def _modify(value: int, e: Effect) -> int:
    # A minimum must never *increase* a value already below it (likewise max).
    if e.amount < 0:
        return min(value, max(e.minimum, value + e.amount))
    return max(value, min(e.maximum, value + e.amount))


def resolve(state: State, first: Move, second: Move) -> State:
    """Resolve indexed side-0 and side-1 moves, independent of leader order."""
    moves = (first, second)
    for side, move in enumerate(moves):
        if not is_legal(state, side, move):
            raise ValueError(f"Illegal move for side {side}: {move}")
    cards = [p.hand[m.card] for p, m in zip(state.players, moves)]
    active = []
    for side, (p, c) in enumerate(zip(state.players, cards)):
        bonus_on = sum(x.clan == c.clan for x in p.hand) >= 2
        effects = c.ability + (c.bonus if bonus_on else ())
        if state.day is None and any(e.condition in {"day", "night"} for e in effects):
            raise ValueError("Day/Night effects require the observed game clock")
        unison = all(x.clan == c.clan for x in p.hand)
        conditions = {"always": True, "courage": side == state.leader,
                      "reprisal": side != state.leader, "confidence": p.last_won is True,
                      "revenge": p.last_won is False, "defeat": True, "victory or defeat": True,
                      "day": state.day is True, "night": state.day is False,
                      "unison": unison, "disunion": not unison,
                      "symmetry": moves[side].card == moves[1-side].card,
                      "asymmetry": moves[side].card != moves[1-side].card}
        multipliers = {"none": 1, "growth": state.round, "degrowth": 5-state.round,
                       "support": sum(x.clan == c.clan for x in p.hand),
                       "brawl": sum(x.clan == cards[1-side].clan for x in state.players[1-side].hand),
                       "equalizer": cards[1-side].stars}
        active.append(tuple(replace(e, amount=e.amount * multipliers[e.multiplier])
                            for e in effects if conditions[e.condition]))
    # Supported Stop Opp. Ability is simultaneous. Stop Opp. Bonus and protection
    # interactions remain rejected by the parser rather than guessed here.
    blocked = [any(e.stat == "stop_ability" for e in active[1-i]) for i in range(2)]
    for side in range(2):
        if blocked[side]:
            bonus_on = sum(x.clan == cards[side].clan for x in state.players[side].hand) >= 2
            # Active effects preserve ability-then-bonus order. Strip precisely
            # the active ability prefix, even when values were multiplied.
            ability_count = sum(1 for e in cards[side].ability
                                if any(a.stat == e.stat and a.condition == e.condition for a in active[side]))
            active[side] = active[side][ability_count:] if bonus_on else ()

    def stat(side, name, initial):
        result = initial
        for owner in (side, 1 - side):
            for e in active[owner]:
                if e.stat == name and (owner != side) == e.opponent:
                    result = _modify(result, e)
        return result

    power = [max(0, stat(i, "power", c.power)) for i, c in enumerate(cards)]
    attack = [max(0, stat(i, "attack", power[i] * (m.pillz + 1))) for i, m in enumerate(moves)]
    winner = max(range(2), key=lambda i: (attack[i], -cards[i].stars, i == state.leader))
    life = [p.life for p in state.players]
    pillz = [p.pillz - m.pillz - 3 * m.fury for p, m in zip(state.players, moves)]
    damage = max(0, stat(winner, "damage", cards[winner].damage + 2 * moves[winner].fury))
    life[1 - winner] = max(0, life[1 - winner] - damage)
    for owner in range(2):
        for e in active[owner]:
            if e.stat not in {"life", "pillz"}:
                continue
            triggered = (owner != winner if e.condition == "defeat" else
                         True if e.condition == "victory or defeat" else owner == winner)
            if triggered:
                target = 1 - owner if e.opponent else owner
                values = life if e.stat == "life" else pillz
                values[target] = max(0, _modify(values[target], e))
    players = tuple(replace(p, life=life[i], pillz=pillz[i], used=p.used + (moves[i].card,),
                            last_won=i == winner) for i, p in enumerate(state.players))
    return State(players, 1 - state.leader, state.round + 1, state.day)


def evaluate(state: State) -> float:
    a, b = state.players
    if state.terminal:
        return float((a.life > b.life) - (a.life < b.life)) * 10000
    # Explicit heuristic at a one-round horizon; not a claimed match win rate.
    reserve = [sum(c.damage for i, c in enumerate(p.hand) if i not in p.used) for p in (a, b)]
    return a.life - b.life + .65 * (a.pillz - b.pillz) + .15 * (reserve[0] - reserve[1])
