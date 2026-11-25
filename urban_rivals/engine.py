"""Immutable deterministic classic-game core; unsupported effects fail closed.

Pillz in Move are *paid* pillz. The free pill is added only to attack.
Original hands are retained so played cards continue to count for clan bonuses.
"""
from dataclasses import dataclass, replace
import re
from functools import lru_cache

ENGINE_REVISION="mechanics-v3"

# Rule sources: official rules page (urban-rivals.com/game/rules) and the
# official per-card ability descriptions stored in data/card_reference.json.
CONDITIONS={"always","courage","reprisal","confidence","revenge","defeat",
            "victory or defeat","day","night","unison","disunion","symmetry",
            "asymmetry","bet_over","bet_under","perfect","killshot","stop",
            # Clan conditions; the clans come from the official description.
            "after","versus","infiltrates"}
CLAN_CONDITIONS={"after","versus","infiltrates"}
# Decided after the fight: these only carry Life/Pillz (incl. persistent) effects.
POST_ROUND={"defeat","victory or defeat","perfect","killshot"}
MULTIPLIER_PREFIXES={"support","brawl","growth","degrowth","equalizer"}
# Hand-level passives: active for the whole match while the card is in the deck.
PASSIVES={"tie_break","bypass","unconditional"}
NEEDS_CONDITION={"courage","reprisal","confidence","revenge"}

# Card text abbreviations seen in official data -> canonical wording.
_ABBREVIATIONS=(
    (r"\bVict\.?\s+Or\s+Def(?:eat)?\.?", "Victory Or Defeat"),
    (r"\bConf\.", "Confidence"), (r"\bRepris\.", "Reprisal"), (r"\bRev\.", "Revenge"),
    (r"\bAsymm?\.", "Asymmetry"), (r"\bBrwl\.", "Brawl"),
    (r"\bRecov?\.", "Recover"), (r"\bRec\.", "Recover"), (r"\bCanc\.", "Cancel"),
    (r"\bProt(?:ec|ect)?\.\s*:?\s*", "Protection: "),
    (r"\bPow\.?\s*/\s*(?=(?:Life|Pillz)\s+(?:Lost|Left))", "Power Per "),
    (r"\bPow\b\.?", "Power"), (r"\bDmg\b\.?", "Damage"), (r"\bDam\b\.?", "Damage"),
    (r"\bAt[tk]\b\.?", "Attack"), (r"\bMod\b\.?", "Modif"),
    (r"\s*&\s*", " And "), (r"\s*/\s*", " And "),
    (r"\b(Pillz|Life)\.\s*(Min|Max)\b", r"\1, \2"), (r";", ":"),
    (r",\s*Per\s+Round", " Per Round"),
    (r"([+-])\s+(\d)", r"\1\2"),
    (r"(\d+)\s+(Pillz|Life|Power|Damage)\s+Opp\.?(?=\s|,|$)", r"\1 Opp \2"),
    (r"\bBonus\s+Protection\b", "Protection: Bonus"),
    (r"\bCancel\s+(Power|Damage|Attack|Life|Pillz)\b", r"Cancel Opp \1"),
)


