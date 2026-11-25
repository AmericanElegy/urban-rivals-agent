"""Poison/Heal/Toxin/Regen/Consume/Dope per the official rules page:
Poison and Heal (Care) tick at the end of each round after the one they were
won in; Toxin/Regen (and Pillz forms Consume/Dope) also tick straight after the
round they were played; a second effect of the same kind replaces the first."""
import unittest

from urban_rivals.engine import Card, Move, Player, State, evaluate, parse_effect, resolve


def card(name, power, damage, clan="X", ability="", bonus=""):
    return Card(name, power, damage, 3, clan, parse_effect(ability), parse_effect(bonus))


def start(mine, theirs, life=12, pillz=12):
    return State((Player(mine, life, pillz), Player(theirs, life, pillz)))


FILLER = card("Filler", 1, 0, "Y")


class PersistentEffectTests(unittest.TestCase):
    def test_poison_ticks_from_the_following_round_down_to_min(self):
        sylth = card("Sylth", 9, 2, ability="Poison 3, Min 1")
        weak = card("Weak", 1, 0, "Y")
        s = start((sylth, FILLER, FILLER, FILLER), (weak, weak, weak, weak), life=12)
        r1 = resolve(s, Move(0, 0), Move(0, 0))
        self.assertEqual(r1.players[1].life, 10)          # damage only, no tick yet
        self.assertEqual(r1.players[1].effects, (("poison", 3, 1),))
        r2 = resolve(r1, Move(1, 0), Move(1, 1))           # we lose round 2
        self.assertEqual(r2.players[1].life, 7)            # poison ticks
        r3 = resolve(r2, Move(2, 0), Move(2, 1))
        self.assertEqual(r3.players[1].life, 4)
        r4 = resolve(r3, Move(3, 0), Move(3, 1))
        self.assertEqual(r4.players[1].life, 1)            # never below Min 1

    def test_poison_only_on_victory(self):
        freak = card("Freak", 1, 2, ability="Poison 2, Min 3")
        strong = card("Strong", 9, 1, "Y")
        s = start((freak, FILLER), (strong, strong))
        self.assertEqual(resolve(s, Move(0, 0), Move(0, 0)).players[1].effects, ())

    def test_toxin_and_consume_tick_immediately(self):
        dr = card("Dr", 9, 0, ability="Toxin 1, Min 0")
        s = start((dr, FILLER), (FILLER, FILLER), life=12)
        self.assertEqual(resolve(s, Move(0, 0), Move(0, 0)).players[1].life, 11)
        eater = card("Eater", 9, 0, ability="Consume 1, Min 4")
        s = start((eater, FILLER), (FILLER, FILLER), pillz=12)
        self.assertEqual(resolve(s, Move(0, 0), Move(0, 2)).players[1].pillz, 9)

    def test_defeat_heal_and_max(self):
        malicia = card("Malicia", 1, 5, ability="Defeat: Heal 1 Max. 13")
        strong = card("Strong", 9, 0, "Y")
        s = start((malicia, FILLER, FILLER), (strong, strong, strong), life=12)
        r1 = resolve(s, Move(0, 0), Move(0, 0))
        self.assertEqual(r1.players[0].effects, (("heal", 1, 13),))
        r2 = resolve(r1, Move(1, 0), Move(1, 0))
        self.assertEqual(r2.players[0].life, 13)
        r3 = resolve(r2, Move(2, 0), Move(2, 0))
        self.assertEqual(r3.players[0].life, 13)          # capped at Max 13

    def test_same_kind_replaces(self):
        a = card("A", 9, 0, ability="Poison 1, Min 0")
        b = card("B", 9, 0, ability="Poison 3, Min 5")
        s = start((a, b, FILLER), (FILLER, FILLER, FILLER))
        r2 = resolve(resolve(s, Move(0, 0), Move(0, 0)), Move(1, 0), Move(1, 0))
        self.assertEqual(r2.players[1].effects, (("poison", 3, 5),))

    def test_freaks_clan_bonus_poison(self):
        hula = card("Hula", 8, 2, "Freaks", bonus="Poison 2, Min 3")
        soushee = card("Soushee", 6, 1, "Freaks", bonus="Poison 2, Min 3")
        s = start((hula, soushee, FILLER, FILLER), (FILLER,) * 4)
        r1 = resolve(s, Move(0, 0), Move(0, 0))
        self.assertEqual(r1.players[1].effects, (("poison", 2, 3),))

    def test_evaluate_credits_pending_ticks(self):
        hula = card("Hula", 8, 2, "Freaks", bonus="Poison 2, Min 3")
        soushee = card("Soushee", 6, 1, "Freaks", bonus="Poison 2, Min 3")
        plain = card("Plain", 8, 2, "Freaks")
        poisoned = resolve(start((hula, soushee, FILLER, FILLER), (FILLER,) * 4), Move(0, 0), Move(0, 0))
        clean = resolve(start((plain, plain, FILLER, FILLER), (FILLER,) * 4), Move(0, 0), Move(0, 0))
        # Three more rounds of Poison 2 are worth about 6 life.
        self.assertAlmostEqual(evaluate(poisoned) - evaluate(clean), 6, delta=.5)


if __name__ == "__main__":
    unittest.main()
