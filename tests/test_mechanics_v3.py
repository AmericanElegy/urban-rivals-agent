"""Mechanics defined by the official per-card descriptions in
data/card_reference.json (After/Versus clans, Reanimate, Corrupt, Xantiax,
Players/Cards, Corrosion, Mindwipe, Combust, Repair, Team, Infiltrated,
shared Poison/Toxin slots, Per Life Lost, instant KO, Tie-break)."""
import unittest

from urban_rivals.descriptions import annotate, description
from urban_rivals.engine import (Card, Move, Player, State, effective_clans,
                                 parse_effect, resolve)


def card(name, power, damage, clan="X", ability="", bonus="", stars=3):
    return Card(name, power, damage, stars, clan, parse_effect(ability), parse_effect(bonus))


FILLER = card("Filler", 1, 0, "Y")


def start(mine, theirs, life=12, pillz=12, **extra):
    n = max(len(mine), len(theirs))
    mine = tuple(mine) + (FILLER,) * (n - len(mine))
    theirs = tuple(theirs) + (FILLER,) * (n - len(theirs))
    return State((Player(mine, life, pillz), Player(theirs, life, pillz)), **extra)


class DescriptionTests(unittest.TestCase):
    def test_official_clan_lists_are_written_into_text(self):
        self.assertIn("Bangers", description("Dorga", "After : Power +2"))
        self.assertEqual(annotate("Dorga", "After : Power +2"),
                         "After [Bangers|Junkz|Montana|Pussycats|Uppers]: Power +2")
        self.assertTrue(annotate("Buf00n", "Versus  : -3 Opp. Life Min 0").startswith("Versus [Freaks|Oculus]:"))


class ClanConditionTests(unittest.TestCase):
    def test_after_needs_a_named_clan_played_last_round(self):
        dorga = card("Dorga", 5, 2, "Z", ability="After [Pussycats]: Power +2")
        cat = card("Cat", 9, 0, "Pussycats")
        other = card("Other", 9, 0, "Q")
        opp = card("Opp", 6, 0, "Y", stars=2)
        after_cat = resolve(start((cat, dorga), (FILLER, opp)), Move(0, 0), Move(0, 0))
        self.assertTrue(resolve(after_cat, Move(1, 0), Move(1, 0)).players[0].last_won)   # 7 > 6
        after_other = resolve(start((other, dorga), (FILLER, opp)), Move(0, 0), Move(0, 0))
        self.assertFalse(resolve(after_other, Move(1, 0), Move(1, 0)).players[0].last_won)

    def test_versus_looks_at_the_whole_opposing_hand(self):
        buf = card("Buf00n", 9, 0, ability="Versus [Freaks]: -3 Opp. Life Min 0")
        freak = card("Freak", 1, 0, "Freaks")
        hit = resolve(start((buf,), (FILLER, freak)), Move(0, 0), Move(0, 0))
        miss = resolve(start((buf,), (FILLER, FILLER)), Move(0, 0), Move(0, 0))
        self.assertEqual((hit.players[1].life, miss.players[1].life), (9, 12))


