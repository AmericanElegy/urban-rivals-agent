"""Immutable deterministic classic-game core; unsupported effects fail closed.

Pillz in Move are *paid* pillz. The free pill is added only to attack.
Original hands are retained so played cards continue to count for clan bonuses.

Rule sources for the extended mechanics (persistent effects, chained
conditions, Stop/Killshot/Perfect/Versus/After, Impose, Cards/Players targets,
Oculus infiltration, Leader team abilities) are the official per-card
descriptions retained in ``data/card_reference.json`` and, where those are
silent, the Urban Rivals wiki. Interpretation choices are documented inline.
"""
from collections import Counter
from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
from functools import lru_cache

ENGINE_REVISION = "persistent-suite-v2"

OLD_CONDITIONS = {"always", "courage", "reprisal", "confidence", "revenge", "defeat",
                  "victory or defeat", "day", "night", "unison", "disunion", "symmetry",
                  "asymmetry", "bet_over", "bet_under"}
OUTCOME_CONDITIONS = {"defeat", "victory or defeat"}
MULTIPLIERS = {"none", "support", "brawl", "growth", "degrowth", "equalizer", "opp_power",
               "opp_damage", "damage_dealt", "life_left", "pillz_left", "life_lost", "pillz_lost"}
# Persistent effects: (life sign, pillz sign) per round; replacement slot.
PERSISTENT = {"poison": ("life", "poison", False), "toxin": ("life", "poison", True),
              "corrosion": ("life", "poison", False), "combust": ("both", "combust", False),
              "mindwipe": ("both", "mindwipe", True), "heal": ("life", "heal", False),
              "regen": ("life", "regen", True), "dope": ("pillz", "dope", True),
              "consume": ("pillz", "consume", True)}
POST_ROUND = {"life", "pillz", "recover_pillz"} | set(PERSISTENT)
STATS = {"power", "damage", "attack", "life", "pillz", "stop_ability",
         "protect_power", "protect_damage", "protect_attack",
         "protect_ability", "protect_bonus", "exchange_power",
         "exchange_damage", "tune_out", "stop_bonus",
         "cancel_power", "cancel_damage", "cancel_attack", "cancel_life", "cancel_pillz",
         "copy_ability", "copy_bonus", "copy_power",
         "copy_damage", "recover_pillz", "impose_power", "impose_damage",
         "infiltrated", "cancel_leader"} | set(PERSISTENT)
# Gates evaluated only after attack is known; restricted to post-round effects.
LATE_GATES = {"killshot", "perfect"}
SIMPLE_GATES = {"stop", "killshot", "perfect", "reanimate", "team"}
CLAN_GATES = ("versus:", "after:", "infiltrates:")


def _valid_gate(gate):
    if gate in SIMPLE_GATES or gate in OLD_CONDITIONS - {"always", "bet_over", "bet_under"}:
        return True
    return gate.startswith(CLAN_GATES) and all(gate.split(":", 1)[1].split("|"))


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
    gates: tuple[str, ...] = ()
    both: bool = False

    def __post_init__(self):
        if self.stat not in STATS:
            raise ValueError(f"Unsupported effect stat: {self.stat}")
        if self.condition not in OLD_CONDITIONS:
            raise ValueError(f"Unsupported condition: {self.condition}")
        if self.multiplier not in MULTIPLIERS:
            raise ValueError(f"Unsupported multiplier: {self.multiplier}")
        if any(not _valid_gate(g) for g in self.gates) or len(set(self.gates)) != len(self.gates):
            raise ValueError("Unsupported or repeated condition gate")
        if LATE_GATES & set(self.gates) and self.stat not in POST_ROUND:
            raise ValueError("Killshot/Perfect require an end-of-round effect")
        if "reanimate" in self.gates and (self.stat != "life" or self.condition != "defeat"
                                          or self.amount <= 0 or self.opponent):
            raise ValueError("Reanimate requires an own Life gain on defeat")
        if self.both and self.opponent:
            raise ValueError("A both-sides effect has no single opponent target")
        if self.multiplier=="damage_dealt" and (self.stat not in {"life","pillz"} or self.amount<=0 or self.opponent or self.condition in OUTCOME_CONDITIONS):
            raise ValueError("Per-damage recovery requires a positive own resource effect on victory")
        if self.minimum < 0 or self.maximum < self.minimum:
            raise ValueError("Invalid effect bounds")
        if type(self.threshold) is not int or self.threshold < 0 or (
                self.condition not in {"bet_over", "bet_under"} and self.threshold != 0):
            raise ValueError("Invalid Bet threshold")
        if type(self.divisor) is not int or self.divisor < 1:
            raise ValueError("Invalid effect divisor")
        if self.stat=="recover_pillz" and (self.amount<1 or self.opponent
                or (self.condition not in OUTCOME_CONDITIONS and not self.both)
                or self.multiplier!="none"):
            raise ValueError("Pillz recovery requires an own defeat-based fraction")
        if self.stat!="recover_pillz" and self.divisor!=1:
            raise ValueError("Only Pillz recovery uses a divisor")
        if self.stat.startswith(("protect_", "exchange_", "cancel_", "copy_", "impose_")) and (
                self.amount != 0 or self.opponent or self.multiplier != "none"
                or self.condition in OUTCOME_CONDITIONS):
            raise ValueError("Unsupported protection/exchange/cancel parameters")
        if self.both and not (self.stat in {"power", "damage", "attack", "life", "pillz",
                                            "recover_pillz", "combust"}
                              or self.stat.startswith("protect_")):
            raise ValueError("Unsupported both-sides effect")


