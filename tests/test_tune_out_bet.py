import unittest
from urban_rivals.engine import Card, Player, State, Move, parse_effect, resolve


def fighter(name, power=5, damage=3, stars=3, ability="", bonus=""):
    return Card(name,power,damage,stars,name,parse_effect(ability),parse_effect(bonus))


def state(a,b,leader=0):
    return State((Player((a,a)),Player((b,b))),leader=leader)


class TuneOutBetTests(unittest.TestCase):
    def test_more_pillz_wins_despite_lower_power_and_attack(self):
        a=fighter("A",power=1,bonus="Tune Out")
        b=fighter("B",power=20,ability="Attack +100")
        after=resolve(state(a,b),Move(0,1),Move(0,0))
        self.assertEqual(after.players[1].life,11)

    def test_pill_ties_use_stars_then_initiative(self):
        a=fighter("A",power=1,stars=2,bonus="Tune Out")
        b=fighter("B",power=20,stars=3)
        self.assertEqual(resolve(state(a,b,1),Move(0,0),Move(0,0)).players[1].life,11)
        b=fighter("B",power=20,stars=2)
        for leader in (0,1):
            after=resolve(state(a,b,leader),Move(0,0),Move(0,0))
            self.assertEqual(after.players[1-leader].life,11)

    def test_lone_clan_card_does_not_activate_tune_out_bonus(self):
        a=fighter("A",power=1,bonus="Tune Out")
        b=fighter("B",power=20)
        after=resolve(State((Player((a,)),Player((b,)))),Move(0,1),Move(0,0))
        self.assertEqual(after.players[0].life,11)

    def test_stop_ability_does_not_remove_clan_tune_out(self):
        a=fighter("A",power=1,ability="Power +4",bonus="Tune Out")
        b=fighter("B",power=20,ability="Stop Opp. Ability")
        self.assertEqual(resolve(state(a,b),Move(0,1),Move(0,0)).players[1].life,11)

    def test_bet_over_is_strict_and_includes_free_pill(self):
        a=fighter("A",power=9,ability="Bet > 3 Pillz: +3 Life")
        b=fighter("B",power=1)
        self.assertEqual(resolve(state(a,b),Move(0,2),Move(0,0)).players[0].life,14)
        self.assertEqual(resolve(state(a,b),Move(0,3),Move(0,0)).players[0].life,17)

    def test_bet_excludes_fury_cost_and_still_requires_victory(self):
        a=fighter("A",power=9,ability="Bet > 3 Pillz: +3 Life")
        b=fighter("B",power=1)
        after=resolve(state(a,b),Move(0,2,True),Move(0,0))
        self.assertEqual((after.players[0].life,after.players[0].pillz),(14,7))
        # A triggered Bet life effect does not fire merely for spending pillz.
        b=fighter("B",power=100)
        self.assertEqual(resolve(state(a,b),Move(0,3),Move(0,0)).players[0].life,11)

    def test_bet_under_is_strict(self):
        a=fighter("A",power=9,ability="Bet < 3 Pillz: +3 Life")
        b=fighter("B",power=1)
        self.assertEqual(resolve(state(a,b),Move(0,1),Move(0,0)).players[0].life,17)
        self.assertEqual(resolve(state(a,b),Move(0,2),Move(0,0)).players[0].life,14)

    def test_bet_reducer_can_be_stopped(self):
        a=fighter("A",power=30,damage=6,ability="Stop Opp. Ability")
        b=fighter("B",power=1,ability="Bet > 3 Pillz: -4 Opp. Damage, Min 1")
        self.assertEqual(resolve(state(a,b),Move(0,0),Move(0,3)).players[1].life,8)

    def test_soa_preserves_bonus_with_same_stat_but_different_bet_threshold(self):
        a=fighter("A",power=30,ability="Bet > 5 Pillz: +1 Pillz",
                  bonus="Bet > 3 Pillz: +2 Pillz")
        b=fighter("B",power=1,ability="Stop Opp. Ability")
        self.assertEqual(resolve(state(a,b),Move(0,3),Move(0,0)).players[0].pillz,11)

    def test_tune_out_uses_attack_pillz_not_fury_spending(self):
        a=fighter("A",power=9,bonus="Tune Out")
        b=fighter("B",power=1)
        after=resolve(state(a,b),Move(0,0,True),Move(0,1))
        self.assertEqual(after.players[0].life,11)
