import unittest
from urban_rivals.engine import Card, Player, State, Move, parse_effect, resolve


def duel(effect, opponent_effect="", fury=False, win=True, damage=4):
    a=Card("recover",8 if win else 1,damage,3,"A",parse_effect(effect))
    b=Card("other",2,3,3,"B",parse_effect(opponent_effect))
    state=State((Player((a,a),life=20,pillz=12),Player((b,b),life=20,pillz=12)))
    return resolve(state,Move(0,0,fury),Move(0,0))


class PerDamageTests(unittest.TestCase):
    def test_recovery_uses_final_damage_after_reduction_and_fury(self):
        state=duel("+1 Life Per Damage","-3 Opp Damage, Min 1",fury=True)
        self.assertEqual(tuple(p.life for p in state.players),(23,17))
        self.assertEqual(state.players[0].pillz,9)

    def test_no_recovery_on_loss_or_stop(self):
        self.assertEqual(duel("+1 Life Per Damage",win=False).players[0].life,17)
        self.assertEqual(duel("+1 Life Per Damage","Stop Opp. Ability").players[0].life,20)

    def test_pillz_recovery_and_zero_damage(self):
        self.assertEqual(duel("+2 Pillz Per Damage").players[0].pillz,20)
        self.assertEqual(duel("+1 Life Per Damage",damage=0).players[0].life,20)

    def test_invalid_variants_remain_rejected(self):
        for text in ("Defeat: +1 Life Per Damage","Victory Or Defeat: +1 Pillz Per Damage",
                     "Support: +1 Life Per Damage","-1 Life Per Damage","+1 Opp Life Per Damage"):
            with self.subTest(text=text),self.assertRaises(ValueError):parse_effect(text)
