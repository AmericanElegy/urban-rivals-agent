"""Immutable deterministic classic-game core; unsupported effects fail closed.

Pillz in Move are *paid* pillz. The free pill is added only to attack.
Original hands are retained so played cards continue to count for clan bonuses.
"""
from dataclasses import dataclass, replace
import re
from functools import lru_cache

ENGINE_REVISION="copy-v1"


@dataclass(frozen=True)
class Effect:
    stat: str
    amount: int
    opponent: bool = False
    minimum: int = 0
    maximum: int = 10000
    condition: str = "always"
    multiplier: str = "none"
    threshold: int = 0

    def __post_init__(self):
        if self.stat not in {"power", "damage", "attack", "life", "pillz", "stop_ability",
                             "protect_power", "protect_damage", "exchange_power", "exchange_damage", "tune_out", "stop_bonus", "cancel_power", "cancel_damage", "copy_ability"}:
            raise ValueError(f"Unsupported effect stat: {self.stat}")
        if self.condition not in {"always", "courage", "reprisal", "confidence", "revenge", "defeat", "victory or defeat", "day", "night", "unison", "disunion", "symmetry", "asymmetry", "bet_over", "bet_under"}:
            raise ValueError(f"Unsupported condition: {self.condition}")
        if self.multiplier not in {"none", "support", "brawl", "growth", "degrowth", "equalizer", "opp_power", "opp_damage"}:
            raise ValueError(f"Unsupported multiplier: {self.multiplier}")
        if self.minimum < 0 or self.maximum < self.minimum:
            raise ValueError("Invalid effect bounds")
        if type(self.threshold) is not int or self.threshold < 0 or (
                self.condition not in {"bet_over", "bet_under"} and self.threshold != 0):
            raise ValueError("Invalid Bet threshold")
        if self.stat.startswith(("protect_", "exchange_", "cancel_")) and (
                self.amount != 0 or self.opponent or self.multiplier != "none"
                or self.condition in {"defeat", "victory or defeat"}):
            raise ValueError("Unsupported protection/exchange/cancel parameters")