_ABBREVIATIONS = (
    (r"(\d)\s+Pillz\.?\s+Opp\b\.?", r"\1 Opp Pillz"),
    (r"\bVict\.?\s+Or\s+Def(?:eat)?\.?", "Victory Or Defeat"),
    (r"\bAsymm?\.", "Asymmetry"),
    (r"\bBrwl\.", "Brawl"),
    (r"\bRev\.", "Revenge"),
    (r"\bRecov\.", "Recover"),
    (r"\bCanc\.", "Cancel Opp"),
    (r"^(Courage|Reprisal|Revenge|Confidence|Defeat)\s*;", r"\1:"),
    (r"\bConf\.", "Confidence"),
    (r"\bRepris\.", "Reprisal"),
    (r"\bRec\.", "Recover"),
    (r"\bProt(?:ect|ec)?\.\s*:?\s*", "Protection: "),
    (r"\bPow\s*/\s*Dam\.?", "Power And Damage"),
    (r"\bPow\.?(?=\s|,|$)", "Power"),
    (r"\b(?:Dmg|Dam)\.?(?=\s|,|$)", "Damage"),
    (r"\b(?:Atk|Att)\.?(?=\s|,|$)", "Attack"),
    (r"\s*&\s*", " And "),
    (r"\bMod\.?$", "Modif"),
    (r"\bModif\.", "Modif"),
    (r"\bPillz\.", "Pillz,"),
    (r"\b(Min|Max)\.", r"\1"),
    (r",\s*(Min|Max)\b", r", \1"),
    (r"\bOpp\.", "Opp"),
    (r"([+-])\s+(\d)", r"\1\2"),
    (r"\s+:", ":"),
    (r"\s+", " "),
)


def canonical_text(text: str) -> str:
    """Collapse official spelling variants without changing their meaning."""
    text = text.strip().rstrip(".").strip()
    for pattern, repl in _ABBREVIATIONS:
        text = re.sub(pattern, repl, text, flags=re.I)
    return text.strip().rstrip(",").strip()


_PREFIX = re.compile(
    r"(Bet\s*[<>]\s*\d+\s*Pillz|Victory Or Defeat|Versus\([^)]*\)|After\([^)]*\)|"
    r"Infiltrates\([^)]*\)|Versus|After|[A-Za-z]+)\s*:\s*", re.I)


def _clan_gate(kind, raw):
    clans = [c.strip() for c in raw.split("|") if c.strip()]
    if not clans:
        raise ValueError(f"{kind.title()} requires its official clan list")
    return kind + ":" + "|".join(sorted(clans, key=str.casefold))


def parse_effect(text: str) -> tuple[Effect, ...]:
    """Parse a deliberately small, auditable subset of English card text.

    Day/Night pairs may be supplied joined by `` / ``; both halves are kept
    and gated by the observed clock. Versus/After/Infiltrates prefixes need
    their clan lists inline, e.g. ``Versus(Oculus|Zenith): Power +2``.
    """
    if " / " in text:
        return tuple(e for part in text.split(" / ") for e in parse_effect(part))
    text = canonical_text(text)
    if text.lower() in ("", "none", "no ability", "no bonus"):
        return ()
    prefixes = []
    while True:
        match = _PREFIX.match(text)
        if not match:
            break
        word = match[1].strip()
        key = word.lower()
        # Protection's and Copy's colon belongs to the mechanic, not a condition.
        if key in {"protection", "copy"}:
            break
        prefixes.append(word)
        text = text[match.end():]
    return _apply_prefixes(prefixes, text.strip())


