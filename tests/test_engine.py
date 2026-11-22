import unittest
from dataclasses import replace
from urban_rivals.engine import Card, Player, State, Move, Effect, parse_effect, resolve, legal_moves
from urban_rivals.solver import matrix_game, advise


def state(a=None, b=None, pillz=3, leader=0):
    a = a or Card("A", 7, 4, 3, "A")
    b = b or Card("B", 7, 4, 3, "B")
    return State((Player((a,), pillz=pillz), Player((b,), pillz=pillz)), leader)


class EngineTests(unittest.TestCase):
    def test_free_pill_and_stars(self):
        s = state(b=Card("B", 6, 4, 2, "B"))
        self.assertEqual(resolve(s, Move(0, 0), Move(0, 0)).players[1].life, 10)
        s = state(b=Card("B", 7, 4, 2, "B"))
        self.assertEqual(resolve(s, Move(0, 0), Move(0, 0)).players[0].life, 10)

    def test_equal_stars_use_initiative(self):
        for leader in (0, 1):
            after = resolve(state(leader=leader), Move(0, 0), Move(0, 0))
            self.assertEqual(after.players[1-leader].life, 10)

    def test_fury_budget_and_damage(self):
        s = state()
        after = resolve(s, Move(0, 0, True), Move(0, 0))
        self.assertEqual(after.players[0].pillz, 0)
        self.assertEqual(after.players[1].life, 8)
        with self.assertRaises(ValueError):
            resolve(s, Move(0, 1, True), Move(0, 0))

    def test_attack_above_byte_limit(self):
        s = state(a=Card("A", 30, 4, 3, "A"), pillz=12)
        self.assertEqual(resolve(s, Move(0, 12), Move(0, 12)).players[1].life, 10)

    def test_minimum_does_not_raise_low_attack(self):
        c = Card("B", 1, 4, 3, "B", ability=parse_effect("-12 Opp. Attack, Min 8"))
        s = state(a=Card("A", 1, 4, 2, "A"), b=c)
        self.assertEqual(resolve(s, Move(0, 0), Move(0, 2)).players[0].life, 10)

    def test_unknown_effect_rejected(self):
        for text in ("Poison 2, Min 1", "Heal 2 Max. 10", "Power Impose"):
            with self.assertRaises(ValueError):
                parse_effect(text)

    def test_bonus_counts_played_cards(self):
        c = Card("A", 5, 4, 3, "A", bonus=parse_effect("Power +2"))
        d = Card("B", 6, 4, 3, "B")
        s = State((Player((c,c), used=(0,)), Player((d,d), used=(0,))), round=2)
        self.assertEqual(resolve(s, Move(1,0), Move(1,0)).players[1].life, 10)

    def test_defeat_and_immutability(self):
        c = Card("A", 1, 2, 3, "A", ability=parse_effect("Defeat: +3 Life"))
        s = state(a=c)
        after = resolve(s, Move(0,0), Move(0,0))
        self.assertEqual(after.players[0].life, 13)
        self.assertEqual(s.players[0].life, 14)

    def test_ko_and_no_reuse(self):
        s = state(a=Card("A", 8, 20, 3, "A"))
        after = resolve(s, Move(0,0), Move(0,0))
        self.assertEqual(after.players[1].life, 0)
        self.assertTrue(after.terminal)
        self.assertEqual(legal_moves(after, 0), ())

    def test_bad_state(self):
        with self.assertRaises(ValueError):
            replace(state(), round=2)


class SolverTests(unittest.TestCase):
    def test_matching_pennies(self):
        eq = matrix_game([[1,-1],[-1,1]], 200)
        self.assertAlmostEqual(eq.value, 0)
        self.assertLess(eq.gap, .001)
        self.assertEqual(eq.row, (.5,.5))

    def test_dominant_action(self):
        eq = matrix_game([[3,2],[0,1]], 2000)
        self.assertGreater(eq.row[0], .99)
        self.assertLess(eq.gap, .01)

    def test_asymmetric_game(self):
        eq = matrix_game([[2,-1],[-1,1]], 5000)
        self.assertAlmostEqual(eq.row[0], .4, delta=.03)
        self.assertAlmostEqual(eq.value, .2, delta=.03)
        self.assertLess(eq.gap, .1)

    def test_responder_requires_public_card(self):
        with self.assertRaises(ValueError):
            advise(state(), side=1)
        a = advise(state(), side=1, observed_card=0, iterations=100)
        self.assertAlmostEqual(sum(a.probabilities), 1)
        self.assertTrue(all(m in legal_moves(state(),1) for m in a.moves))

    def test_invalid_observation(self):
        with self.assertRaises(ValueError):
            advise(state(), side=1, observed_card=8)


if __name__ == "__main__":
    unittest.main()
