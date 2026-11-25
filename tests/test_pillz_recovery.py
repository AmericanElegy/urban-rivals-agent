import unittest

from urban_rivals.engine import Card, Move, Player, State, parse_effect, resolve


def card(name, ability="", bonus="", power=5, clan=None):
    return Card(name,power,3,3,clan or name,parse_effect(ability),parse_effect(bonus))


def state(recovering,opponent):
    allies=(card("ally",clan=recovering.clan),card("filler a"),card("filler b"))
    enemies=(card("enemy ally",clan=opponent.clan),card("filler c"),card("filler d"))
    return State((Player((recovering,)+allies),Player((opponent,)+enemies)),leader=0)


class PillzRecoveryTests(unittest.TestCase):
    def test_defeat_recovers_fraction_of_full_attack_allocation(self):
        vortex=card("vortex",bonus="Defeat: Recover 2 Pillz Out Of 3",clan="Vortex")
        winner=card("winner",power=9)
        result=resolve(state(vortex,winner),Move(0,2),Move(0,1))
        self.assertEqual(result.players[0].pillz,12)  # 12 - 2 + floor(3*2/3)

    def test_minimum_one_applies_to_free_pill(self):
        vortex=card("vortex",bonus="Defeat: Recover 2 Pillz Out Of 3",clan="Vortex")
        result=resolve(state(vortex,card("winner",power=9)),Move(0,0),Move(0,0))
        self.assertEqual(result.players[0].pillz,13)

    def test_recovery_does_not_trigger_on_victory(self):
        vortex=card("vortex",bonus="Defeat: Recover 2 Pillz Out Of 3",power=9,clan="Vortex")
        result=resolve(state(vortex,card("loser",power=1)),Move(0,2),Move(0,0))
        self.assertEqual(result.players[0].pillz,10)

    def test_stop_bonus_blocks_recovery(self):
        vortex=card("vortex",bonus="Defeat: Recover 2 Pillz Out Of 3",clan="Vortex")
        stopper=card("stopper","Stop Opp. Bonus",power=9)
        result=resolve(state(vortex,stopper),Move(0,2),Move(0,1))
        self.assertEqual(result.players[0].pillz,10)

    def test_plain_recover_is_inherently_defeat_based(self):
        effect=parse_effect("Recover 1 Pillz Out Of 2")[0]
        self.assertEqual((effect.condition,effect.amount,effect.divisor,effect.minimum),
                         ("defeat",1,2,1))

    def test_combined_or_player_targeted_variants_remain_rejected(self):
        for text in ("Support: Recover 1 Pillz Out Of 2",
                     "Unison: Recover 1 Players Pillz Out Of 2"):
            with self.subTest(text=text),self.assertRaises(ValueError):
                parse_effect(text)