def _apply_prefixes(prefixes, body):
    condition, multiplier, threshold = "always", "none", 0
    gates = []
    flags = set()
    plain_conditions = []
    for word in prefixes:
        key = word.lower()
        bet = re.fullmatch(r"Bet\s*([<>])\s*(\d+)\s*Pillz", word, re.I)
        clan = re.fullmatch(r"(Versus|After|Infiltrates)\(([^)]*)\)", word, re.I)
        if bet:
            plain_conditions.append(("bet_over" if bet[1] == ">" else "bet_under", int(bet[2])))
        elif clan:
            gates.append(_clan_gate(clan[1].lower(), clan[2]))
        elif key in {"versus", "after"}:
            raise ValueError(f"Unsupported condition: {word} (clan list required)")
        elif key in {"support", "brawl", "growth", "degrowth", "equalizer"}:
            if multiplier != "none":
                raise ValueError("Combined multipliers are not supported")
            multiplier = key
        elif key in {"stop", "killshot", "perfect", "team"}:
            gates.append(key)
        elif key in {"backlash", "xantiax", "reanimate"}:
            flags.add(key)
        elif key in OLD_CONDITIONS - {"always", "bet_over", "bet_under"}:
            plain_conditions.append((key, 0))
        else:
            raise ValueError(f"Unsupported condition: {word}")
    outcome = [c for c in plain_conditions if c[0] in OUTCOME_CONDITIONS]
    if len(outcome) > 1:
        raise ValueError("Conflicting outcome conditions")
    primary = outcome[0] if outcome else (plain_conditions[0] if plain_conditions else None)
    for item in plain_conditions:
        if item is primary:
            continue
        if item[0] in {"bet_over", "bet_under"}:
            raise ValueError("Bet must be the only pre-round condition")
        gates.append(item[0])
    if primary:
        condition, threshold = primary
    effects = _parse_body(body, condition, multiplier, threshold, bool(gates or flags))
    if "reanimate" in flags:
        if condition not in {"always", "defeat"}:
            raise ValueError("Reanimate is a defeat condition")
        condition = "defeat"
        gates.append("reanimate")
    if "xantiax" in flags:
        if condition not in {"always", "victory or defeat"}:
            raise ValueError("Xantiax is a victory-or-defeat condition")
        condition = "victory or defeat"
    result = []
    for e in effects:
        if "backlash" in flags:
            # Backlash turns the effect on its own controller.
            if e.stat in PERSISTENT:
                e = replace(e, opponent=False)
            elif not (e.stat in {"life", "pillz"} and e.amount < 0 and not e.opponent):
                raise ValueError("Backlash requires an own resource loss")
        if "xantiax" in flags:
            if not (e.stat == "life" and e.amount < 0 and not e.opponent):
                raise ValueError("Xantiax requires a Life loss")
            e = replace(e, both=True)
        if e.condition == "always":
            e = replace(e, condition=condition, threshold=threshold)
        elif condition != "always" and condition != e.condition:
            # A pre-round condition in front of an outcome-bound mechanic
            # (e.g. "Unison: Recover ...") becomes an additional gate.
            if condition in OUTCOME_CONDITIONS or condition in {"bet_over", "bet_under"}:
                raise ValueError("Conflicting outcome conditions")
            gates.insert(0, condition)
        if multiplier != "none":
            if e.multiplier != "none" and e.multiplier != multiplier:
                raise ValueError("Combined multipliers are not supported")
            e = replace(e, multiplier=multiplier)
        e = replace(e, gates=tuple(gates))
        if e.condition in OUTCOME_CONDITIONS and e.stat not in POST_ROUND:
            raise ValueError("Post-round conditions require life or pillz effects")
        result.append(e)
    return tuple(result)


def _bounds(values):
    bound = (values.get("bound") or "").lower()
    limit = int(values["limit"]) if values.get("limit") else None
    return (limit if bound == "min" else 0, limit if bound == "max" else 10000)


