"""Rule-based offline cases; these are not live match receipts."""
import unittest
from urban_rivals.engine import Card, Player, State, Move, parse_effect, resolve
from urban_rivals.vision import Catalog, RecognitionError


def fighter(name, power, damage, ability="", bonus=""):
    return Card(name, power, damage, 3, name,
                parse_effect(ability), parse_effect(bonus))


def play(a, b, leader=0, fury=False):
    # Pairs activate bonuses while preserving four-round condition semantics.
    state = State((Player((a, a)), Player((b, b))), leader=leader)
    return resolve(state, Move(0, 0, fury), Move(0, 0))


class ProtectionExchangeTests(unittest.TestCase):
    def test_reprisal_protection_blocks_power_and_damage_reducers(self):
        a = fighter("A", 9, 6, "Reprisal: Protection: Power And Damage")
        b = fighter("B", 8, 3, "-4 Opp. Power And Damage, Min 1")
        self.assertEqual(play(a, b, leader=0).players[0].life, 11)
        protected = play(a, b, leader=1)
        self.assertEqual([p.life for p in protected.players], [14, 8])

    def test_soa_removes_protection_but_leaves_opponent_bonus(self):
        a = fighter("A", 9, 6, "Protection: Power And Damage")
        b = fighter("B", 1, 3, "Stop Opp. Ability", "-4 Opp. Power And Damage, Min 1")
        self.assertEqual(play(a, b).players[1].life, 12)

    def test_protection_preserves_positive_modifiers(self):
        a = fighter("A", 9, 6, "Protection: Damage", "Damage +2")
        b = fighter("B", 1, 3, "-5 Opp. Damage, Min 1")
        self.assertEqual(play(a, b).players[1].life, 6)

    def test_exchange_bypasses_protection_and_precedes_modifiers(self):
        a = fighter("A", 9, 6, "Protection: Damage", "Damage +2")
        b = fighter("B", 1, 2, "Damage Exchange")
        self.assertEqual(play(a, b).players[1].life, 10)

    def test_losing_exchange_changes_winners_base_damage(self):
        a = fighter("A", 1, 7, "Damage Exchange")
        b = fighter("B", 9, 2)
        self.assertEqual(play(a, b).players[0].life, 7)

    def test_fury_is_added_after_exchange_and_cards_are_immutable(self):
        a = fighter("A", 9, 7, "Damage Exchange")
        b = fighter("B", 1, 2)
        result = play(a, b, fury=True)
        self.assertEqual(result.players[1].life, 10)
        self.assertEqual(result.players[0].pillz, 9)
        self.assertEqual((a.damage, b.damage), (7, 2))

    def test_stop_ability_prevents_exchange(self):
        a = fighter("A", 9, 7, "Damage Exchange")
        b = fighter("B", 1, 2, "Stop Opp. Ability")
        self.assertEqual(play(a, b).players[1].life, 7)

    def test_reprisal_exchange_requires_responding(self):
        a = fighter("A", 9, 7, "Reprisal: Damage Exchange")
        b = fighter("B", 1, 2)
        self.assertEqual(play(a, b, leader=0).players[1].life, 7)
        self.assertEqual(play(a, b, leader=1).players[1].life, 12)

    def test_power_exchange_changes_round_winner(self):
        a = fighter("A", 2, 6, "Power Exchange")
        b = fighter("B", 9, 2)
        self.assertEqual(play(a, b).players[1].life, 8)

    def test_dual_active_exchange_stops_instead_of_guessing(self):
        a = fighter("A", 9, 7, "Damage Exchange")
        b = fighter("B", 1, 2, "Reprisal: Damage Exchange")
        with self.assertRaisesRegex(ValueError, "Simultaneous damage Exchange"):
            play(a, b, leader=0)
        self.assertEqual(play(a, b, leader=1).players[1].life, 12)

    def test_unsupported_special_interactions_stay_rejected(self):
        for text in ("Protection: Ability", "Protection: Bonus", "Tune Out And Power +2",
                     "Bet >= 5 Pillz: -2 Opp. Damage, Min 1", "Copy: Opp. Bonus",
                     "Defeat: Damage Exchange", "Brawl: Protection: Damage"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_effect(text)

    def test_exact_captured_evolutions_are_cataloged_without_omitting_effects(self):
        catalog = Catalog()
        fixit = catalog.identify("Fixit", True)
        self.assertEqual((fixit.power, fixit.damage, fixit.stars), (7, 6, 4))
        self.assertEqual({e.stat for e in fixit.ability}, {"protect_power", "protect_damage"})
        self.assertTrue(all(e.condition == "reprisal" for e in fixit.ability))
        paca = catalog.identify("Pacarezza", True)
        self.assertEqual((paca.stars, paca.ability[0].stat), (2, "exchange_damage"))
        self.assertEqual(paca.ability[0].condition, "reprisal")
        for name in ("Dr Elisa", "Mendossa", "Caballine"):
            with self.subTest(name=name), self.assertRaises(RecognitionError):
                catalog.identify(name, True)
