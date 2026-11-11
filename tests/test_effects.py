import unittest
from urban_rivals.engine import Card, Player, State, Move, parse_effect, resolve


def card(name, ability="", bonus="", clan="A", power=5, damage=3):
    return Card(name,power,damage,2,clan,parse_effect(ability),parse_effect(bonus))


class EffectTests(unittest.TestCase):
    def test_compound_modifier(self):
        a = card("A", "Power And Damage +3")
        b = card("B",clan="B",power=7)
        after = resolve(State((Player((a,)),Player((b,)))),Move(0,0),Move(0,0))
        self.assertEqual(after.players[1].life,8)

    def test_soa_stops_ability_not_bonus(self):
        a = card("A", "Stop Opp. Ability",power=7)
        b = card("B", "Power And Damage +3", "Power +2",clan="B")
        after = resolve(State((Player((a,a)),Player((b,b)))),Move(0,0),Move(0,0))
        self.assertEqual(after.players[1].life,11)

    def test_soa_preserves_conditional_bonus(self):
        a = card("A", "Stop Opp. Ability",power=9)
        b = card("B", "Revenge: Power +5", "Victory Or Defeat: +1 Pillz",clan="B")
        after = resolve(State((Player((a,a)),Player((b,b)))),Move(0,0),Move(0,0))
        self.assertEqual(after.players[1].pillz,13)

    def test_day_requires_observation(self):
        a=card("A",bonus="Day: Power And Damage +1")
        b=card("B",clan="B")
        s=State((Player((a,a)),Player((b,b))))
        with self.assertRaises(ValueError):
            resolve(s,Move(0,0),Move(0,0))
        after=resolve(State(s.players,day=True),Move(0,0),Move(0,0))
        self.assertEqual(after.players[1].life,10)

    def test_brawl_counts_opposing_selected_clan(self):
        a=card("A","Brawl: -1 Opp. Power, Min 1",power=7)
        b=card("B",clan="B",power=8)
        after=resolve(State((Player((a,a)),Player((b,b)))),Move(0,0),Move(0,0))
        self.assertEqual(after.players[1].life,11)

    def test_asymmetry(self):
        a=card("A","Asymmetry: Power And Damage +3")
        b=card("B",clan="B",power=7)
        after=resolve(State((Player((a,a)),Player((b,b)))),Move(0,0),Move(1,0))
        self.assertEqual(after.players[1].life,8)

    def test_unison_includes_used_hand(self):
        a=card("A","Unison: Attack +16")
        b=card("B",clan="B",power=9)
        after=resolve(State((Player((a,a)),Player((b,b)))),Move(0,0),Move(0,0))
        self.assertEqual(after.players[1].life,11)
