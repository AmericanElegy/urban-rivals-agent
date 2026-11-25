"""Perfect, Killshot, Stop:, Backlash, Impose, Cancel Life/Pillz Modif. and
abbreviated card text. Rules: urban-rivals.com/game/rules (Killshot, Stop:,
Backlash, Impose, Cancel); Perfect as described by the player: the card wins
with exactly the Pillz needed."""
import unittest

from urban_rivals.engine import Card, Move, Player, State, parse_effect, resolve


def card(name, power, damage, clan="X", ability="", bonus="", stars=3):
    return Card(name, power, damage, stars, clan, parse_effect(ability), parse_effect(bonus))


FILLER = card("Filler", 1, 0, "Y")


def start(mine, theirs, life=12, pillz=12):
    n = max(len(mine), len(theirs))
    mine = tuple(mine) + (FILLER,) * (n - len(mine))
    theirs = tuple(theirs) + (FILLER,) * (n - len(theirs))
    return State((Player(mine, life, pillz), Player(theirs, life, pillz)))


class PerfectTests(unittest.TestCase):
    def setUp(self):
        self.hula = card("Hula", 8, 2, "Freaks", ability="Perfect: Consume 1, Min 3")
        self.opp = card("Opp", 7, 0, "Y", stars=4)

    def test_exact_pillz_triggers(self):
        # Opp attacks 7*(2+1)=21. Hula needs 2 paid pillz: 8*3=24 > 21, 8*2=16 loses.
        s = start((self.hula, FILLER), (self.opp, FILLER))
        after = resolve(s, Move(0, 2), Move(0, 2))
        self.assertEqual(after.players[1].effects, (("consume", 1, 3),))
        self.assertEqual(after.players[1].pillz, 12 - 2 - 1)   # Consume ticks at once

    def test_overpaying_does_not_trigger(self):
        s = start((self.hula, FILLER), (self.opp, FILLER))
        after = resolve(s, Move(0, 5), Move(0, 2))
        self.assertEqual(after.players[1].effects, ())

    def test_zero_paid_win_is_perfect(self):
        s = start((self.hula, FILLER), (card("Tiny", 1, 0, "Y"), FILLER))
        self.assertTrue(resolve(s, Move(0, 0), Move(0, 0)).players[1].effects)


class KillshotTests(unittest.TestCase):
    def test_needs_double_attack(self):
        raoul = card("Raoul", 7, 4, ability="Killshot: +5 Life")
        s = start((raoul, FILLER), (card("Opp", 7, 0, "Y"), FILLER), life=10)
        self.assertEqual(resolve(s, Move(0, 1), Move(0, 0)).players[0].life, 15)  # 14 vs 7
        self.assertEqual(resolve(s, Move(0, 0), Move(0, 0)).players[0].life, 10)  # 7 vs 7 tie path


class StopConditionTests(unittest.TestCase):
    def test_stop_prefix_only_when_ability_is_stopped(self):
        stopper = card("Stopper", 5, 1, "Y", ability="Stop Opp. Ability")
        stopped = card("Stopped", 5, 5, ability="Stop: Power +3")
        s = start((stopped, FILLER), (stopper, card("Plain", 5, 1, "Z")))
        # Against a Stop Opp. Ability: 8 power beats 5.
        self.assertTrue(resolve(s, Move(0, 0), Move(0, 0)).players[0].last_won)
        # Against a plain card the Stop: effect stays off (5 vs 5, fewer stars... equal -> leader).
        plain_state = start((stopped, FILLER), (card("Plain", 5, 1, "Z", stars=2), FILLER))
        self.assertFalse(resolve(plain_state, Move(0, 0), Move(0, 0)).players[0].last_won)


class BacklashImposeCancelTests(unittest.TestCase):
    def test_backlash_costs_own_life_on_victory(self):
        gork = card("Gork", 9, 3, ability="Backlash: - 2 Life Min 2")
        after = resolve(start((gork, FILLER), (FILLER, FILLER)), Move(0, 0), Move(0, 0))
        self.assertEqual((after.players[0].life, after.players[1].life), (10, 9))

    def test_backlash_poison_lands_on_self(self):
        gork = card("Gork", 9, 3, ability="Backlash: Poison 1, Min 3")
        after = resolve(start((gork, FILLER), (FILLER, FILLER)), Move(0, 0), Move(0, 0))
        self.assertEqual(after.players[0].effects, (("poison", 1, 3),))

    def test_power_impose(self):
        imposer = card("Imposer", 2, 1, ability="Power Impose")
        strong = card("Strong", 9, 5, "Y", stars=4)
        after = resolve(start((imposer, FILLER), (strong, FILLER)), Move(0, 0), Move(0, 0))
        self.assertTrue(after.players[0].last_won)   # 2 vs imposed 2, fewer stars wins

    def test_cancel_life_pauses_opponent_poison_for_the_round(self):
        sylth = card("Sylth", 9, 0, ability="Poison 3, Min 1")
        canceller = card("Canceller", 1, 0, "Y", ability="Cancel Opp. Life Modif.")
        s = start((sylth, FILLER, FILLER), (FILLER, canceller, FILLER))
        r1 = resolve(s, Move(0, 0), Move(0, 0))
        r2 = resolve(r1, Move(1, 0), Move(1, 0))
        self.assertEqual(r2.players[1].life, r1.players[1].life)        # paused
        r3 = resolve(r2, Move(2, 0), Move(2, 0))
        self.assertEqual(r3.players[1].life, r2.players[1].life - 3)    # back next round


class AbbreviationTests(unittest.TestCase):
    def test_official_abbreviations_parse(self):
        cases = {
            "Reprisal: -2 Opp Pow. & Dmg,min 2": {("power", -2), ("damage", -2)},
            "-2 Opp Pillz. Min 1": {("pillz", -2)},
            "Vict. Or Def.: -1 Opp Life & Pillz Min 1": {("life", -1), ("pillz", -1)},
            "Courage; -2 Opp Pillz. Min 1": {("pillz", -2)},
            "Revenge: Protec. Power And Dmg": {("protect_power", 0), ("protect_damage", 0)},
            "Cancel Opp. Pow/dam Mod.": {("cancel_power", 0), ("cancel_damage", 0)},
            "Stop: Atk. +12": {("attack", 12)},
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual({(e.stat, e.amount) for e in parse_effect(text)}, expected)


if __name__ == "__main__":
    unittest.main()