def _parse_body(text, condition, multiplier, threshold, chained=False):
    """Parse a mechanic once prefixes are removed; conditions applied later."""
    if not text:
        raise ValueError("Missing effect after condition")
    match = re.fullmatch(r"Copy:?\s*Opp\s+(Ability|Bonus)", text, re.I)
    if match:
        if multiplier != "none":
            raise ValueError("Modified effect-copy is not verified")
        return (Effect("copy_" + match[1].lower(), 0),)
    match=re.fullmatch(r"Copy:?\s*Opp\s+(Power|Damage)", text, re.I)
    if match:
        return (Effect("copy_"+match[1].lower(),0),)
    if re.fullmatch(r"Copy:\s*Power\s+And\s+Damage\s+Opp",text,re.I):
        return (Effect("copy_power",0), Effect("copy_damage",0))
    match = re.fullmatch(r"Cancel\s+Opp\s+(Power(?:\s+And\s+Damage)?|Damage|Attack|Life|Pillz(?:\s+And\s+Life)?)\s+Modif", text, re.I)
    if match:
        return tuple(Effect("cancel_"+stat,0)
                     for stat in re.split(r"\s+and\s+",match[1].lower()))
    match = re.fullmatch(r"(Power|Damage)\s+Impose", text, re.I)
    if match:
        return (Effect("impose_" + match[1].lower(), 0),)
    if re.fullmatch(r"Infiltrated", text, re.I):
        return (Effect("infiltrated", 0),)
    if re.fullmatch(r"Cancel\s+Leader", text, re.I):
        return (Effect("cancel_leader", 0),)
    if re.fullmatch(r"Stop\s+Opp\s+Bonus", text, re.I):
        return (Effect("stop_bonus",0,True),)
    match=re.fullmatch(r"Recover\s+(\d+)\s+(Players\s+)?Pillz\s+Out\s+Of\s+(\d+)",text,re.I)
    if match:
        if multiplier!="none":
            raise ValueError("Combined Pillz recovery conditions are not supported")
        if match[2]:
            # Official: on victory both players each recover a share of their own stake.
            if condition != "always":
                raise ValueError("Combined Pillz recovery conditions are not supported")
            return (Effect("recover_pillz",int(match[1]),minimum=1,
                           divisor=int(match[3]),both=True),)
        # A pre-round prefix (e.g. Unison) becomes an extra gate later.
        return (Effect("recover_pillz",int(match[1]),minimum=1,
                       condition=condition if condition in OUTCOME_CONDITIONS else "defeat",
                       divisor=int(match[3])),)
    match = re.fullmatch(r"(Players\s+)?(Poison|Toxin|Corrosion|Combust|Mindwipe|Consume)\s+(\d+),?\s*Min\s*(\d+)", text, re.I)
    if match:
        if match[1] and match[2].lower() != "combust":
            raise ValueError("Only Combust has an official Players variant")
        stat = match[2].lower()
        return (Effect(stat, -int(match[3]), not match[1], minimum=int(match[4]),
                       multiplier="growth" if stat == "corrosion" else "none", both=bool(match[1])),)
    match = re.fullmatch(r"(Heal|Regen|Dope)\s+(\d+),?\s*Max\s*(\d+)", text, re.I)
    if match:
        return (Effect(match[1].lower(), int(match[2]), maximum=int(match[3])),)
    match=re.fullmatch(r"([+]\d+)\s+(Life|Pillz)\s+Per\s+Damage(?:,?\s*Max\s*(\d+))?",text,re.I)
    if match:
        if multiplier!="none":
            raise ValueError("Combined per-damage multipliers are not supported")
        return (Effect(match[2].lower(),int(match[1]),multiplier="damage_dealt",
                       maximum=int(match[3]) if match[3] else 10000),)
    match = re.fullmatch(r"([+]\d+)\s+(Life|Pillz)\s+Per\s+Opp\s+(Power|Damage)", text, re.I)
    if match:
        # Official: gained at the end of a won round, times the opposing printed value.
        if multiplier != "none":
            raise ValueError("Combined multipliers are not supported")
        return (Effect(match[2].lower(), int(match[1]), multiplier="opp_" + match[3].lower()),)
    match = re.fullmatch(r"([+]\d+)\s+Attack\s+Per\s+Opp\s+(Power|Damage)",text,re.I)
    if match:
        return (Effect("attack",int(match[1]),multiplier="opp_"+match[2].lower()),)
    match = re.fullmatch(r"(?P<amount>[+-]\d+)\s+(?P<opp>Opp\s+)?(?P<stat>Power|Damage|Attack)\s+Per\s+(?P<res>Life|Pillz)\s+(?P<kind>Left|Lost)"
                         r"(?:,?\s*(?P<bound>Min|Max)\s*(?P<limit>\d+))?", text, re.I)
    if match:
        values = match.groupdict()
        amount = int(values["amount"])
        if bool(values["opp"]) != (amount < 0):
            raise ValueError("Resource scaling must raise own or lower opposing statistics")
        if multiplier != "none":
            raise ValueError("Combined resource multipliers are not supported")
        minimum, maximum = _bounds(values)
        return (Effect(values["stat"].lower(), amount, bool(values["opp"]), minimum, maximum,
                       multiplier=values["res"].lower()+"_"+values["kind"].lower()),)
    match = re.fullmatch(r"Protection\s*:\s*(Cards\s+)?(Power|Damage|Attack|Ability|Bonus|Power\s+And\s+Damage)", text, re.I)
    if match:
        if multiplier != "none":
            raise ValueError("Protection does not support numeric multipliers")
        if match[1] and match[2].lower() not in {"power", "damage", "power and damage"}:
            raise ValueError("Unsupported Cards protection")
        return tuple(Effect("protect_" + stat, 0, both=bool(match[1]))
                     for stat in re.split(r"\s+and\s+", match[2].lower()))
    match = re.fullmatch(r"(Power|Damage|Power\s+And\s+Damage)\s+Exchange", text, re.I)
    if match:
        if multiplier != "none":
            raise ValueError("Exchange does not support numeric multipliers")
        return tuple(Effect("exchange_" + stat, 0)
                     for stat in re.split(r"\s+and\s+", match[1].lower()))
    if re.fullmatch(r"Stop\s+Opp\s+Ability", text, re.I):
        return (Effect("stop_ability", 0, True),)
    if re.fullmatch(r"Tune\s+Out", text, re.I):
        if condition != "always" or chained:
            raise ValueError("Conditional Tune Out is not verified")
        return (Effect("tune_out", 0),)
    stat_words = r"(?:Power|Damage|Attack|Life|Pillz)(?:\s+And\s+(?:Power|Damage|Attack|Life|Pillz))?"
    patterns = (
        r"(?P<target>Cards\s+|Players\s+)?(?P<stat>" + stat_words + r")\s*(?P<amount>[+-]\d+)",
        r"(?P<amount>[+-]\d+)\s*(?P<opp>Opp\s+)?(?P<target>Cards\s+|Players\s+)?(?P<stat>" + stat_words + r")",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern + r"(?:,?\s*(?P<bound>Min|Max)\s*(?P<limit>\d+))?", text, re.I)
        if match:
            values = match.groupdict()
            stats = re.split(r"\s+and\s+", values["stat"].lower())
            target = (values.get("target") or "").strip().lower()
            if values.get("opp") and target:
                raise ValueError("Opp and Cards/Players targets are exclusive")
            if target == "cards" and any(s not in {"power", "damage", "attack"} for s in stats):
                raise ValueError("Cards targets card statistics")
            if target == "players" and any(s not in {"life", "pillz"} for s in stats):
                raise ValueError("Players targets player resources")
            if condition in OUTCOME_CONDITIONS and any(stat not in {"life", "pillz"} for stat in stats):
                raise ValueError("Post-round conditions require life or pillz effects")
            minimum, maximum = _bounds(values)
            return tuple(Effect(stat, int(values["amount"]), bool(values.get("opp")),
                                minimum, maximum, both=bool(target)) for stat in stats)
    raise ValueError(f"Unsupported effect: {text!r}")


