import unittest

from urban_rivals.engine import Card, Move, Player, State, parse_effect, resolve


def card(name,power=5,ability="",bonus="",clan=None):
    return Card(name,power,3,3,clan or name,parse_effect(ability),parse_effect(bonus))


def battle(left,right,left_mate=None,right_mate=None,leader=0):
    lm=left_mate or card("left mate",clan=left.clan)
    rm=right_mate or card("right mate",clan=right.clan)
    return State((Player((left,lm,card("la"),card("lb"))),
                  Player((right,rm,card("ra"),card("rb")))),leader=leader)


class CopyBonusPowerTests(unittest.TestCase):
    def test_power_copy_uses_printed_opposing_power(self):
        copier=card("copier",2,"Copy: Opp. Power")
        opponent=card("opponent",7,"Power +3")
        result=resolve(battle(copier,opponent),Move(0,0),Move(0,0))
        self.assertFalse(result.players[0].last_won)  # copied 7 loses to modified 10

    def test_combined_power_damage_copy_parses_both_stats(self):
        effects=parse_effect("Copy: Power And Damage Opp.")
        self.assertEqual({e.stat for e in effects},{"copy_power","copy_damage"})

    def test_copy_bonus_replaces_ability_with_activated_opposing_bonus(self):
        copier=card("copier",5,"Copy: Opp. Bonus")
        opponent=card("opponent",5,bonus="Power +3",clan="Bangers")
        result=resolve(battle(copier,opponent),Move(0,0),Move(0,0))
        self.assertTrue(result.players[0].last_won)  # 5+3 ties 7+3; initiative wins

    def test_copy_bonus_has_no_effect_when_opposing_bonus_is_inactive(self):
        copier=card("copier",5,"Copy Opp. Bonus")
        opponent=card("opponent",7,bonus="Power +3",clan="Bangers")
        off_clan=card("off clan",clan="Other")
        result=resolve(battle(copier,opponent,right_mate=off_clan),Move(0,0),Move(0,0))
        self.assertFalse(result.players[0].last_won)

    def test_copied_bonus_retains_ability_source(self):
        copier=card("copier",5,"Copy: Opp. Bonus")
        opponent=card("opponent",7,"Stop Opp. Ability","Power +3",clan="Bangers")
        result=resolve(battle(copier,opponent),Move(0,0),Move(0,0))
        self.assertFalse(result.players[0].last_won)

    def test_modified_and_recursive_bonus_copy_remain_rejected(self):
        with self.assertRaises(ValueError):parse_effect("Support: Copy Opp. Bonus")
        copier=card("copier",5,"Copy: Opp. Bonus")
        recursive=card("recursive",7,bonus="Copy: Opp. Bonus",clan="copy clan")
        with self.assertRaisesRegex(ValueError,"Recursive effect-copy"):
            resolve(battle(copier,recursive),Move(0,0),Move(0,0))
