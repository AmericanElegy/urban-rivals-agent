"""Behavior of the extended mechanics, each checked against official card text."""
import unittest

from urban_rivals.card_text import annotate
from urban_rivals.engine import (Card, Move, Player, State, effective_clans, evaluate,
                                 parse_effect, resolve)


def card(name, power=5, damage=3, ability="", bonus="", clan=None, stars=3):
    return Card(name, power, damage, stars, clan or "Clan" + name,
                parse_effect(ability), parse_effect(bonus))


def filler(prefix, clan=None):
    return tuple(card(prefix + str(i), 1, 0, clan=clan) for i in range(3))


def battle(a, b, life=(12, 12), pillz=(12, 12), hands=None, leader=0, day=None):
    hands = hands or ((a,) + filler("x"), (b,) + filler("y"))
    return State((Player(hands[0], life[0], pillz[0]), Player(hands[1], life[1], pillz[1])),
                 leader=leader, day=day)


def play(state, a=0, b=0, pa=0, pb=0):
    return resolve(state, Move(a, pa), Move(b, pb))


class ParserTests(unittest.TestCase):
    def test_spelling_variants_match_canonical_text(self):
        pairs = (("Reprisal: -2 Opp Pow. & Dmg,min 2", "Reprisal: -2 Opp Power And Damage, Min 2"),
                 ("-2 Opp Pillz. Min 1", "-2 Opp Pillz, Min 1"),
                 ("Stop: Atk. +12", "Stop: Attack +12"),
                 ("Backlash: - 1 Life Min 3", "Backlash: -1 Life, Min 3"),
                 ("Courage: Prot.: Power & Damage", "Courage: Protection: Power And Damage"),
                 ("Vict. Or Def.: -2 Opp Life & Pillz Min 0", "Victory Or Defeat: -2 Opp Life And Pillz, Min 0"),
                 ("Unison : Attack +8", "Unison: Attack +8"))
        for variant, canonical in pairs:
            with self.subTest(variant=variant):
                self.assertEqual(parse_effect(variant), parse_effect(canonical))

    def test_chained_conditions(self):
        e, = parse_effect("Day: Growth: Poison 1, Min 0")
        self.assertEqual((e.stat, e.condition, e.multiplier), ("poison", "day", "growth"))
        e, = parse_effect("Versus(Oculus): Defeat: -1 Opp Pillz, Min 2")
        self.assertEqual((e.condition, e.gates), ("defeat", ("versus:Oculus",)))
        e, = parse_effect("Conf.: Vict. Or Def.: -2 Opp. Life, Min 0")
        self.assertEqual((e.condition, e.gates), ("victory or defeat", ("confidence",)))

    def test_clan_lists_are_mandatory(self):
        for text in ("Versus  : Power +2", "After : +2 Life", "Infiltrates(): Power +3"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_effect(text)

    def test_killshot_and_perfect_need_end_of_round_effects(self):
        with self.assertRaises(ValueError):
            parse_effect("Killshot: Power +2")
        self.assertEqual(parse_effect("Killshot: +2 Life")[0].gates, ("killshot",))


class PersistentTests(unittest.TestCase):
    def test_poison_ticks_only_in_following_rounds(self):
        # "If CARD wins the round, at the end of each of the following turns
        # the opponent will lose 3 Life point(s) if he/she has more than 5."
        s = play(battle(card("a", 9, 2, "Poison 3, Min 5"), card("b", 1, 1)))
        self.assertEqual(s.players[1].life, 10)          # damage only this round
        self.assertEqual(s.players[1].effects[0].kind, "poison")
        s = play(s, 1, 1)                                 # fillers: 1 power each, side 0 leads tie
        self.assertEqual(s.players[1].life, 7)            # 10 - 0 damage - 3 poison
        s = play(s, 2, 2)
        self.assertEqual(s.players[1].life, 5)            # bounded at Min 5

    def test_toxin_also_ticks_this_round(self):
        # "your opponent will lose 1 Life points... This effect will persist"
        s = play(battle(card("a", 9, 2, "Toxin 1, Min 0"), card("b", 1, 1)))
        self.assertEqual(s.players[1].life, 9)

    def test_new_poison_replaces_old(self):
        hands = ((card("a", 9, 0, "Poison 1, Min 0"), card("c", 9, 0, "Toxin 2, Min 0")) + filler("x")[:2],
                 (card("b", 1, 1), card("d", 1, 1)) + filler("y")[:2])
        s = play(battle(None, None, hands=hands))
        s = play(s, 1, 1)
        self.assertEqual([e.kind for e in s.players[1].effects], ["toxin"])
        self.assertEqual(s.players[1].life, 10)           # toxin replaced poison before ticking

    def test_heal_and_regen_respect_maximum(self):
        s = play(battle(card("a", 9, 0, "Regen 2, Max 13"), card("b", 1, 0)), pa=0)
        self.assertEqual(s.players[0].life, 13)
        s = play(battle(card("a", 9, 0, "Heal 2, Max 13"), card("b", 1, 0)))
        self.assertEqual(s.players[0].life, 12)           # Heal waits for the next round
        self.assertEqual(play(s, 1, 1).players[0].life, 13)

    def test_dope_and_consume_change_pillz(self):
        s = play(battle(card("a", 9, 0, "Dope 1, Max 20"), card("b", 1, 0)))
        self.assertEqual(s.players[0].pillz, 13)
        s = play(battle(card("a", 9, 0, "Consume 2, Min 4"), card("b", 1, 0)))
        self.assertEqual(s.players[1].pillz, 10)

    def test_combust_hits_life_and_pillz_and_players_variant_hits_both(self):
        s = play(play(battle(card("a", 9, 0, "Combust 1, Min 0"), card("b", 1, 0))), 1, 1)
        self.assertEqual((s.players[1].life, s.players[1].pillz), (11, 11))
        s = play(play(battle(card("a", 9, 0, "Players Combust 1, Min 0"), card("b", 1, 0))), 1, 1)
        self.assertEqual([(p.life, p.pillz) for p in s.players], [(11, 11), (11, 11)])

    def test_corrosion_scales_with_round_played(self):
        hands = ((card("f", 1, 0), card("a", 9, 0, "Victory Or Defeat: Corrosion 1, Min 0")) + filler("x")[:2],
                 (card("g", 1, 0), card("b", 1, 0)) + filler("y")[:2])
        s = play(battle(None, None, hands=hands))         # round 1 filler
        s = play(s, 1, 1)                                 # round 2: corrosion 2 installed
        s = play(s, 2, 2)
        self.assertEqual(s.players[1].life, 10)

    def test_backlash_poison_targets_its_owner(self):
        s = play(play(battle(card("a", 9, 0, "Backlash: Poison 1, Min 3"), card("b", 1, 0))), 1, 1)
        self.assertEqual((s.players[0].life, s.players[1].life), (11, 12))

    def test_cancel_life_modif_silences_ticks_and_installs(self):
        hands = ((card("a", 9, 0, "Poison 2, Min 0"), card("c", 1, 0)) + filler("x")[:2],
                 (card("b", 1, 0), card("d", 1, 0, "Cancel Opp. Life Modif.")) + filler("y")[:2])
        s = play(play(battle(None, None, hands=hands)), 1, 1)
        self.assertEqual(s.players[1].life, 12)           # tick cancelled for that round
        self.assertTrue(s.players[1].effects)             # but the poison keeps running

    def test_evaluation_projects_running_effects(self):
        base = battle(card("a"), card("b"))
        poisoned = State((base.players[0],
                          Player(base.players[1].hand, 12, 12,
                                 effects=play(battle(card("a", 9, 0, "Poison 2, Min 0"), card("b", 1, 0)))
                                 .players[1].effects)), round=1)
        self.assertGreater(evaluate(poisoned), evaluate(base))


class ConditionTests(unittest.TestCase):
    def test_stop_condition_fires_only_when_ability_is_stopped(self):
        a = card("a", 5, 2, "Stop: Power +5")
        self.assertTrue(play(battle(a, card("b", 6, 2, "Stop Opp. Ability"))).players[0].last_won)
        self.assertFalse(play(battle(a, card("b", 6, 2))).players[0].last_won)

    def test_killshot_requires_double_attack(self):
        a = card("a", 4, 0, "Killshot: +3 Life")
        self.assertEqual(play(battle(a, card("b", 2, 0)), pa=0).players[0].life, 15)
        self.assertEqual(play(battle(a, card("b", 3, 0)), pa=0).players[0].life, 12)

    def test_perfect_requires_exact_winning_pillz(self):
        a = card("a", 5, 0, "Perfect: +2 Pillz")
        b = card("b", 9, 0)
        # Attack 10 vs 9 is a perfect win; 15 vs 9 wastes a pill.
        self.assertEqual(play(battle(a, b), pa=1).players[0].pillz, 13)
        self.assertEqual(play(battle(a, b), pa=2).players[0].pillz, 10)

    def test_reanimate_prevents_ko(self):
        s = play(battle(card("a", 1, 0, "Reanimate: +2 Life"), card("b", 9, 9), life=(3, 12)))
        self.assertEqual(s.players[0].life, 3)            # held at 1, then +2

    def test_xantiax_hits_both_players(self):
        s = play(battle(card("a", 1, 0, "Xantiax: -2 Life, Min. 5"), card("b", 9, 0)))
        self.assertEqual([p.life for p in s.players], [10, 10])

    def test_versus_checks_whole_opposing_hand(self):
        a = card("a", 5, 0, "Versus(Oculus): Power +5")
        b = card("b", 8, 0)
        hands = ((a,) + filler("x"), (b,) + filler("y")[:2] + (card("o", 1, 0, clan="Oculus"),))
        self.assertTrue(play(battle(None, None, hands=hands)).players[0].last_won)
        self.assertFalse(play(battle(a, b)).players[0].last_won)

    def test_after_uses_previous_own_card_clan(self):
        a = card("a", 5, 0, "After(Frozn): Power +5")
        hands = ((card("f", 1, 0, clan="Frozn"), a) + filler("x")[:2],
                 (card("g", 9, 0), card("b", 8, 0)) + filler("y")[:2])
        s = play(battle(None, None, hands=hands))
        self.assertTrue(play(s, 1, 1).players[0].last_won)

    def test_conditional_copy(self):
        a = card("a", 5, 0, "Reprisal: Copy Opp. Ability")
        # Played second (Reprisal) it copies Power +4: 9 x 2 = 18 > 11.
        self.assertEqual(play(battle(a, card("b", 7, 0, "Power +4"), leader=1), pa=1).players[0].last_won, True)
        self.assertFalse(play(battle(a, card("b", 7, 0, "Power +4"), leader=0), pa=1).players[0].last_won)


class TargetTests(unittest.TestCase):
    def test_power_impose_uses_printed_value(self):
        # "The opposing character has equal Power to CARD... only the figure
        # shown on CARD", then the opponent's own modifiers still apply.
        a = card("a", 6, 0, "Power Impose")
        self.assertTrue(play(battle(a, card("b", 9, 0))).players[0].last_won)        # 6 v 6, leader wins
        self.assertFalse(play(battle(a, card("b", 9, 0, "Power +1"))).players[0].last_won)  # 6 v 7

    def test_cards_effects_hit_both_characters(self):
        s = play(battle(card("a", 5, 5, "-2 Cards Damage, Min 1"), card("b", 1, 0)))
        self.assertEqual(s.players[1].life, 9)

    def test_players_life(self):
        s = play(battle(card("a", 9, 0, "+2 Players Life"), card("b", 1, 0)))
        self.assertEqual([p.life for p in s.players], [14, 14])

    def test_life_lost_scaling_needs_start_value(self):
        a = card("a", 5, 0, "+1 Power Per Life Lost Max 9")
        hands = ((a,) + filler("x"), (card("b", 7, 0),) + filler("y"))
        hurt = State((Player(hands[0], 8, 12, start_life=12), Player(hands[1], 12, 12)))
        self.assertTrue(play(hurt).players[0].last_won)


class SpecialClanTests(unittest.TestCase):
    def test_oculus_infiltration_rule(self):
        oculus = card("o", bonus="Infiltrated", clan="Oculus")
        a, b = card("a", clan="A"), card("b", clan="B")
        self.assertEqual(effective_clans((oculus, a, a, a))[0], "A")
        self.assertEqual(effective_clans((oculus, a, a, b))[0], "B")
        self.assertEqual(effective_clans((oculus, a, b, card("c", clan="C")))[0], "Oculus")
        self.assertEqual(effective_clans((oculus, oculus, a, a))[0], "Oculus")

    def test_oculus_ability_needs_infiltrated_clan(self):
        o = card("o", 5, 0, "Infiltrates(Bangers): Power +5", "Infiltrated", clan="Oculus")
        b = card("b", 8, 0)
        bangers = tuple(card("k" + str(i), 1, 0, clan="Bangers") for i in range(3))
        self.assertTrue(play(battle(None, None, hands=((o,) + bangers, (b,) + filler("y")))).players[0].last_won)
        jungo = tuple(card("k" + str(i), 1, 0, clan="Jungo") for i in range(3))
        self.assertFalse(play(battle(None, None, hands=((o,) + jungo, (b,) + filler("y")))).players[0].last_won)

    def test_leader_team_ability_and_cancel_leader(self):
        leader = card("L", 1, 0, "Team: Power +4", "Cancel Leader", clan="Leader")
        a = card("a", 5, 0)
        b = card("b", 8, 0)
        hands = ((a, leader, card("x1", 1, 0), card("x2", 1, 0)), (b,) + filler("y"))
        self.assertTrue(play(battle(None, None, hands=hands)).players[0].last_won)
        two = ((a, leader, card("L2", 1, 0, "Team: Power +1", "Cancel Leader", clan="Leader"),
                card("x2", 1, 0)), (b,) + filler("y"))
        self.assertFalse(play(battle(None, None, hands=two)).players[0].last_won)

    def test_ghostown_day_night_bonus(self):
        text = annotate("Day: Power And Damage + 1", "GhosTown", None, "bonus")
        self.assertIn(" / ", text)
        g = Card("g", 5, 2, 3, "GhosTown", (), parse_effect(text))
        hands = ((g, g) + filler("x")[:2], (card("b", 5, 2),) + filler("y"))
        self.assertTrue(play(battle(None, None, hands=hands, leader=1, day=True)).players[0].last_won)
        # Night: -1 Opp Power And Damage, Min 1 also wins the 5 vs 5 tie.
        night = play(battle(None, None, hands=hands, leader=1, day=False))
        self.assertTrue(night.players[0].last_won)
        self.assertEqual(night.players[1].life, 10)
        with self.assertRaises(ValueError):
            play(battle(None, None, hands=hands))


if __name__ == "__main__":
    unittest.main()