@lru_cache(maxsize=1)
def clan_bonus_table():
    """Most common official bonus text per clan, for Oculus infiltration."""
    root = Path(__file__).parent / "data"
    try:
        catalog = json.loads((root / "training_cards.json").read_text(encoding="utf-8"))["cards"]
    except (OSError, ValueError, KeyError):
        return {}
    counts = {}
    for card in catalog:
        counts.setdefault(card["clan"], Counter())[card.get("bonus", "")] += 1
    table = {clan: c.most_common(1)[0][0] for clan, c in counts.items()}
    try:
        reference = json.loads((root / "card_reference.json").read_text(encoding="utf-8"))
        for clan, variants in reference.get("conditional_bonuses", {}).items():
            if set(variants) == {"day", "night"}:
                table[clan] = variants["day"]["text"] + " / " + variants["night"]["text"]
    except (OSError, ValueError):
        pass
    return table


@lru_cache(maxsize=256)
def clan_bonus_effects(clan):
    text = clan_bonus_table().get(clan)
    if text is None:
        return None
    try:
        effects = parse_effect(text)
    except ValueError:
        return None
    if any(e.stat in {"infiltrated", "cancel_leader"} for e in effects):
        return None
    return effects


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
class Persistent:
    """A running effect on a player (the victim or beneficiary)."""
    kind: str
    slot: str
    life: int
    pillz: int
    minimum: int
    maximum: int
    owner: int

    def __post_init__(self):
        if self.owner not in (0, 1) or self.kind not in PERSISTENT:
            raise ValueError("Invalid persistent effect")


@dataclass(frozen=True)
class Player:
    hand: tuple[Card, ...]
    life: int = 14
    pillz: int = 12
    used: tuple[int, ...] = ()
    last_won: bool | None = None
    effects: tuple[Persistent, ...] = ()
    start_life: int | None = None
    start_pillz: int | None = None

    def __post_init__(self):
        if not 1 <= len(self.hand) <= 4 or self.life < 0 or self.pillz < 0:
            raise ValueError("Invalid player resources or hand size")
        if len(set(self.used)) != len(self.used) or any(i not in range(len(self.hand)) for i in self.used):
            raise ValueError("Invalid used-card indices")
        if len({e.slot for e in self.effects}) != len(self.effects):
            raise ValueError("Only one running effect per slot")


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


def _bounded(value, amount, minimum, maximum):
    if amount < 0:
        return min(value, max(minimum, value + amount))
    return max(value, min(maximum, value + amount))


def effective_clans(hand: tuple[Card, ...]) -> tuple[str, ...]:
    """Clan each card counts as, applying the official Oculus Infiltrated rule.

    One other clan present: the Oculus joins it. Two other clans: it joins
    the clan of the sole card. Three or more, or several Oculus: no effect.
    """
    oculus = [i for i, c in enumerate(hand) if c.clan == "Oculus"]
    clans = [c.clan for c in hand]
    if len(oculus) != 1 or not any(e.stat == "infiltrated" for e in hand[oculus[0]].bonus):
        return tuple(clans)
    others = Counter(c.clan for c in hand if c.clan != "Oculus")
    target = None
    if len(others) == 1:
        target = next(iter(others))
    elif len(others) == 2:
        singles = [clan for clan, n in others.items() if n == 1]
        if len(singles) == 1:
            target = singles[0]
    if target is None:
        return tuple(clans)
    clans[oculus[0]] = target
    return tuple(clans)


