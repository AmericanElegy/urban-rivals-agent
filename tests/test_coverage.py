import unittest

from urban_rivals.coverage import catalog_coverage, gap_category


def rejected(ability,reason,clan="Test"):
    return {"reason":reason,"record":{"ability":ability,"bonus":"No Bonus","clan":clan}}


class CoverageInventoryTests(unittest.TestCase):
    def test_primary_gap_categories_are_explicit(self):
        cases=(
            (rejected("Poison 2, Min 3","Unsupported effect"),"persistent_round_effects"),
            (rejected("Stop: Power +3","Unsupported condition: Stop"),"compound_conditions"),
            (rejected("No Ability","Clock-specific, leader or infiltration rules require separately verified entries","Oculus"),"special_clans"),
            (rejected("Cancel Opp. Pillz & Life Modif","Unsupported effect"),"resource_modification_cancellation"),
            (rejected("Copy Opp. Bonus","Unsupported effect"),"remaining_copy_variants"),
            (rejected("Power Impose","Unsupported effect"),"impose_mechanics"),
            (rejected("+1 Damage Per Life Lost Max. 7","Unsupported effect"),"advanced_scaling_and_team_effects"),
            (rejected("Dope 3, Max. 4","Unsupported effect"),"ordinary_parser_and_mechanics_tail"),
        )
        for entry,expected in cases:
            with self.subTest(expected=expected):self.assertEqual(gap_category(entry),expected)

    def test_gap_inventory_is_exhaustive(self):
        result=catalog_coverage()
        self.assertEqual(sum(result["gap_categories"].values()),result["rejected_source_records"])
        self.assertEqual(sum(result["special_clan_gaps"].values()),result["gap_categories"]["special_clans"])
        self.assertEqual(sum(result["persistent_effect_gaps"].values()),result["gap_categories"]["persistent_round_effects"])
