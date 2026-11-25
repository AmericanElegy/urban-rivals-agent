import unittest

from urban_rivals.engine import Card, Move, Player, State, parse_effect, resolve


def card(name,ability="",power=5):
    return Card(name,power,3,3,name,parse_effect(ability))


def play(effect,life=14,pillz=12,paid=0,opponent_power=18):
    own=card("scaled",effect)
    opponent=card("opponent",power=opponent_power)
    fillers=lambda prefix:(card(prefix+"1"),card(prefix+"2"),card(prefix+"3"))
    state=State((Player((own,)+fillers("a"),life=life,pillz=pillz),
                 Player((opponent,)+fillers("b"))),leader=0)
    return resolve(state,Move(0,paid),Move(0,0))


class ResourceScalingTests(unittest.TestCase):
    def test_attack_per_life_left_uses_starting_round_life(self):
        result=play("+1 Attack Per Life Left",life=14)
        self.assertTrue(result.players[0].last_won)  # 5 + 14 > 18

    def test_attack_per_pillz_left_uses_reserve_before_spending(self):
        result=play("+1 Atk Per Pillz Left",pillz=12,paid=1,opponent_power=20)
        self.assertTrue(result.players[0].last_won)  # 5*2 + 12 > 20
        self.assertEqual(result.players[0].pillz,11)

    def test_scaling_obeys_conditions_and_stop_ability(self):
        self.assertEqual(parse_effect("Reprisal: +2 Attack Per Life Left")[0].condition,
                         "reprisal")
        own=card("scaled","+1 Attack Per Life Left")
        opponent=card("stopper","Stop Opp. Ability",power=18)
        fillers=lambda prefix:(card(prefix+"1"),card(prefix+"2"),card(prefix+"3"))
        state=State((Player((own,)+fillers("a")),Player((opponent,)+fillers("b"))),leader=0)
        result=resolve(state,Move(0,0),Move(0,0))
        self.assertFalse(result.players[0].last_won)

    def test_opponent_or_negative_resource_scaling_stays_rejected(self):
        # Official: "-1 Opp Att. Per Life Left, Min 2" lowers the opposing Attack
        # by the owner's remaining Life (now supported, see test_mechanics_v3).
        for text in ("+1 Opp Attack Per Pillz Left",):
            with self.subTest(text=text),self.assertRaises(ValueError):
                parse_effect(text)
