"""Immutable deterministic classic-game core; unsupported effects fail closed.

Pillz in Move are *paid* pillz. The free pill is added only to attack.
Original hands are retained so played cards continue to count for clan bonuses.
"""
from dataclasses import dataclass, replace
import re
from functools import lru_cache

ENGINE_REVISION="mechanics-v2"

CONDITIONS={"always","courage","reprisal","confidence","revenge","defeat",
            "victory or defeat","day","night","unison","disunion","symmetry",
            "asymmetry","bet_over","bet_under","perfect","killshot","stop"}
# Decided after the fight: these only carry Life/Pillz (incl. persistent) effects.
POST_ROUND={"defeat","victory or defeat","perfect","killshot"}

# Card text abbreviations seen in official data -> canonical wording.
_ABBREVIATIONS=(
    (r"\bVict\.?\s+Or\s+Def(?:eat)?\.?", "Victory Or Defeat"),
    (r"\bConf\.", "Confidence"), (r"\bRepris\.", "Reprisal"), (r"\bRev\.", "Revenge"),
    (r"\bAsymm?\.", "Asymmetry"), (r"\bBrwl\.", "Brawl"),
    (r"\bRecov?\.", "Recover"), (r"\bCanc\.", "Cancel"),
    (r"\bProt(?:ec|ect)?\.\s*:?\s*", "Protection: "),
    (r"\bPow\b\.?", "Power"), (r"\bDmg\b\.?", "Damage"), (r"\bDam\b\.?", "Damage"),
    (r"\bAt[tk]\b\.?", "Attack"), (r"\bMod\b\.?", "Modif"),
    (r"\s*&\s*", " And "), (r"\s*/\s*", " And "), (r"\bPillz\.\s*(Min|Max)\b", r"Pillz, \1"), (r";", ":"),
)


def normalize_text(text: str) -> str:
    for pattern, replacement in _ABBREVIATIONS:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()

# Persistent end-of-round effects (official rules, urban-rivals.com/game/rules):
# Poison/Heal(Care) tick at the end of each round AFTER the one they were won
# in; Toxin/Regen and their Pillz forms Consume/Dope also tick straight after
# the round they were played. A second effect of the same kind replaces the
# first. Poison/Toxin/Consume never take the target below Min; Heal/Regen/Dope
# never raise it above Max.
PERSISTENT={"poison":("life",True,False),"toxin":("life",True,True),
            "consume":("pillz",True,True),"heal":("life",False,False),
            "regen":("life",False,True),"dope":("pillz",False,True)}


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
    divisor: int = 1

    def __post_init__(self):
        if self.stat not in {"power", "damage", "attack", "life", "pillz", "stop_ability",
                             "protect_power", "protect_damage", "protect_attack",
                             "protect_ability", "protect_bonus", "exchange_power",
                             "exchange_damage", "tune_out", "stop_bonus",
                             "cancel_power", "cancel_damage", "cancel_attack",
                             "copy_ability", "copy_bonus", "copy_power",
                             "copy_damage", "recover_pillz", *PERSISTENT,
                             "impose_power", "impose_damage", "cancel_life", "cancel_pillz"}:
            raise ValueError(f"Unsupported effect stat: {self.stat}")
        if self.condition not in CONDITIONS:
            raise ValueError(f"Unsupported condition: {self.condition}")
        if self.multiplier not in {"none", "support", "brawl", "growth", "degrowth", "equalizer", "opp_power", "opp_damage", "damage_dealt", "life_left", "pillz_left"}:
            raise ValueError(f"Unsupported multiplier: {self.multiplier}")
        if self.multiplier=="damage_dealt" and (self.stat not in {"life","pillz"} or self.amount<=0 or self.opponent or self.condition in {"defeat","victory or defeat"}):
            raise ValueError("Per-damage recovery requires a positive own resource effect on victory")
        if self.minimum < 0 or self.maximum < self.minimum:
            raise ValueError("Invalid effect bounds")
        if type(self.threshold) is not int or self.threshold < 0 or (
                self.condition not in {"bet_over", "bet_under"} and self.threshold != 0):
            raise ValueError("Invalid Bet threshold")
        if type(self.divisor) is not int or self.divisor < 1:
            raise ValueError("Invalid effect divisor")
        if self.stat=="recover_pillz" and (self.amount<1 or self.opponent
                or self.condition not in {"defeat","victory or defeat"}
                or self.multiplier!="none"):
            raise ValueError("Pillz recovery requires an own defeat-based fraction")
        if self.stat!="recover_pillz" and self.divisor!=1:
            raise ValueError("Only Pillz recovery uses a divisor")
        if self.condition in POST_ROUND - {"defeat", "victory or defeat"} and self.stat not in {"life", "pillz", *PERSISTENT}:
            raise ValueError("Perfect/Killshot conditions require life or pillz effects")
        if self.stat.startswith(("protect_", "exchange_", "cancel_", "copy_", "impose_")) and (
                self.amount != 0 or self.opponent or self.multiplier != "none"
                or self.condition in {"defeat", "victory or defeat"}):
            raise ValueError("Unsupported protection/exchange/cancel parameters")