def parse_effect(text: str) -> tuple[Effect, ...]:
    """Parse a deliberately small, auditable subset of English card text."""
    text = text.strip().rstrip(".")
    if text.lower() in ("", "none", "no ability", "no bonus"):
        return ()
    condition, multiplier, threshold = "always", "none", 0
    if ":" in text:
        prefix, remainder = text.split(":", 1)
        condition = prefix.strip().lower()
        bet = re.fullmatch(r"Bet\s*([<>])\s*(\d+)\s*Pillz", prefix.strip(), re.I)
        if bet:
            condition = "bet_over" if bet[1] == ">" else "bet_under"
            threshold = int(bet[2])
        # Protection's colon belongs to the mechanic, not a condition.
        if condition in {"protection", "copy"}:
            condition = "always"
        else:
            text = remainder
        if condition in {"support", "brawl", "growth", "degrowth", "equalizer"}:
            multiplier, condition = condition, "always"
        if condition not in {"always", "courage", "reprisal", "confidence", "revenge", "defeat", "victory or defeat", "day", "night", "unison", "disunion", "symmetry", "asymmetry", "bet_over", "bet_under"}:
            raise ValueError(f"Unsupported condition: {prefix}")
        text = text.strip()
    if re.fullmatch(r"Copy:\s*Opp\.?\s+Ability", text, re.I) and condition=="always":
        return (Effect("copy_ability",0),)
    match = re.fullmatch(r"Cancel\s+Opp\.?\s+(Power|Damage)\s+Modif", text, re.I)
    if match:
        return (Effect("cancel_"+match[1].lower(),0,condition=condition,threshold=threshold),)
    if re.fullmatch(r"Stop\s+Opp\.?\s+Bonus", text, re.I):
        return (Effect("stop_bonus",0,True,condition=condition,threshold=threshold),)
    match = re.fullmatch(r"([+]\d+)\s+Attack\s+Per\s+Opp\.?\s+(Power|Damage)",text,re.I)
    if match:
        return (Effect("attack",int(match[1]),condition=condition,
                       multiplier="opp_"+match[2].lower(),threshold=threshold),)
    match = re.fullmatch(r"Protection:\s*(Power|Damage|Power\s+And\s+Damage)", text, re.I)
    if match:
        if multiplier != "none":
            raise ValueError("Protection does not support numeric multipliers")
        return tuple(Effect("protect_" + stat, 0, condition=condition, threshold=threshold)
                     for stat in re.split(r"\s+and\s+", match[1].lower()))
    match = re.fullmatch(r"(Power|Damage|Power\s+And\s+Damage)\s+Exchange", text, re.I)
    if match:
        if multiplier != "none":
            raise ValueError("Exchange does not support numeric multipliers")
        return tuple(Effect("exchange_" + stat, 0, condition=condition, threshold=threshold)
                     for stat in re.split(r"\s+and\s+", match[1].lower()))
    if re.fullmatch(r"Stop\s+Opp\.?\s+Ability", text, re.I):
        return (Effect("stop_ability", 0, True, condition=condition, threshold=threshold),)
    if re.fullmatch(r"Tune\s+Out", text, re.I) and condition == "always":
        return (Effect("tune_out", 0),)
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
                           condition, multiplier, threshold) for stat in stats)
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
    # Expand from the original opposing ability, before checking conditions.
    # The replacement retains the copying source (ability or bonus); conditions
    # and multipliers are evaluated from the copier's side, never the donor's.
    sources=[]
    for side,c in enumerate(cards):
        other=cards[1-side]
        def expand(row):
            result=[]
            for e in row:
                if e.stat!="copy_ability":
                    result.append(e)
                    continue
                if (e.amount,e.condition,e.multiplier,e.opponent)!=(0,"always","none",False):
                    raise ValueError("Conditional or modified ability-copy is not verified")
                if other.clan.casefold() in {"leader","genesis"}:
                    continue
                if any(x.stat=="copy_ability" for x in other.ability):
                    raise ValueError("Recursive ability-copy is not verified")
                result.extend(other.ability)
            return tuple(result)
        bonus_on=sum(x.clan==c.clan for x in state.players[side].hand)>=2
        sources.append((expand(c.ability),expand(c.bonus) if bonus_on else ()))
    active = []
    ability_sizes = []
    for side, (p, c) in enumerate(zip(state.players, cards)):
        ability,bonus=sources[side]
        effects = ability + bonus
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
                       "equalizer": cards[1-side].stars,
                       "opp_power": cards[1-side].power, "opp_damage": cards[1-side].damage}
        def enabled(e):
            # Bets count the attack allocation plus its free pill, not Fury's
            # separate three-pill cost or the player's remaining reserve.
            if e.condition == "bet_over":
                return moves[side].pillz + 1 > e.threshold
            if e.condition == "bet_under":
                return moves[side].pillz + 1 < e.threshold
            return conditions[e.condition]
        active.append(tuple(replace(e, amount=e.amount * multipliers[e.multiplier])
                            for e in effects if enabled(e)))
        ability_sizes.append(sum(enabled(e) for e in ability))
    # Retain source identity while resolving stops. Opposing ability/bonus
    # stop cycles need an observed precedence rule; do not silently choose one.
    for side in range(2):
        if (any(e.stat=="stop_ability" for e in active[side][ability_sizes[side]:])
                and any(e.stat=="stop_bonus" for e in active[1-side][:ability_sizes[1-side]])):
            raise ValueError("Cross-source Stop Ability/Bonus precedence is not yet verified")
    blocked = [any(e.stat == "stop_ability" for e in active[1-i]) for i in range(2)]
    abilities=[active[i][:ability_sizes[i]] if not blocked[i] else () for i in range(2)]
    bonuses=[active[i][ability_sizes[i]:] for i in range(2)]
    bonus_blocked=[any(e.stat=="stop_bonus" for e in abilities[1-i]+bonuses[1-i]) for i in range(2)]
    active=[abilities[i]+(() if bonus_blocked[i] else bonuses[i]) for i in range(2)]
    # Cancel removes the opposing card's modifiers of this type, irrespective
    # of their source or which card those modifiers would target.
    cancelled=[{name for name in ("power","damage")
                if any(e.stat=="cancel_"+name for e in active[1-i])} for i in range(2)]
    active=[tuple(e for e in row if e.stat not in cancelled[i]
                  and not (e.stat.startswith("exchange_") and e.stat[9:] in cancelled[i]))
            for i,row in enumerate(active)]

    def stat(side, name, initial):
        result = initial
        protected = any(e.stat == "protect_" + name for e in active[side])
        for owner in (side, 1 - side):
            for e in active[owner]:
                if e.stat == name and (owner != side) == e.opponent:
                    if protected and e.amount < 0:
                        continue
                    result = _modify(result, e)
        return result

    bases = {}
    for name in ("power", "damage"):
        exchanging = [any(e.stat == "exchange_" + name for e in row) for row in active]
        if all(exchanging):
            raise ValueError(f"Simultaneous {name} Exchange is not yet verified")
        values = [getattr(c, name) for c in cards]
        # Exchange changes starting values, bypasses Protection, and precedes
        # ordinary modifiers and Fury. Each round starts from immutable cards.
        bases[name] = values[::-1] if any(exchanging) else values
    power = [max(0, stat(i, "power", bases["power"][i])) for i in range(2)]
    attack = [max(0, stat(i, "attack", power[i] * (m.pillz + 1))) for i, m in enumerate(moves)]
    tune_out = any(e.stat == "tune_out" for row in active for e in row)
    contest = [m.pillz + 1 for m in moves] if tune_out else attack
    winner = max(range(2), key=lambda i: (contest[i], -cards[i].stars, i == state.leader))
    life = [p.life for p in state.players]
    pillz = [p.pillz - m.pillz - 3 * m.fury for p, m in zip(state.players, moves)]
    damage = max(0, stat(winner, "damage", bases["damage"][winner] + 2 * moves[winner].fury))
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