def normalize_text(text: str) -> str:
    for pattern, replacement in _ABBREVIATIONS:
        text = re.sub(pattern, replacement, text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()


def _clan_list(text: str) -> list[str]:
    return [c.strip() for c in re.split(r",\s*|\s+or\s+|\s+o\s+|\s+and\s+", text) if c.strip()]


def annotate_text(title: str, description: str) -> str:
    """Write the clans an official description names into the card text.

    "After : Power +2" + "...played a Bangers, Junkz or Uppers character in
    the previous round" -> "After [Bangers|Junkz|Uppers]: Power +2".
    Versus names clans in the opponent's hand; some Oculus abilities only work
    when the card infiltrates named clans.
    """
    text = (title or "").strip()
    desc = description or ""
    def bracket(keyword, pattern):
        nonlocal text
        match = re.search(pattern, desc)
        if match and re.match(rf"\s*{keyword}\s*:", text, re.I) is None and keyword != "Infiltrates":
            return
        if match:
            clans = "|".join(_clan_list(match[1]))
            if keyword == "Infiltrates":
                text = f"Infiltrates [{clans}]: {text}"
            else:
                text = re.sub(rf"^\s*{keyword}\s*:", f"{keyword} [{clans}]:", text, count=1, flags=re.I)
    bracket("After", r"played (?:a|an) (.+?) character in the previous round")
    bracket("Versus", r"there's (?:a|an) (.+?) in your opponent's hand")
    if "Infiltrates" not in text:
        bracket("Infiltrates", r"only activates if .+? infiltrates (.+?)\.")
    return text


# Persistent end-of-round effects. Poison/Heal(Care) tick at the end of each
# round AFTER the one they were won in; Toxin/Regen and the Pillz forms
# Consume/Dope also tick straight after their own round (official rules).
# Official card texts: "If two poisons or toxins are applied, the second will
# replace the first as soon as the latter takes effect" (likewise heal/regen),
# so those share a slot. Combust also drains Pillz with Poison timing ("rot").
PERSISTENT={"poison":("life",True,False),"toxin":("life",True,True),
            "consume":("pillz",True,True),"heal":("life",False,False),
            "regen":("life",False,True),"dope":("pillz",False,True),
            "rot":("pillz",True,False)}
SLOTS={"poison":"life-","toxin":"life-","heal":"life+","regen":"life+",
       "consume":"pillz-","dope":"pillz+","rot":"pillz-later"}

STATS={"power", "damage", "attack", "life", "pillz", "stop_ability",
       "protect_power", "protect_damage", "protect_attack",
       "protect_ability", "protect_bonus", "exchange_power",
       "exchange_damage", "tune_out", "stop_bonus",
       "cancel_power", "cancel_damage", "cancel_attack",
       "copy_ability", "copy_bonus", "copy_power",
       "copy_damage", "recover_pillz", *PERSISTENT,
       "impose_power", "impose_damage", "cancel_life", "cancel_pillz",
       "ko", *PASSIVES}
MULTIPLIERS={"none", "support", "brawl", "growth", "degrowth", "equalizer", "opp_power",
             "opp_damage", "damage_dealt", "life_left", "pillz_left", "life_lost", "pillz_lost"}


def condition_parts(condition: str) -> set[str]:
    return set(condition.split("+"))


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
    clans: tuple[str, ...] = ()
    both: bool = False      # "Players"/"Cards"/Xantiax: both sides
    team: bool = False      # "Team:": every card in your deck has it
    revive: bool = False    # Reanimate: no KO from opposing damage

    def __post_init__(self):
        parts = condition_parts(self.condition)
        if self.stat not in STATS:
            raise ValueError(f"Unsupported effect stat: {self.stat}")
        if not parts <= CONDITIONS:
            raise ValueError(f"Unsupported condition: {self.condition}")
        if bool(parts & CLAN_CONDITIONS) != bool(self.clans):
            raise ValueError("Clan conditions need the official clan list")
        if self.multiplier not in MULTIPLIERS:
            raise ValueError(f"Unsupported multiplier: {self.multiplier}")
        if self.multiplier=="damage_dealt" and (self.stat not in {"life","pillz"} or self.amount<=0 or self.opponent or parts & {"defeat","victory or defeat"}):
            raise ValueError("Per-damage recovery requires a positive own resource effect on victory")
        if self.minimum < 0 or self.maximum < self.minimum:
            raise ValueError("Invalid effect bounds")
        if type(self.threshold) is not int or self.threshold < 0 or (
                not parts & {"bet_over", "bet_under"} and self.threshold != 0):
            raise ValueError("Invalid Bet threshold")
        if type(self.divisor) is not int or self.divisor < 1:
            raise ValueError("Invalid effect divisor")
        if self.stat=="recover_pillz" and (self.amount<1 or self.opponent
                or not parts & {"defeat","victory or defeat"}
                or self.multiplier!="none"):
            raise ValueError("Pillz recovery requires an own defeat-based fraction")
        if self.stat!="recover_pillz" and self.divisor!=1:
            raise ValueError("Only Pillz recovery uses a divisor")
        if parts & POST_ROUND and self.stat not in {"life", "pillz", "ko", "recover_pillz", *PERSISTENT}:
            raise ValueError("Post-round conditions require life or pillz effects")
        if self.stat.startswith(("protect_", "exchange_", "cancel_", "copy_", "impose_")) and (
                self.amount != 0 or self.opponent or self.multiplier != "none"
                or parts & {"defeat", "victory or defeat"}):
            raise ValueError("Unsupported protection/exchange/cancel parameters")


def parse_effect(text: str) -> tuple[Effect, ...]:
    """Parse a deliberately small, auditable subset of English card text.

    Condition prefixes chain ("Day: Courage: Attack +20"); every condition must
    hold. Unknown wording fails closed (ValueError).
    """
    text = normalize_text(text.strip()).rstrip(".")
    if text.lower() in ("", "none", "no ability", "no bonus"):
        return ()
    # Infiltrated: handled by clan logic. Counter-attack: play order is read
    # from the screen, so the engine needs nothing.
    if re.fullmatch(r"Infiltrated|Counter-?\s*attack|Cancel\s+Leader", text, re.I):
        return ()
    passive = {"tie-break": "tie_break", "bypass": "bypass",
               "remove ability conditions": "unconditional"}.get(text.lower())
    if passive:
        return (Effect(passive, 0),)
    ko = {"perfection": "perfect", "sinister symmetry": "symmetry",
          "fatal killshot": "killshot"}.get(text.lower())
    if ko:
        return (Effect("ko", 0, True, condition=ko),)
    parts, clans, multiplier, threshold = [], (), "none", 0
    backlash = team = revive = both = False
    while True:
        match = re.match(r"([^:\[\]]+?)\s*(?:\[([^\]]*)\])?\s*:\s*(.+)$", text)
        if not match:
            break
        head = match[1].strip()
        key = head.lower()
        if key in ("protection", "copy"):
            break
        bet = re.fullmatch(r"Bet\s*([<>])\s*(\d+)\s*Pillz", head, re.I)
        if bet:
            parts.append("bet_over" if bet[1] == ">" else "bet_under")
            threshold = int(bet[2])
        elif key in MULTIPLIER_PREFIXES:
            if multiplier != "none":
                raise ValueError("Two multipliers on one effect are not supported")
            multiplier = key
        elif key in CLAN_CONDITIONS:
            if not match[2] or clans:
                raise ValueError(f"{head} needs exactly one official clan list")
            parts.append(key)
            clans = tuple(c.strip() for c in match[2].split("|") if c.strip())
        elif key == "backlash":
            backlash = True
        elif key == "team":
            team = True
        elif key == "reanimate":
            # Official: if the card loses, +X Life at round end and the player
            # cannot be KO'd by the opposing damage.
            revive = True
            parts.append("defeat")
        elif key == "xantiax":
            # Official: win or lose, both players lose X Life (Min).
            parts.append("victory or defeat")
            both = True
        elif key in CONDITIONS:
            parts.append(key)
        else:
            raise ValueError(f"Unsupported condition: {head}")
        text = match[3].strip()
    condition = "+".join(dict.fromkeys(parts)) or "always"
    effects = _parse_core(text, condition, multiplier, threshold, clans)
    result = []
    for e in effects:
        if backlash:
            if e.stat not in {"life", "pillz", *PERSISTENT}:
                raise ValueError("Only Backlash Life/Pillz/Poison costs are supported")
            e = replace(e, opponent=False,
                        amount=-abs(e.amount) if e.stat in {"life", "pillz"} else e.amount)
        if both and not e.both:
            e = replace(e, both=True, opponent=False)
        result.append(replace(e, clans=clans, team=team, revive=revive or e.revive))
    return tuple(result)


def _parse_core(text, condition, multiplier, threshold, clans=()):
    def make(stat, amount, opponent=False, minimum=0, maximum=10000, **extra):
        return Effect(stat, amount, opponent, minimum, maximum, condition, extra.pop("multiplier", multiplier),
                      threshold, clans=clans, **extra)

    def with_parts(*more):
        return "+".join(dict.fromkeys([p for p in condition.split("+") if p != "always"] + list(more))) or "always"

    if re.fullmatch(r"Copy:?\s*Opp\.?\s+Ability", text, re.I) and multiplier=="none":
        return (make("copy_ability",0),)
    if re.fullmatch(r"Copy:?\s*Opp\.?\s+Bonus", text, re.I) and multiplier=="none":
        return (make("copy_bonus",0),)
    match=re.fullmatch(r"Copy:?\s*Opp\.?\s+(Power|Damage)", text, re.I)
    if match:
        return (make("copy_"+match[1].lower(),0),)
    if re.fullmatch(r"Copy:\s*Power\s+And\s+Damage\s+Opp\.?",text,re.I):
        return (make("copy_power",0), make("copy_damage",0))
    match = re.fullmatch(r"Cancel\s+Opp\.?\s+(Power(?:\s+And\s+Damage)?|Damage|Attack)\s+Modif", text, re.I)
    if match:
        return tuple(make("cancel_"+stat,0) for stat in re.split(r"\s+and\s+",match[1].lower()))
    match = re.fullmatch(r"(Power|Damage)\s+Impose", text, re.I)
    if match:
        return (make("impose_" + match[1].lower(), 0),)
    match = re.fullmatch(r"Cancel\s+Opp\.?\s+(Pillz\s+And\s+Life|Life|Pillz)\s+Modif", text, re.I)
    if match:
        return tuple(make("cancel_" + stat, 0) for stat in re.split(r"\s+and\s+", match[1].lower()))
    if re.fullmatch(r"Stop\s+Opp\.?\s+Bonus", text, re.I):
        return (make("stop_bonus",0,True),)
    match=re.fullmatch(r"Recover\s+(\d+)\s+Pillz\s+Out\s+Of\s+(\d+)",text,re.I)
    if match:
        if multiplier!="none" or not condition_parts(condition) <= {"always","defeat","victory or defeat","unison","day"}:
            raise ValueError("Combined Pillz recovery conditions are not supported")
        parts=condition_parts(condition)
        cond=condition if parts & {"defeat","victory or defeat"} else with_parts("defeat")
        return (Effect("recover_pillz",int(match[1]),minimum=1,condition=cond,divisor=int(match[2]),clans=clans),)
    match=re.fullmatch(r"([+]\d+)\s+(Life|Pillz)\s+Per\s+Damage(?:,?\s*Max\.?\s*(\d+))?",text,re.I)
    if match:
        if multiplier!="none":
            raise ValueError("Combined per-damage multipliers are not supported")
        return (make(match[2].lower(),int(match[1]),maximum=int(match[3] or 10000),multiplier="damage_dealt"),)
    match=re.fullmatch(r"([+]\d+)\s+(Life|Pillz)\s+Per\s+Opp\.?\s+(Damage|Power)",text,re.I)
    if match:
        return (make(match[2].lower(),int(match[1]),multiplier="opp_"+match[3].lower()),)
    match = re.fullmatch(r"([+]\d+)\s+Attack\s+Per\s+Opp\.?\s+(Power|Damage)",text,re.I)
    if match:
        return (make("attack",int(match[1]),multiplier="opp_"+match[2].lower()),)
    match = re.fullmatch(r"([+-]\d+)\s+(Opp\.?\s+)?(Power|Damage|Attack)\s+Per\s+(Life|Pillz)\s+(Left|Lost)"
                         r"(?:,?\s*(Min|Max)\.?\s*(\d+))?", text, re.I)
    if match:
        if multiplier!="none":
            raise ValueError("Combined resource multipliers are not supported")
        if match[2] and int(match[1]) > 0:
            raise ValueError("Raising the opponent's stat per resource is not an official form")
        bound=(match[6] or "").lower()
        return (make(match[3].lower(),int(match[1]),bool(match[2]),
                     int(match[7]) if bound=="min" else 0,
                     int(match[7]) if bound=="max" else 10000,
                     multiplier=f"{match[4].lower()}_{match[5].lower()}"),)
    match = re.fullmatch(r"Protection\s*:\s*(Cards\s+)?(Power|Damage|Attack|Ability|Bonus|Power\s+And\s+Damage)", text, re.I)
    if match:
        if multiplier != "none":
            raise ValueError("Protection does not support numeric multipliers")
        return tuple(make("protect_" + stat, 0, both=bool(match[1]))
                     for stat in re.split(r"\s+and\s+", match[2].lower()))
    match = re.fullmatch(r"(Power|Damage|Power\s+And\s+Damage)\s+Exchange", text, re.I)
    if match:
        if multiplier != "none":
            raise ValueError("Exchange does not support numeric multipliers")
        return tuple(make("exchange_" + stat, 0) for stat in re.split(r"\s+and\s+", match[1].lower()))
    if re.fullmatch(r"Stop\s+Opp\.?\s+Ability", text, re.I):
        return (make("stop_ability", 0, True),)
    # Corrupt (official): win or lose, the card's own player loses X Life (Min).
    match = re.fullmatch(r"Corrupt\s+(\d+)\s*,?\s*Min\.?\s*(\d+)", text, re.I)
    if match:
        return (Effect("life", -int(match[1]), False, int(match[2]), 10000,
                       with_parts("victory or defeat"), multiplier, threshold, clans=clans),)
    match = re.fullmatch(r"(Players\s+)?(Poison|Toxin|Consume|Corrosion|Mindwipe|Combust)\s+(\d+)\s*,?\s*Min\.?\s*(\d+)", text, re.I)
    if match:
        both=bool(match[1])
        kind=match[2].lower()
        amount,floor=int(match[3]),int(match[4])
        if kind=="corrosion":
            # Official: a Poison multiplied by the round the card was played in.
            if multiplier!="none":
                raise ValueError("Corrosion with another multiplier is not supported")
            return (make("poison",amount,not both,floor,multiplier="growth",both=both),)
        kinds={"mindwipe":("toxin","consume"),"combust":("poison","rot")}.get(kind,(kind,))
        return tuple(make(k,amount,not both,floor,both=both) for k in kinds)
    match = re.fullmatch(r"(Heal|Care|Regen|Regeneration|Dope|Repair)\s+(\d+)\s*,?\s*Max\.?\s*(\d+)", text, re.I)
    if match:
        kind = {"care": "heal", "regeneration": "regen"}.get(match[1].lower(), match[1].lower())
        # Official Repair: Life AND Pillz, persisting like Regen/Dope.
        kinds = ("regen", "dope") if kind == "repair" else (kind,)
        return tuple(make(k, int(match[2]), False, maximum=int(match[3])) for k in kinds)
    if re.fullmatch(r"Tune\s+Out", text, re.I) and condition == "always":
        return (Effect("tune_out", 0),)
    stat_words = r"(?:Power|Damage|Attack|Life|Pillz)(?:\s+And\s+(?:Power|Damage|Attack|Life|Pillz))?"
    patterns = (
        rf"(?:(?P<who>Cards|Players)\s+|(?P<opp>Opp\.?)\s+)?(?P<stat>{stat_words})\s*(?P<amount>[+-]\s*\d+)",
        rf"(?P<amount>[+-]\s*\d+)\s*(?:(?P<opp>Opp\.?)\s*|(?P<who>Players|Cards)\s+)?(?P<stat>{stat_words})",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern + r"(?:,?\s*(?P<bound>Min|Max)\.?\s*(?P<limit>\d+))?", text, re.I)
        if match:
            values = match.groupdict()
            stats = re.split(r"\s+and\s+", values["stat"].lower())
            if condition_parts(condition) & POST_ROUND and any(stat not in {"life", "pillz"} for stat in stats):
                raise ValueError("Post-round conditions require life or pillz effects")
            both = bool(values.get("who"))
            return tuple(make(stat, int(values["amount"].replace(" ", "")),
                              bool(values.get("opp")),
                              int(values["limit"]) if (values["bound"] or "").lower() == "min" else 0,
                              int(values["limit"]) if (values["bound"] or "").lower() == "max" else 10000,
                              both=both) for stat in stats)
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
    # Match start values, for "Per Life Lost" / "Per Pillz Lost" (official:
    # counted since the start of the match).
    start_life: int = 12
    start_pillz: int = 12

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


def effective_clans(hand) -> tuple[str, ...]:
    """Oculus Infiltrated (official): one Oculus takes the clan of the only
    other clan in the hand, or of the sole card when two other clans are
    present. Three other clans, or more than one Oculus: no effect."""
    clans = [c.clan for c in hand]
    oculus = [i for i, c in enumerate(clans) if c.casefold() == "oculus"]
    if len(oculus) != 1:
        return tuple(clans)
    others = [c for c in clans if c.casefold() != "oculus"]
    counts = {c: others.count(c) for c in others}
    target = None
    if len(counts) == 1:
        target = others[0]
    elif len(counts) == 2:
        singles = [c for c, n in counts.items() if n == 1]
        target = singles[0] if len(singles) == 1 else None
    if target:
        clans[oculus[0]] = target
    return tuple(clans)


def _same(a: str, b: str) -> bool:
    return a.casefold() == b.casefold()


def hand_passives(p: Player) -> set[str]:
    """Deck-wide passives (Tie-break, Bypass, Remove Ability Conditions)."""
    return {e.stat for c in p.hand for e in c.ability if e.stat in PASSIVES}


def team_effects(p: Player) -> tuple[Effect, ...]:
    """'Team:' abilities reach every card in the deck. Official Cancel Leader:
    Leader abilities are deactivated with more than one Leader in the team."""
    leaders = sum(_same(c.clan, "Leader") for c in p.hand)
    return tuple(e for c in p.hand for e in c.ability
                 if e.team and not (leaders > 1 and _same(c.clan, "Leader")))


def resolve(state: State, first: Move, second: Move) -> State:
    """Resolve indexed side-0 and side-1 moves, independent of leader order."""
    moves = (first, second)
    for side, move in enumerate(moves):
        if not is_legal(state, side, move):
            raise ValueError(f"Illegal move for side {side}: {move}")
    players = state.players
    cards = [p.hand[m.card] for p, m in zip(players, moves)]
    clans = [effective_clans(p.hand) for p in players]
    passives = [hand_passives(p) for p in players]

    def bonus_on(side, index):
        own = clans[side][index]
        return "bypass" in passives[side] or sum(_same(x, own) for x in clans[side]) >= 2

    def copy_condition(side, e):
        """Pre-fight conditions on a Copy (e.g. "Reprisal: Copy Opp. Bonus")."""
        p = players[side]
        checks = {"always": True, "courage": side == state.leader, "reprisal": side != state.leader,
                  "confidence": p.last_won is True, "revenge": p.last_won is False,
                  "day": state.day is True, "night": state.day is False,
                  "symmetry": moves[side].card == moves[1-side].card,
                  "asymmetry": moves[side].card != moves[1-side].card,
                  "unison": all(_same(x, clans[side][moves[side].card]) for x in clans[side]),
                  "bet_over": moves[side].pillz + 1 > e.threshold,
                  "bet_under": moves[side].pillz + 1 < e.threshold}
        parts = condition_parts(e.condition)
        if not parts <= set(checks):
            raise ValueError(f"Copy under {e.condition} is not verified")
        return all(checks[part] for part in parts)

    # Expand from the original opposing ability, before checking conditions.
    # The replacement retains the copying source (ability or bonus); conditions
    # and multipliers are evaluated from the copier's side, never the donor's.
    sources=[]
    for side,c in enumerate(cards):
        other=cards[1-side]
        other_bonus_on=bonus_on(1-side,moves[1-side].card)
        def expand(row):
            result=[]
            for e in row:
                if e.stat not in {"copy_ability","copy_bonus"}:
                    result.append(e)
                    continue
                if (e.amount,e.multiplier,e.opponent)!=(0,"none",False):
                    raise ValueError("Modified effect-copy is not verified")
                if not copy_condition(side, e):
                    continue
                if other.clan.casefold() in {"leader","genesis"}:
                    continue
                donor=other.ability if e.stat=="copy_ability" else other.bonus if other_bonus_on else ()
                if any(x.stat in {"copy_ability","copy_bonus"} for x in donor):
                    raise ValueError("Recursive effect-copy is not verified")
                result.extend(donor)
            return tuple(result)
        own_ability=tuple(e for e in c.ability if not e.team and e.stat not in PASSIVES)
        ability=expand(own_ability)+team_effects(players[side])
        sources.append((ability,expand(c.bonus) if bonus_on(side,moves[side].card) else ()))
    active = []
    ability_sizes = []
    for side, (p, c) in enumerate(zip(players, cards)):
        ability,bonus=sources[side]
        effects = ability + bonus
        if state.day is None and any(condition_parts(e.condition) & {"day", "night"} for e in effects):
            raise ValueError("Day/Night effects require the observed game clock")
        my_clan = clans[side][moves[side].card]
        unison = all(_same(x, my_clan) for x in clans[side])
        opp = players[1-side]
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
                       "support": sum(_same(x, my_clan) for x in clans[side]),
                       "brawl": sum(_same(x, clans[1-side][moves[1-side].card]) for x in clans[1-side]),
                       "equalizer": cards[1-side].stars,
                       "opp_power": cards[1-side].power, "opp_damage": cards[1-side].damage,
                       "life_left":p.life,"pillz_left":p.pillz,
                       "life_lost":max(0,p.start_life-p.life),
                       "pillz_lost":max(0,p.start_pillz-p.pillz),
                       "damage_dealt":1}
        def enabled(e, is_ability):
            for part in condition_parts(e.condition):
                if is_ability and part in NEEDS_CONDITION and "unconditional" in passives[side]:
                    continue
                # Bets count the attack allocation plus its free pill, not Fury's
                # separate three-pill cost or the player's remaining reserve.
                if part == "bet_over":
                    ok = moves[side].pillz + 1 > e.threshold
                elif part == "bet_under":
                    ok = moves[side].pillz + 1 < e.threshold
                elif part == "after":
                    # Official: a card of a named clan was played last round;
                    # an Oculus never counts, even infiltrated.
                    ok = bool(p.used) and any(_same(p.hand[p.used[-1]].clan, k) for k in e.clans)
                elif part == "versus":
                    ok = any(_same(x.clan, k) for x in opp.hand for k in e.clans)
                elif part == "infiltrates":
                    ok = _same(c.clan, "Oculus") and any(_same(my_clan, k) for k in e.clans)
                else:
                    ok = conditions[part]
                if not ok:
                    return False
            return True
        kept_ability = tuple(e for e in ability if enabled(e, True))
        kept_bonus = tuple(e for e in bonus if enabled(e, False))
        active.append(tuple(replace(e, amount=e.amount * multipliers[e.multiplier])
                            for e in kept_ability + kept_bonus))
        ability_sizes.append(len(kept_ability))
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
    def is_stop(e):
        return "stop" in condition_parts(e.condition)
    abilities=[tuple(e for e in active[i][:ability_sizes[i]] if is_stop(e)==blocked[i])
               for i in range(2)]
    bonuses=[tuple(e for e in active[i][ability_sizes[i]:] if not is_stop(e)) for i in range(2)]
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

    def affects(owner, side, e):
        return e.both or (owner != side) == e.opponent

    def stat(side, name, initial):
        result = initial
        protected = any(e.stat == "protect_" + name and (owner == side or e.both)
                        for owner in range(2) for e in active[owner])
        for owner in (side, 1 - side):
            for e in active[owner]:
                if e.stat == name and affects(owner, side, e):
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
    # Official Tie-break: its owner wins equal attacks (cancelled if both have it).
    tie = [("tie_break" in passives[i]) and ("tie_break" not in passives[1-i]) for i in range(2)]
    def ranking(values):
        return max(range(2), key=lambda i: (values[i], tie[i], -cards[i].stars, i == state.leader))
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
        parts = condition_parts(e.condition)
        if "defeat" in parts:
            result = owner != winner
        elif "victory or defeat" in parts:
            result = True
        else:
            result = owner == winner
        if "perfect" in parts and not perfect:
            return False
        if "killshot" in parts and not killshot:
            return False
        return result
    life = [p.life for p in players]
    pillz = [p.pillz - m.pillz - 3 * m.fury for p, m in zip(players, moves)]
    damage = max(0, stat(winner, "damage", bases["damage"][winner] + 2 * moves[winner].fury))
    life[loser] = max(0, life[loser] - damage)
    # A KO by damage is final, except that Reanimate (official) prevents it.
    revived = any(e.revive and triggered(loser, e) for e in active[loser])
    knocked = [life[i] == 0 and i == loser and not revived for i in range(2)]

    def change(target, resource, e):
        values = life if resource == "life" else pillz
        if resource == "life" and knocked[target] and e.amount > 0:
            return
        values[target] = max(0, _modify(values[target], e))

    for owner in range(2):
        for e in active[owner]:
            if e.stat == "ko" and triggered(owner, e):
                life[1 - owner] = 0
                knocked[1 - owner] = True
                continue
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
                targets = (0, 1) if e.both else ((1 - owner) if e.opponent else owner,)
                for target in targets:
                    change(target, e.stat, e)
    # Lingering effects. Same-slot effects replace each other "as soon as the
    # latter takes effect" (official card texts), so an old effect does not
    # also tick in a round where an immediate replacement ticks.
    new_effects = []
    for owner in range(2):
        for e in active[owner]:
            if e.stat not in PERSISTENT or not triggered(owner, e) or e.amount <= 0:
                continue
            bound = e.minimum if PERSISTENT[e.stat][1] else e.maximum
            targets = (0, 1) if e.both else ((1 - owner) if e.opponent else owner,)
            for target in targets:
                new_effects.append((target, e.stat, e.amount, bound))
    replaced_now = {(t, SLOTS[k]) for t, k, _, _ in new_effects if PERSISTENT[k][2]}
    lingering = [{SLOTS[k]: (k, a, b) for k, a, b in p.effects} for p in players]

    def tick(target, kind, amount, bound):
        resource, harmful, _ = PERSISTENT[kind]
        e = Effect(resource, -amount if harmful else amount,
                   minimum=bound if harmful else 0, maximum=10000 if harmful else bound)
        change(target, resource, e)

    for target in range(2):
        for slot, (kind, amount, bound) in lingering[target].items():
            if (target, slot) in replaced_now:
                continue
            resource, harmful, _ = PERSISTENT[kind]
            # Harmful effects on a player came from the opponent; helpful ones are
            # the player's own. Cancel Opp. Life/Pillz Modif. pauses the
            # opponent's for this round only (official rules).
            source = 1 - target if harmful else target
            if resource in cancelled[source]:
                continue
            tick(target, kind, amount, bound)
    for target, kind, amount, bound in new_effects:
        lingering[target][SLOTS[kind]] = (kind, amount, bound)
        if PERSISTENT[kind][2]:
            tick(target, kind, amount, bound)
    after = tuple(replace(p, life=life[i], pillz=pillz[i], used=p.used + (moves[i].card,),
                          last_won=i == winner,
                          effects=tuple(sorted(lingering[i].values())))
                  for i, p in enumerate(players))
    return State(after, 1 - state.leader, state.round + 1, state.day)


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