def parse_effect(text: str) -> tuple[Effect, ...]:
    """Parse a deliberately small, auditable subset of English card text."""
    text = normalize_text(text.strip()).rstrip(".")
    if text.lower() in ("", "none", "no ability", "no bonus"):
        return ()
    # Backlash: the card's own player pays (official rules: abilities that cost
    # your own Life or Pillz); it fires when the card wins, like other effects.
    backlash = re.match(r"Backlash\s*:\s*(.*)", text, re.I)
    if backlash:
        inner = parse_effect(backlash[1])
        if any(e.stat not in {"life", "pillz", *PERSISTENT} or e.condition != "always" for e in inner):
            raise ValueError("Only plain Backlash Life/Pillz/Poison costs are supported")
        return tuple(replace(e, opponent=False, amount=-abs(e.amount) if e.stat in {"life", "pillz"} else e.amount)
                     for e in inner)
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
        if condition not in CONDITIONS:
            raise ValueError(f"Unsupported condition: {prefix}")
        text = text.strip()
    if re.fullmatch(r"Copy:\s*Opp\.?\s+Ability", text, re.I) and condition=="always":
        return (Effect("copy_ability",0),)
    if re.fullmatch(r"Copy:?\s*Opp\.?\s+Bonus", text, re.I) and condition=="always":
        return (Effect("copy_bonus",0),)
    match=re.fullmatch(r"Copy:?\s*Opp\.?\s+(Power|Damage)", text, re.I)
    if match:
        return (Effect("copy_"+match[1].lower(),0,condition=condition,threshold=threshold),)
    if re.fullmatch(r"Copy:\s*Power\s+And\s+Damage\s+Opp\.?",text,re.I):
        return (Effect("copy_power",0,condition=condition,threshold=threshold),
                Effect("copy_damage",0,condition=condition,threshold=threshold))
    match = re.fullmatch(r"Cancel\s+Opp\.?\s+(Power(?:\s+And\s+Damage)?|Damage|Attack)\s+Modif", text, re.I)
    if match:
        return tuple(Effect("cancel_"+stat,0,condition=condition,threshold=threshold)
                     for stat in re.split(r"\s+and\s+",match[1].lower()))
    match = re.fullmatch(r"(Power|Damage)\s+Impose", text, re.I)
    if match:
        return (Effect("impose_" + match[1].lower(), 0, condition=condition, threshold=threshold),)
    match = re.fullmatch(r"Cancel\s+Opp\.?\s+(Pillz\s+And\s+Life|Life|Pillz)\s+Modif", text, re.I)
    if match:
        return tuple(Effect("cancel_" + stat, 0, condition=condition, threshold=threshold)
                     for stat in re.split(r"\s+and\s+", match[1].lower()))
    if re.fullmatch(r"Stop\s+Opp\.?\s+Bonus", text, re.I):
        return (Effect("stop_bonus",0,True,condition=condition,threshold=threshold),)
    match=re.fullmatch(r"Recover\s+(\d+)\s+Pillz\s+Out\s+Of\s+(\d+)",text,re.I)
    if match:
        if multiplier!="none" or condition not in {"always","defeat","victory or defeat"}:
            raise ValueError("Combined Pillz recovery conditions are not supported")
        return (Effect("recover_pillz",int(match[1]),minimum=1,
                       condition="defeat" if condition=="always" else condition,
                       divisor=int(match[2])),)
    match=re.fullmatch(r"([+]\d+)\s+(Life|Pillz)\s+Per\s+Damage",text,re.I)
    if match:
        if multiplier!="none":
            raise ValueError("Combined per-damage multipliers are not supported")
        return (Effect(match[2].lower(),int(match[1]),condition=condition,
                       multiplier="damage_dealt",threshold=threshold),)
    match = re.fullmatch(r"([+]\d+)\s+Attack\s+Per\s+Opp\.?\s+(Power|Damage)",text,re.I)
    if match:
        return (Effect("attack",int(match[1]),condition=condition,
                       multiplier="opp_"+match[2].lower(),threshold=threshold),)
    match = re.fullmatch(r"([+]\d+)\s+(?:Attack|Atk)\s+Per\s+(Life|Pillz)\s+Left",text,re.I)
    if match:
        return (Effect("attack",int(match[1]),condition=condition,
                       multiplier=match[2].lower()+"_left",threshold=threshold),)
    match = re.fullmatch(r"Protection\s*:\s*(Power|Damage|Attack|Ability|Bonus|Power\s+And\s+Damage)", text, re.I)
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
    match = re.fullmatch(r"(Poison|Toxin|Consume)\s+(\d+)\s*,?\s*Min\.?\s*(\d+)", text, re.I)
    if match:
        return (Effect(match[1].lower(), int(match[2]), True, minimum=int(match[3]),
                       condition=condition, multiplier=multiplier, threshold=threshold),)
    match = re.fullmatch(r"(Heal|Care|Regen|Regeneration|Dope)\s+(\d+)\s*,?\s*Max\.?\s*(\d+)", text, re.I)
    if match:
        kind = {"care": "heal", "regeneration": "regen"}.get(match[1].lower(), match[1].lower())
        return (Effect(kind, int(match[2]), False, maximum=int(match[3]),
                       condition=condition, multiplier=multiplier, threshold=threshold),)
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
            if condition in POST_ROUND and any(stat not in {"life", "pillz"} for stat in stats):
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
    # Persistent effects currently acting ON this player: (kind, amount, bound).
    effects: tuple[tuple[str, int, int], ...] = ()

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
        other_bonus_on=sum(x.clan==other.clan for x in state.players[1-side].hand)>=2
        def expand(row):
            result=[]
            for e in row:
                if e.stat not in {"copy_ability","copy_bonus"}:
                    result.append(e)
                    continue
                if (e.amount,e.condition,e.multiplier,e.opponent)!=(0,"always","none",False):
                    raise ValueError("Conditional or modified effect-copy is not verified")
                if other.clan.casefold() in {"leader","genesis"}:
                    continue
                donor=other.ability if e.stat=="copy_ability" else other.bonus if other_bonus_on else ()
                if any(x.stat in {"copy_ability","copy_bonus"} for x in donor):
                    raise ValueError("Recursive effect-copy is not verified")
                result.extend(donor)
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
                      "asymmetry": moves[side].card != moves[1-side].card,
                      # Decided later: Perfect/Killshot after the fight, Stop by the
                      # opposing Stop Opp. Ability below.
                      "perfect": True, "killshot": True, "stop": True}
        multipliers = {"none": 1, "growth": state.round, "degrowth": 5-state.round,
                       "support": sum(x.clan == c.clan for x in p.hand),
                       "brawl": sum(x.clan == cards[1-side].clan for x in state.players[1-side].hand),
                       "equalizer": cards[1-side].stars,
                       "opp_power": cards[1-side].power, "opp_damage": cards[1-side].damage,
                       "life_left":p.life,"pillz_left":p.pillz,
                       "damage_dealt":1}
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
    # Retain source identity while resolving stops. Protection: Ability is
    # normally a bonus (Skeelz); Protection: Bonus is normally an ability.
    # Each works only while its own source remains active. Opposing cross-source
    # cycles still need an observed precedence rule and remain fail-closed.
    for side in range(2):
        if (any(e.stat=="stop_ability" for e in active[side][ability_sizes[side]:])
                and any(e.stat=="stop_bonus" for e in active[1-side][:ability_sizes[1-side]])):
            raise ValueError("Cross-source Stop Ability/Bonus precedence is not yet verified")
    raw_abilities=[active[i][:ability_sizes[i]] for i in range(2)]
    raw_bonuses=[active[i][ability_sizes[i]:] for i in range(2)]
    stop_bonus_raw=[any(e.stat=="stop_bonus" for e in raw_abilities[1-i]+raw_bonuses[1-i])
                    for i in range(2)]
    ability_protected=[any(e.stat=="protect_ability" for e in raw_bonuses[i])
                       and not stop_bonus_raw[i] for i in range(2)]
    blocked = [any(e.stat == "stop_ability" for e in active[1-i])
               and not ability_protected[i] for i in range(2)]
    # "Stop:" effects activate only when Stop Opp. Ability blocks this card;
    # everything else in a blocked ability is removed.
    abilities=[tuple(e for e in active[i][:ability_sizes[i]] if (e.condition=="stop")==blocked[i])
               for i in range(2)]
    bonuses=[tuple(e for e in active[i][ability_sizes[i]:] if e.condition!="stop") for i in range(2)]
    bonus_protected=[any(e.stat=="protect_bonus" for e in abilities[i]) for i in range(2)]
    bonus_blocked=[any(e.stat=="stop_bonus" for e in abilities[1-i]+bonuses[1-i])
                   and not bonus_protected[i] for i in range(2)]
    active=[abilities[i]+(() if bonus_blocked[i] else bonuses[i]) for i in range(2)]
    # Cancel removes the opposing card's modifiers of this type, irrespective
    # of their source or which card those modifiers would target.
    cancelled=[{name for name in ("power","damage","attack","life","pillz")
                if any(e.stat=="cancel_"+name for e in active[1-i])} for i in range(2)]
    active=[tuple(e for e in row if e.stat not in cancelled[i]
                  and not (e.stat in PERSISTENT and PERSISTENT[e.stat][0] in cancelled[i])
                  and not (e.stat.startswith(("exchange_","copy_","impose_")) and e.stat.split("_",1)[1] in cancelled[i]))
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
        copying=[any(e.stat=="copy_"+name for e in row) for row in active]
        imposing=[any(e.stat=="impose_"+name for e in row) for row in active]
        if any(imposing) and (all(imposing) or any(exchanging) or any(copying)):
            raise ValueError(f"{name.title()} Impose against Copy/Exchange/Impose is not yet verified")
        # A matching Exchange takes precedence over Copy (official Exchange rule).
        # Impose forces the imposer's starting value onto the opposing card.
        bases[name] = (values[::-1] if any(exchanging) else
                       [values[1-i] if (copying[i] or imposing[1-i]) else values[i] for i in range(2)])
    power = [max(0, stat(i, "power", bases["power"][i])) for i in range(2)]
    attack = [max(0, stat(i, "attack", power[i] * (m.pillz + 1))) for i, m in enumerate(moves)]
    tune_out = any(e.stat == "tune_out" for row in active for e in row)
    contest = [m.pillz + 1 for m in moves] if tune_out else attack
    def ranking(values):
        return max(range(2), key=lambda i: (values[i], -cards[i].stars, i == state.leader))
    winner = ranking(contest)
    loser = 1 - winner
    # Killshot: won with at least twice the opposing Attack (official rules).
    killshot = attack[winner] >= 2 * attack[loser]
    # Perfect: won with exactly the Pillz needed, i.e. one paid pill fewer
    # (all else equal) would not have won. Zero paid Pillz is always exact.
    perfect = True
    if moves[winner].pillz > 0:
        fewer = list(contest)
        fewer[winner] = (moves[winner].pillz if tune_out else
                         max(0, stat(winner, "attack", power[winner] * moves[winner].pillz)))
        perfect = ranking(fewer) != winner

    def triggered(owner, e):
        if e.condition == "defeat":
            return owner != winner
        if e.condition == "victory or defeat":
            return True
        if owner != winner:
            return False
        return {"perfect": perfect, "killshot": killshot}.get(e.condition, True)
    life = [p.life for p in state.players]
    pillz = [p.pillz - m.pillz - 3 * m.fury for p, m in zip(state.players, moves)]
    damage = max(0, stat(winner, "damage", bases["damage"][winner] + 2 * moves[winner].fury))
    life[1 - winner] = max(0, life[1 - winner] - damage)
    for owner in range(2):
        for e in active[owner]:
            if e.stat not in {"life", "pillz", "recover_pillz"}:
                continue
            if triggered(owner, e):
                if e.stat=="recover_pillz":
                    # The attack allocation includes the free pill. Official
                    # recovery rounds the stated fraction down, minimum one.
                    recovered=max(e.minimum,(moves[owner].pillz+1)*e.amount//e.divisor)
                    pillz[owner]+=recovered
                    continue
                if e.multiplier=="damage_dealt":
                    e=replace(e,amount=e.amount*damage,multiplier="none")
                target = 1 - owner if e.opponent else owner
                values = life if e.stat == "life" else pillz
                values[target] = max(0, _modify(values[target], e))
    # Effects won in earlier rounds tick now, then this round's new ones start.
    lingering=[dict((k,(a,b)) for k,a,b in p.effects) for p in state.players]
    def tick(target,kind,amount,bound):
        resource,harmful,_=PERSISTENT[kind]
        values=life if resource=="life" else pillz
        e=Effect(resource,-amount if harmful else amount,
                 minimum=bound if harmful else 0,maximum=10000 if harmful else bound)
        values[target]=max(0,_modify(values[target],e))
    for target in range(2):
        for kind,(amount,bound) in lingering[target].items():
            resource,harmful,_=PERSISTENT[kind]
            # Harmful effects on a player came from the opponent; helpful ones are
            # the player's own. Cancel Opp. Life/Pillz Modif. pauses the
            # opponent's for this round only (official rules).
            source=1-target if harmful else target
            if resource in cancelled[source]:
                continue
            tick(target,kind,amount,bound)
    for owner in range(2):
        for e in active[owner]:
            if e.stat not in PERSISTENT:
                continue
            if not triggered(owner, e) or e.amount<=0:
                continue
            target=1-owner if e.opponent else owner
            bound=e.minimum if PERSISTENT[e.stat][1] else e.maximum
            lingering[target][e.stat]=(e.amount,bound)
            if PERSISTENT[e.stat][2]:
                tick(target,e.stat,e.amount,bound)
    players = tuple(replace(p, life=life[i], pillz=pillz[i], used=p.used + (moves[i].card,),
                            last_won=i == winner,
                            effects=tuple(sorted((k,a,b) for k,(a,b) in lingering[i].items())))
                    for i, p in enumerate(state.players))
    return State(players, 1 - state.leader, state.round + 1, state.day)


def evaluate(state: State) -> float:
    a, b = state.players
    if state.terminal:
        return float((a.life > b.life) - (a.life < b.life)) * 10000
    # Explicit heuristic at a one-round horizon; not a claimed match win rate.
    reserve = [sum(c.damage for i, c in enumerate(p.hand) if i not in p.used) for p in (a, b)]
    life = [a.life, b.life]
    pillz = [a.pillz, b.pillz]
    # Credit lingering effects for the rounds still to be played.
    remaining = max(0, 5 - state.round)
    for side, p in enumerate((a, b)):
        for kind, amount, bound in p.effects:
            resource, harmful, _ = PERSISTENT[kind]
            values = life if resource == "life" else pillz
            for _ in range(remaining):
                values[side] = (max(min(values[side], bound), values[side] - amount) if harmful
                                else min(max(values[side], bound), values[side] + amount))
    return life[0] - life[1] + .65 * (pillz[0] - pillz[1]) + .15 * (reserve[0] - reserve[1])