def _card_effects(state, side, card_index):
    """Ability and bonus rows for a played card (before Copy expansion)."""
    p = state.players[side]
    card = p.hand[card_index]
    clans = effective_clans(p.hand)
    mine = clans[card_index]
    bonus_on = sum(c == mine for c in clans) >= 2
    bonus = card.bonus
    if any(e.stat == "infiltrated" for e in bonus):
        if mine == "Oculus":
            bonus = ()
        else:
            bonus = clan_bonus_effects(mine)
            if bonus is None:
                raise ValueError(f"Infiltrated bonus of {mine} is not modeled")
    bonus = tuple(e for e in bonus if e.stat != "cancel_leader") if bonus_on else ()
    leaders = [c for c in p.hand if c.clan == "Leader"]
    leaders_cancelled = len(leaders) > 1 and any(
        e.stat == "cancel_leader" for c in leaders for e in c.bonus)
    ability = card.ability
    if card.clan == "Leader" and leaders_cancelled:
        ability = ()
    # Team abilities: every character of the team receives them.
    ability = tuple(e for e in ability if "team" not in e.gates)
    if not leaders_cancelled:
        for c in leaders:
            ability += tuple(e for e in c.ability if "team" in e.gates)
    return card, mine, ability, bonus


def resolve(state: State, first: Move, second: Move) -> State:
    """Resolve indexed side-0 and side-1 moves, independent of leader order."""
    moves = (first, second)
    for side, move in enumerate(moves):
        if not is_legal(state, side, move):
            raise ValueError(f"Illegal move for side {side}: {move}")
    rows = [_card_effects(state, side, m.card) for side, m in enumerate(moves)]
    cards = [r[0] for r in rows]
    eff_clans = [r[1] for r in rows]
    hand_clans = [effective_clans(p.hand) for p in state.players]
    def context(side):
        p = state.players[side]
        c = cards[side]
        unison = all(x.clan == c.clan for x in p.hand)
        opp_hand = state.players[1-side].hand
        last = p.hand[p.used[-1]].clan if p.used else None
        conditions = {"always": True, "courage": side == state.leader,
                      "reprisal": side != state.leader, "confidence": p.last_won is True,
                      "revenge": p.last_won is False, "defeat": True, "victory or defeat": True,
                      "day": state.day is True, "night": state.day is False,
                      "unison": unison, "disunion": not unison,
                      "symmetry": moves[side].card == moves[1-side].card,
                      "asymmetry": moves[side].card != moves[1-side].card,
                      "stop": True, "killshot": True, "perfect": True, "reanimate": True,
                      "team": True}
        start_life = p.start_life if p.start_life is not None else p.life
        start_pillz = p.start_pillz if p.start_pillz is not None else p.pillz
        multipliers = {"none": 1, "growth": state.round, "degrowth": 5-state.round,
                       "support": sum(x == eff_clans[side] for x in hand_clans[side]),
                       "brawl": sum(x == eff_clans[1-side] for x in hand_clans[1-side]),
                       "equalizer": cards[1-side].stars,
                       "opp_power": cards[1-side].power, "opp_damage": cards[1-side].damage,
                       "life_left":p.life,"pillz_left":p.pillz,
                       "life_lost": max(0, start_life - p.life),
                       "pillz_lost": max(0, start_pillz - p.pillz),
                       "damage_dealt":1}
        def gate_ok(g):
            if g.startswith("versus:"):
                return any(x.clan in g[7:].split("|") for x in opp_hand)
            if g.startswith("after:"):
                return last in g[6:].split("|")
            if g.startswith("infiltrates:"):
                return eff_clans[side] in g[12:].split("|")
            return conditions[g]
        def enabled(e):
            if state.day is None and (e.condition in {"day", "night"} or {"day", "night"} & set(e.gates)):
                raise ValueError("Day/Night effects require the observed game clock")
            # Bets count the attack allocation plus its free pill, not Fury's
            # separate three-pill cost or the player's remaining reserve.
            if e.condition == "bet_over":
                ok = moves[side].pillz + 1 > e.threshold
            elif e.condition == "bet_under":
                ok = moves[side].pillz + 1 < e.threshold
            else:
                ok = conditions[e.condition]
            return ok and all(gate_ok(g) for g in e.gates)
        return enabled, multipliers
    contexts = [context(side) for side in range(2)]
    # Expand from the original opposing ability, before checking conditions.
    # The replacement retains the copying source (ability or bonus); a
    # conditional Copy copies only when its own (copier-side) condition holds,
    # and copied conditions and multipliers are evaluated from the copier's side.
    sources = []
    for side in range(2):
        other = cards[1-side]
        other_ability, other_bonus = rows[1-side][2], rows[1-side][3]
        enabled = contexts[side][0]
        def expand(row):
            result=[]
            for e in row:
                if e.stat not in {"copy_ability","copy_bonus"}:
                    result.append(e)
                    continue
                if (e.amount,e.multiplier,e.opponent)!=(0,"none",False) or "stop" in e.gates:
                    raise ValueError("Modified effect-copy is not verified")
                if not enabled(e) or other.clan.casefold() in {"leader","genesis"}:
                    continue
                donor = other_ability if e.stat == "copy_ability" else other_bonus
                if any(x.stat in {"copy_ability","copy_bonus"} for x in donor):
                    raise ValueError("Recursive effect-copy is not verified")
                result.extend(x for x in donor if "team" not in x.gates)
            return tuple(result)
        sources.append((expand(rows[side][2]), expand(rows[side][3])))
    abil, bon = [], []
    for side in range(2):
        enabled, multipliers = contexts[side]
        ability, bonus = sources[side]
        def scaled(row):
            return tuple(replace(e, amount=e.amount * multipliers[e.multiplier])
                         for e in row if enabled(e))
        abil.append(scaled(ability))
        bon.append(scaled(bonus))
    # Retain source identity while resolving stops. Protection: Ability is
    # normally a bonus (Skeelz); Protection: Bonus is normally an ability.
    # Each works only while its own source remains active. Opposing cross-source
    # cycles still need an observed precedence rule and remain fail-closed.
    # "Stop:" effects wait for the owner's ability to be cancelled.
    pre = [tuple(e for e in abil[i] if "stop" not in e.gates) for i in range(2)]
    for side in range(2):
        if (any(e.stat=="stop_ability" for e in bon[side])
                and any(e.stat=="stop_bonus" for e in pre[1-side])):
            raise ValueError("Cross-source Stop Ability/Bonus precedence is not yet verified")
    stop_bonus_raw=[any(e.stat=="stop_bonus" for e in pre[1-i]+bon[1-i]) for i in range(2)]
    ability_protected=[any(e.stat=="protect_ability" for e in bon[i])
                       and not stop_bonus_raw[i] for i in range(2)]
    blocked = [any(e.stat == "stop_ability" for e in pre[1-i]+bon[1-i])
               and not ability_protected[i] for i in range(2)]
    abilities=[tuple(e for e in abil[i] if "stop" in e.gates) if blocked[i] else pre[i]
               for i in range(2)]
    if any(e.stat in {"stop_ability", "stop_bonus"} for i in range(2) if blocked[i] for e in abilities[i]):
        raise ValueError("Stop-triggered Stop effects are not verified")
    bonuses=list(bon)
    bonus_protected=[any(e.stat=="protect_bonus" for e in abilities[i]) for i in range(2)]
    bonus_blocked=[any(e.stat=="stop_bonus" for e in abilities[1-i]+bonuses[1-i])
                   and not bonus_protected[i] for i in range(2)]
    active=[abilities[i]+(() if bonus_blocked[i] else bonuses[i]) for i in range(2)]
    # Cancel removes the opposing card's modifiers of this type, irrespective
    # of their source or which card those modifiers would target.
    cancelled=[{name for name in ("power","damage","attack","life","pillz")
                if any(e.stat=="cancel_"+name for e in active[1-i])} for i in range(2)]
    def kept(e, gone):
        if e.stat in gone:
            return False
        if e.stat.startswith(("exchange_","copy_","impose_")) and e.stat.split("_",1)[1] in gone:
            return False
        if e.stat == "recover_pillz" and "pillz" in gone:
            return False
        if e.stat in PERSISTENT:
            kind = PERSISTENT[e.stat][0]
            parts = {"life", "pillz"} if kind == "both" else {kind}
            return not parts <= gone
        return True
    active=[tuple(e for e in row if kept(e, cancelled[i])) for i,row in enumerate(active)]

    def stat(side, name, initial):
        result = initial
        protected = any(e.stat == "protect_" + name for e in active[side]) or any(
            e.stat == "protect_" + name and e.both for e in active[1-side])
        for owner in (side, 1 - side):
            for e in active[owner]:
                if e.stat == name and (e.both or (owner != side) == e.opponent):
                    if protected and e.amount < 0:
                        continue
                    result = _modify(result, e)
        return result

    bases = {}
    for name in ("power", "damage"):
        exchanging = [any(e.stat == "exchange_" + name for e in row) for row in active]
        imposing = [any(e.stat == "impose_" + name for e in row) for row in active]
        if all(exchanging):
            raise ValueError(f"Simultaneous {name} Exchange is not yet verified")
        if any(imposing) and (all(imposing) or any(exchanging)):
            raise ValueError(f"{name.title()} Impose with Exchange or a second Impose is not verified")
        values = [getattr(c, name) for c in cards]
        # Exchange changes starting values, bypasses Protection, and precedes
        # ordinary modifiers and Fury. Each round starts from immutable cards.
        copying=[any(e.stat=="copy_"+name for e in row) for row in active]
        # A matching Exchange takes precedence over Copy (official Exchange rule).
        base = (values[::-1] if any(exchanging) else
                [values[1-i] if copying[i] else values[i] for i in range(2)])
        # Impose: the opposing card takes the printed value of the imposer.
        for i in range(2):
            if imposing[i]:
                base[1-i] = values[i]
        bases[name] = base
    power = [max(0, stat(i, "power", bases["power"][i])) for i in range(2)]
    attack = [max(0, stat(i, "attack", power[i] * (m.pillz + 1))) for i, m in enumerate(moves)]
    tune_out = any(e.stat == "tune_out" for row in active for e in row)
    contest = [m.pillz + 1 for m in moves] if tune_out else attack
    winner = max(range(2), key=lambda i: (contest[i], -cards[i].stars, i == state.leader))
    killshot = [attack[i] >= 2 * attack[1-i] for i in range(2)]
    # Official Perfect pillz: one pill fewer would have lost the round.
    perfect = [winner == i and contest[i] - contest[1-i] < (1 if tune_out else max(1, power[i]))
               for i in range(2)]
    def late_ok(owner, e):
        return (("killshot" not in e.gates or killshot[owner])
                and ("perfect" not in e.gates or perfect[owner]))
    active = [tuple(e for e in row if e.stat not in POST_ROUND or late_ok(i, e))
              for i, row in enumerate(active)]
    life = [p.life for p in state.players]
    pillz = [p.pillz - m.pillz - 3 * m.fury for p, m in zip(state.players, moves)]
    damage = max(0, stat(winner, "damage", bases["damage"][winner] + 2 * moves[winner].fury))
    loser = 1 - winner
    life[loser] = max(0, life[loser] - damage)
    def triggered(owner, e):
        return (owner != winner if e.condition == "defeat" else
                True if e.condition == "victory or defeat" else
                owner == winner)
    if life[loser] == 0 and any(e.stat == "life" and "reanimate" in e.gates and triggered(loser, e)
                                for e in active[loser]):
        life[loser] = 1
    installs = []
    for owner in range(2):
        for e in active[owner]:
            if e.stat not in POST_ROUND or not triggered(owner, e):
                continue
            targets = (0, 1) if e.both else (1 - owner,) if e.opponent else (owner,)
            if e.stat in PERSISTENT:
                kind = PERSISTENT[e.stat][0]
                for target in targets:
                    installs.append((target, Persistent(
                        e.stat, PERSISTENT[e.stat][1],
                        e.amount if kind in {"life", "both"} else 0,
                        e.amount if kind in {"pillz", "both"} else 0,
                        e.minimum, e.maximum, owner)))
                continue
            if e.stat=="recover_pillz":
                # The attack allocation includes the free pill. Official
                # recovery rounds the stated fraction down, minimum one.
                for target in targets:
                    pillz[target]+=max(e.minimum,(moves[target].pillz+1)*e.amount//e.divisor)
                continue
            if e.multiplier=="damage_dealt":
                e=replace(e,amount=e.amount*damage,multiplier="none")
            values = life if e.stat == "life" else pillz
            for target in targets:
                values[target] = max(0, _modify(values[target], e))
    # Running effects: those already active tick first, unless replaced by an
    # immediate effect (Toxin/Regen/Dope/Consume/Mindwipe tick this round). A
    # Cancel Opp. Life/Pillz Modif. silences the opponent's ticks this round.
    def tick(target, p):
        if p.life and "life" not in cancelled[p.owner]:
            life[target] = max(0, _bounded(life[target], p.life, p.minimum, p.maximum))
        if p.pillz and "pillz" not in cancelled[p.owner]:
            pillz[target] = max(0, _bounded(pillz[target], p.pillz, p.minimum, p.maximum))
    running = []
    for target, player in enumerate(state.players):
        slots = {p.slot: p for p in player.effects}
        new = {}
        for t, p in installs:
            if t == target:
                new[p.slot] = p
        for slot in sorted(set(slots) | set(new)):
            fresh = new.get(slot)
            if fresh is not None and PERSISTENT[fresh.kind][2]:
                tick(target, fresh)
            elif slot in slots:
                tick(target, slots[slot])
            if fresh is not None:
                slots[slot] = fresh
        running.append(tuple(slots[s] for s in sorted(slots)))
    players = tuple(replace(p, life=life[i], pillz=pillz[i], used=p.used + (moves[i].card,),
                            last_won=i == winner, effects=running[i])
                    for i, p in enumerate(state.players))
    return State(players, 1 - state.leader, state.round + 1, state.day)


def projected(player: Player):
    """Life and pillz after running effects tick for every remaining round."""
    life, pillz = player.life, player.pillz
    for _ in range(len(player.hand) - len(player.used)):
        for p in player.effects:
            if p.life:
                life = max(0, _bounded(life, p.life, p.minimum, p.maximum))
            if p.pillz:
                pillz = max(0, _bounded(pillz, p.pillz, p.minimum, p.maximum))
    return life, pillz


def evaluate(state: State) -> float:
    a, b = state.players
    if state.terminal:
        return float((a.life > b.life) - (a.life < b.life)) * 10000
    # Explicit heuristic at a one-round horizon; not a claimed match win rate.
    # Running effects are projected over the rounds still to play.
    (la, pa), (lb, pb) = projected(a), projected(b)
    if la == 0 and lb > 0:
        return -5000.0
    if lb == 0 and la > 0:
        return 5000.0
    reserve = [sum(c.damage for i, c in enumerate(p.hand) if i not in p.used) for p in (a, b)]
    return la - lb + .65 * (pa - pb) + .15 * (reserve[0] - reserve[1])