class OfficialMechanicTests(unittest.TestCase):
    def test_reanimate_prevents_ko_and_heals_on_defeat(self):
        cadmendus = card("Cadmendus", 1, 0, ability="Reanimate: +1 Life")
        killer = card("Killer", 9, 9, "Y")
        after = resolve(start((cadmendus, FILLER), (killer, FILLER), life=5), Move(0, 0), Move(0, 0))
        self.assertEqual(after.players[0].life, 1)
        self.assertFalse(after.terminal)

    def test_heal_does_not_revive_a_ko(self):
        mina = card("Mina", 1, 0, ability="Defeat: Heal 1 Max. 15")
        killer = card("Killer", 9, 9, "Y")
        after = resolve(start((mina, FILLER), (killer, FILLER), life=5), Move(0, 0), Move(0, 0))
        self.assertEqual(after.players[0].life, 0)

    def test_corrupt_costs_own_life_win_or_lose(self):
        nega = card("Nega", 1, 8, ability="Corrupt 2 Min. 5")
        strong = card("Strong", 9, 0, "Y")
        after = resolve(start((nega, FILLER), (strong, FILLER), life=12), Move(0, 0), Move(0, 0))
        self.assertEqual(after.players[0].life, 10)

    def test_xantiax_and_players_hit_both(self):
        x = card("X", 9, 0, ability="Xantiax: -2 Life, Min. 0")
        after = resolve(start((x, FILLER), (FILLER, FILLER)), Move(0, 0), Move(0, 0))
        self.assertEqual((after.players[0].life, after.players[1].life), (10, 10))
        cards = card("C", 9, 5, ability="-2 Cards Damage, Min 1")
        after = resolve(start((cards, FILLER), (FILLER, FILLER)), Move(0, 0), Move(0, 0))
        self.assertEqual(after.players[1].life, 9)   # own damage 5 -> 3

    def test_corrosion_scales_with_the_round_played(self):
        scarlacc = card("Scarlacc", 9, 0, ability="Victory Or Defeat: Corrosion 1, Min 0")
        s = start((FILLER, scarlacc, FILLER), (FILLER, FILLER, FILLER))
        r1 = resolve(s, Move(0, 0), Move(0, 0))
        r2 = resolve(r1, Move(1, 0), Move(1, 0))
        self.assertEqual(r2.players[1].effects, (("poison", 2, 0),))

    def test_mindwipe_combust_repair_expand(self):
        self.assertEqual({e.stat for e in parse_effect("Mindwipe 1, Min 0")}, {"toxin", "consume"})
        self.assertEqual({e.stat for e in parse_effect("Combust 1, Min 1")}, {"poison", "rot"})
        self.assertEqual({e.stat for e in parse_effect("Repair 1, Max. 14")}, {"regen", "dope"})

    def test_poison_and_toxin_share_a_slot(self):
        poison = card("P", 9, 0, ability="Poison 1, Min 0")
        toxin = card("T", 9, 0, ability="Toxin 2, Min 0")
        s = start((poison, toxin, FILLER), (FILLER,) * 3)
        r2 = resolve(resolve(s, Move(0, 0), Move(0, 0)), Move(1, 0), Move(1, 0))
        self.assertEqual(r2.players[1].effects, (("toxin", 2, 0),))
        self.assertEqual(r2.players[1].life, 12 - 2)   # the replaced Poison did not also tick

    def test_power_per_life_lost(self):
        padre = card("Padre", 2, 1, ability="+1 Pow./ Life Lost Max. 14")
        opp = card("Opp", 5, 0, "Y", stars=2)
        hurt = State((Player((padre, FILLER), life=8), Player((opp, FILLER), life=12)))
        self.assertTrue(resolve(hurt, Move(0, 0), Move(0, 0)).players[0].last_won)   # 2+4=6 > 5

    def test_team_ability_reaches_every_card(self):
        hugo = card("Hugo", 1, 0, "Leader", ability="Team: +7 Attack")
        plain = card("Plain", 1, 1, "Z")
        opp = card("Opp", 5, 0, "Y")
        s = start((plain, hugo), (opp, FILLER))
        self.assertTrue(resolve(s, Move(0, 0), Move(0, 0)).players[0].last_won)   # 1+7 > 5

    def test_cancel_leader_with_two_leaders(self):
        hugo = card("Hugo", 1, 0, "Leader", ability="Team: +7 Attack")
        other = card("Boss", 1, 0, "Leader")
        opp = card("Opp", 5, 0, "Y")
        s = start((card("Plain", 1, 1, "Z"), hugo, other), (opp, FILLER, FILLER))
        self.assertFalse(resolve(s, Move(0, 0), Move(0, 0)).players[0].last_won)

    def test_oculus_infiltration(self):
        hand = tuple(card(n, 5, 2, c) for n, c in (("O", "Oculus"), ("A1", "A"), ("A2", "A"), ("B", "B")))
        self.assertEqual(effective_clans(hand), ("B", "A", "A", "B"))
        self.assertEqual(effective_clans(hand[:3]), ("A", "A", "A"))
        three = hand[:2] + (card("B", 5, 2, "B"), card("C", 5, 2, "C"))
        self.assertEqual(effective_clans(three)[0], "Oculus")

    def test_perfection_wins_by_ko(self):
        glibon = card("Glibon", 8, 0, ability="Perfection")
        after = resolve(start((glibon, FILLER), (FILLER, FILLER)), Move(0, 0), Move(0, 0))
        self.assertEqual(after.players[1].life, 0)

    def test_tie_break_wins_equal_attack(self):
        solomon = card("Solomon", 5, 1, ability="Tie-break", stars=5)
        opp = card("Opp", 5, 0, "Y", stars=1)
        s = start((solomon, FILLER), (opp, FILLER), leader=1)
        self.assertTrue(resolve(s, Move(0, 0), Move(0, 0)).players[0].last_won)

    def test_chained_conditions(self):
        e = parse_effect("Day: Courage: Attack +20")[0]
        self.assertEqual(e.condition, "day+courage")
        boost = card("G", 1, 0, ability="Day: Courage: Attack +20")
        opp = card("Opp", 9, 0, "Y")
        day = start((boost, FILLER), (opp, FILLER), day=True)
        night = start((boost, FILLER), (opp, FILLER), day=False)
        self.assertTrue(resolve(day, Move(0, 0), Move(0, 0)).players[0].last_won)
        self.assertFalse(resolve(night, Move(0, 0), Move(0, 0)).players[0].last_won)


if __name__ == "__main__":
    unittest.main()
