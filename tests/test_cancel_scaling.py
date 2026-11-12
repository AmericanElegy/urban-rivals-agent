import unittest
from urban_rivals.engine import Card, Player, State, Move, parse_effect, resolve


def card(name, power=7, damage=4, stars=3, ability="", bonus="", clan=None):
    return Card(name,power,damage,stars,clan or name,parse_effect(ability),parse_effect(bonus))


def duel(a,b,paid=(0,0),fury=False,leader=0):
    # Two matching clan members activate the printed bonus.
    state=State((Player((a,a),life=30),Player((b,b),life=30)),leader=leader)
    return resolve(state,Move(0,paid[0],fury),Move(0,paid[1]))


class CancelScalingTests(unittest.TestCase):
    def test_per_opponent_damage_uses_base_not_bonus_or_fury(self):
        a=card("a",power=1,ability="+3 Attack Per Opp. Damage")
        b=card("b",power=15,damage=5,bonus="Damage +4")
        self.assertTrue(duel(a,b).players[0].last_won)  # 1+3*5=16
        self.assertFalse(duel(a,card("b",power=17,damage=5,bonus="Damage +4")).players[0].last_won)

    def test_per_opponent_power_uses_base(self):
        a=card("a",power=1,ability="+3 Attack Per Opp. Power")
        b=card("b",power=5,bonus="Power +12")
        self.assertFalse(duel(a,b).players[0].last_won)  # 16 versus 17

    def test_cancel_removes_opposing_own_bonus_and_ability(self):
        a=card("a",ability="Power +4",bonus="Power +2")
        b=card("b",power=8,ability="Cancel Opp. Power Modif.")
        self.assertFalse(duel(a,b).players[0].last_won)

    def test_cancel_removes_opposing_reducers_too(self):
        a=card("a",ability="-5 Opp. Power, Min 1")
        b=card("b",power=8,ability="Cancel Opp. Power Modif.")
        self.assertFalse(duel(a,b).players[0].last_won)

    def test_cancel_damage_keeps_fury(self):
        a=card("a",power=10,damage=4,ability="Damage +3",bonus="Damage +2")
        b=card("b",ability="Cancel Opp. Damage Modif.")
        self.assertEqual(duel(a,b,fury=True).players[1].life,24)

    def test_cancel_exchange_preserves_original_bases(self):
        a=card("a",power=10,damage=2,ability="Damage Exchange")
        b=card("b",damage=8,ability="Cancel Opp. Damage Modif.")
        self.assertEqual(duel(a,b).players[1].life,28)

    def test_stopped_cancel_has_no_effect(self):
        a=card("a",ability="Stop Opp. Ability",bonus="Power +2")
        b=card("b",power=8,ability="Cancel Opp. Power Modif.")
        self.assertTrue(duel(a,b).players[0].last_won)

    def test_stop_bonus_and_ability_sources_remain_distinct(self):
        a=card("a",ability="Power +3",bonus="Power +2")
        b=card("b",power=9,ability="Stop Opp. Bonus")
        self.assertTrue(duel(a,b).players[0].last_won)  # ability remains: 10

    def test_soa_disables_ability_sob_before_bonus_is_removed(self):
        a=card("a",ability="Stop Opp. Ability",bonus="Power +2")
        b=card("b",power=8,ability="Stop Opp. Bonus")
        self.assertTrue(duel(a,b).players[0].last_won)

    def test_equalizer_damage_uses_opponent_stars_and_minimum(self):
        a=card("a",power=10,damage=6,stars=4)
        b=card("b",ability="Equalizer: -1 Opp. Damage, Min 1")
        self.assertEqual(duel(a,b).players[1].life,28)

    def test_uncertain_cross_source_stop_cycle_rejected(self):
        a=card("a",bonus="Stop Opp. Ability")
        b=card("b",ability="Stop Opp. Bonus")
        with self.assertRaisesRegex(ValueError,"precedence"):
            duel(a,b)

    def test_recursive_copy_remains_rejected(self):
        with self.assertRaises(ValueError):
            duel(card("a",ability="Copy: Opp. Ability"),card("b",ability="Copy: Opp. Ability"))
