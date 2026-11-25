"""Checks against real captured canvases in tests/fixtures/frames."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from urban_rivals.bridge import save_failure_frames
from urban_rivals.vision import CanvasReader

FRAMES = Path(__file__).parent / "fixtures" / "frames"


def rapidocr_available():
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


class HealButtonFrameTests(unittest.TestCase):
    """Round 4 frame where a HEAL button pushed our bottom bar ~0.11 left."""

    def setUp(self):
        self.image = Image.open(FRAMES / "round4-heal-button.png").convert("RGB")

    def test_heart_is_found_and_shift_measured(self):
        cx, cy = CanvasReader.find_our_heart(self.image)
        self.assertAlmostEqual(cx, 849 / 1318, delta=.004)
        reader = object.__new__(CanvasReader)
        reader.hud_scale = 1.0
        self.assertAlmostEqual(reader.bottom_bar_shift(self.image), -.114, delta=.006)

    @unittest.skipUnless(rapidocr_available(), "needs local OCR model")
    def test_resources_read_despite_heal_button(self):
        from urban_rivals.vision import LocalOCR
        reader = CanvasReader(ocr=LocalOCR())
        reader.hud_scale = 1.0
        resources = reader.read_resources(self.image)
        self.assertEqual(resources, {"our_life": 13, "opponent_life": 16, "our_pillz": 9, "opponent_pillz": 7})


class FailureFrameTests(unittest.TestCase):
    def test_last_frames_and_error_are_saved(self):
        frames = [(7, Image.new("RGB", (8, 8))), (8, Image.new("RGB", (8, 8)))]
        with tempfile.TemporaryDirectory() as d:
            folder = save_failure_frames(d, "abcdef123456", "MIN did not confirm", frames)
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             ["error.txt", "frame-0007.png", "frame-0008.png"])
            self.assertIn("abcdef12", folder.name)

    def test_no_frames_saves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(save_failure_frames(d, "x", "e", []))


if __name__ == "__main__":
    unittest.main()


class LegendaryLeadFrameTests(unittest.TestCase):
    """Tourney round 1: opponent leads with Nega D Ld (white stars, no disc)."""

    def setUp(self):
        self.image = Image.open(FRAMES / "tourney-r1-legendary-lead.png").convert("RGB")

    def test_white_stars_are_counted(self):
        import numpy as np
        pixels = np.array(self.image)
        self.assertEqual(CanvasReader.white_stars(pixels, CanvasReader.CENTERS[3], .335), 5)

    @unittest.skipUnless(rapidocr_available(), "needs local OCR model")
    def test_board_reads_legendary_lead(self):
        from urban_rivals.vision import Catalog, LocalOCR
        reader = CanvasReader(ocr=LocalOCR(), catalog=Catalog(allow_star_fallback=True))
        reader.hud_scale = 1.0
        board = reader.board(self.image)
        self.assertEqual((board.state.leader, board.observed_card), (1, 3))
        nega = board.state.players[1].hand[3]
        self.assertEqual((nega.name, nega.power, nega.damage, nega.stars), ("Nega D Ld", 8, 8, 5))
        self.assertEqual([c.name for c in board.state.players[0].hand],
                         ["Hula", "Brittany", "Diana", "Malicia"])
