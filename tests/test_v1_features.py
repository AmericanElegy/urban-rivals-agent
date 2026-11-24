"""Unit tests for v1 features: StarCatalog, mode_policy, calibration, and multi-mode bridge."""
import tempfile
import unittest
from pathlib import Path

from urban_rivals.bridge import validate_frame
from urban_rivals.calibration import default_points, load_calibration, save_calibration
from urban_rivals.engine import Card, Player, State
from urban_rivals.mode_policy import recommend_move
from urban_rivals.star_catalog import StarCatalog


class StarCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = StarCatalog()

    def test_loads_all_official_cards_with_star_levels(self):
        self.assertGreaterEqual(len(self.catalog), 2500)

    def test_ratsky_per_star_abilities_differ_by_level(self):
        lv1 = self.catalog.resolve("Ratsky", stars=1)
        lv2 = self.catalog.resolve("Ratsky", stars=2)
        lv3 = self.catalog.resolve("Ratsky", stars=3)
        self.assertIsNotNone(lv1)
        self.assertIsNotNone(lv2)
        self.assertIsNotNone(lv3)
        self.assertIn("Attack", lv1.ability_text)
        self.assertIn("Power", lv2.ability_text)
        self.assertIn("Damage", lv3.ability_text)

    def test_resolves_intermediate_star_by_stats_when_stars_missing(self):
        evos = self.catalog.evolutions("Ratsky")
        self.assertGreaterEqual(len(evos), 3)
        resolved = self.catalog.resolve("Ratsky", stars=None, power=evos[0].power, damage=evos[0].damage)
        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.damage, evos[0].damage)

    def test_fuzzy_ocr_name_resolves_x_odus_to_x_0dus(self):
        evo = self.catalog.resolve("X-ODUS")
        self.assertIsNotNone(evo)
        self.assertEqual(evo.norm_name, "x0dus")

    def test_unmodeled_abilities_fall_back_gracefully_without_crashing(self):
        # Even cards with bespoke or persistent abilities resolve to a valid Card.
        evos = self.catalog.evolutions("ARN 2000")
        if evos:
            self.assertEqual(evos[-1].card.name, "ARN 2000")


class ModePolicyTests(unittest.TestCase):
    def test_recommends_moves_for_training_efc_and_tourney(self):
        c1 = Card("Alpha", 7, 5, 3, "Bangers")
        c2 = Card("Beta", 6, 4, 2, "Bangers")
        p0 = Player((c1, c2), life=12, pillz=12)
        p1 = Player((c2, c1), life=12, pillz=12)
        state = State((p0, p1), leader=0, round=1, day=True)

        for mode in ("training", "efc", "tourney"):
            rec = recommend_move(state, side=0, mode=mode)
            self.assertEqual(rec.mode, mode)
            self.assertIn(rec.card_index, (0, 1))
            self.assertGreaterEqual(rec.pillz, 0)
            self.assertLessEqual(rec.pillz, 12)


class CalibrationTests(unittest.TestCase):
    def test_save_and_load_calibration_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            pts = default_points()
            pts["hand_0"] = {"x": 0.21, "y": 0.74}
            saved = save_calibration(path, {"points": pts})
            loaded = load_calibration(path)
            self.assertEqual(saved["hand_0"], {"x": 0.21, "y": 0.74})
            self.assertEqual(loaded["hand_0"], {"x": 0.21, "y": 0.74})

    def test_rejects_out_of_range_coordinates(self):
        pts = default_points()
        pts["confirm_btn"] = {"x": 1.5, "y": 0.5}
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                save_calibration(Path(tmp) / "calibration.json", {"points": pts})


class MultiModeFrameTests(unittest.TestCase):
    def test_validate_frame_accepts_training_efc_tourney_and_advisor(self):
        for mode in ("training", "efc", "tourney"):
            validate_frame(
                {
                    "schema": "urban-rivals/frame/v1",
                    "url": "https://www.urban-rivals.com/game/play/webgl/",
                    "captured_at": 100.0,
                    "sequence": 1,
                    "run_id": "a" * 32,
                    "mode": mode,
                    "execute": False,
                    "advisor": True,
                },
                now=101.0,
            )


class LiveReadinessTests(unittest.TestCase):
    def test_read_resources_falls_back_to_counter_and_labels_errors(self):
        from urban_rivals.vision import CanvasReader, RecognitionError

        class FallbackOCR:
            def number(self, image, box, palette="white"):
                return ""

            def counter(self, image, box):
                return "12"

        reader = object.__new__(CanvasReader)
        reader.ocr = FallbackOCR()
        res = reader.read_resources(None)
        self.assertEqual(res["our_life"], 12)
        self.assertEqual(res["opponent_pillz"], 12)

        class FailingOCR:
            def number(self, image, box, palette="white"):
                return ""

            def counter(self, image, box):
                return ""

        reader.ocr = FailingOCR()
        with self.assertRaisesRegex(RecognitionError, r"our_life:"):
            reader.read_resources(None)

    def test_advisor_supports_mid_match_rounds_and_open_stake_panel(self):
        from urban_rivals.vision import Board, VisionSession

        c1 = Card("Alpha", 7, 5, 3, "Bangers")
        c2 = Card("Beta", 6, 4, 2, "Bangers")
        c3 = Card("Gamma", 7, 4, 3, "Bangers")
        c4 = Card("Delta", 5, 5, 2, "Bangers")
        p0 = Player((c1, c2, c3, c4), life=12, pillz=10, used=(0,))
        p1 = Player((c2, c1, c4, c3), life=10, pillz=9, used=(1,))
        state_r2 = State((p0, p1), leader=0, round=2, day=True)

        class AdvisorReader:
            CENTERS = (0.22, 0.40, 0.59, 0.77)

            def __init__(self):
                self.stake = False
                self.saw_allow_mid_match = False

            def text(self, image, box, minimum=0.85):
                return "CONFIRM THE STAKE" if self.stake else "ROUND 2/4 YOUR TURN"

            def board(self, image, previous=None, submitted=None, allow_mid_match=False):
                self.saw_allow_mid_match = allow_mid_match
                return Board(state_r2, None, 60, ((2, None, None, None), (None, 3, None, None)))

        reader = AdvisorReader()
        session = VisionSession(reader=reader, execute=False, mode="training", advisor=True)
        res1 = session.step(None)
        self.assertTrue(reader.saw_allow_mid_match)
        self.assertIsNone(res1["action"])
        self.assertIn("recommendation", res1)

        reader.stake = True
        res2 = session.step(None)
        self.assertIsNone(res2["action"])
        self.assertIn("stake panel", res2["status"].lower())

    def test_recommend_move_respects_allow_fury_false_for_autoplay(self):
        c1 = Card("Alpha", 7, 5, 3, "Bangers")
        c2 = Card("Beta", 6, 4, 2, "Bangers")
        p0 = Player((c1, c2), life=12, pillz=12)
        p1 = Player((c2, c1), life=12, pillz=12)
        state = State((p0, p1), leader=0, round=1, day=True)

        for mode in ("training", "efc", "tourney"):
            rec = recommend_move(state, side=0, mode=mode, allow_fury=False)
            self.assertFalse(rec.fury)


if __name__ == "__main__":
    unittest.main()
