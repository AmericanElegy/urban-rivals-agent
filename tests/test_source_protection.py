import unittest

from urban_rivals.engine import Card, Move, Player, State, parse_effect, resolve


def card(name, ability="", bonus="", power=5, damage=3, clan=None):
    return Card(name,power,damage,3,clan or name,
                parse_effect(ability),parse_effect(bonus))


def duel(left,right,left_clanmate=None,right_clanmate=None):
    left_mate=left_clanmate or card("left mate",clan=left.clan)
    right_mate=right_clanmate or card("right mate",clan=right.clan)
    filler_left=(card("left filler 1"),card("left filler 2"))
    filler_right=(card("right filler 1"),card("right filler 2"))
    return State((Player((left,left_mate)+filler_left),
                  Player((right,right_mate)+filler_right)),leader=0)


class SourceProtectionTests(unittest.TestCase):
    def test_skeelz_bonus_preserves_ability_against_stop_ability(self):
        protected=card("protected","Power +3","Protection: Ability",clan="Skeelz")
        stopper=card("stopper","Stop Opp. Ability",power=7)
        result=resolve(duel(protected,stopper),Move(0,0),Move(0,0))
        self.assertTrue(result.players[0].last_won)

    def test_stop_bonus_removes_skeelz_protection_then_stop_ability_applies(self):
        protected=card("protected","Power +3","Protection: Ability",clan="Skeelz")
        stopper=card("stopper","Stop Opp. Ability","Stop Opp. Bonus",power=7,
                     clan="stoppers")
        result=resolve(duel(protected,stopper),Move(0,0),Move(0,0))
        self.assertFalse(result.players[0].last_won)

    def test_protection_bonus_preserves_bonus_against_stop_bonus(self):
        protected=card("protected","Protection: Bonus","Power +3",clan="Rescue")
        stopper=card("stopper","Stop Opp. Bonus",power=7)
        result=resolve(duel(protected,stopper),Move(0,0),Move(0,0))
        self.assertTrue(result.players[0].last_won)

    def test_stop_ability_removes_protection_bonus_before_stop_bonus(self):
        protected=card("protected","Protection: Bonus","Power +3",clan="Rescue")
        stopper=card("stopper","Stop Opp. Ability","Stop Opp. Bonus",power=7,
                     clan="stoppers")
        result=resolve(duel(protected,stopper),Move(0,0),Move(0,0))
        self.assertFalse(result.players[0].last_won)

    def test_attack_and_spaced_damage_protection_parse(self):
        self.assertEqual(parse_effect("Protection: Attack")[0].stat,"protect_attack")
        self.assertEqual(parse_effect("Protection : Damage")[0].stat,"protect_damage")

    def test_attack_protection_blocks_reduction_but_not_power_reduction(self):
        protected=card("protected","Protection: Attack",power=5)
        reducer=card("reducer","-8 Opp Attack, Min 0",power=5)
        result=resolve(duel(protected,reducer),Move(0,1),Move(0,1))
        self.assertTrue(result.players[0].last_won)
