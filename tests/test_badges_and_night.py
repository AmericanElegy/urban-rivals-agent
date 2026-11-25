"""Running-effect badges and the night clock, from live matches.

Badges rarely show their Min/Max limit, and which HUD shows one does not say
whom it affects, so each is attributed to the played card that caused it. A
badge also pushes the clock aside, putting the yellow settings gear where the
day icon used to be read. Player names and scenery are blacked out.
"""
import unittest
from pathlib import Path

try:
    import cv2  # noqa: F401
    from PIL import Image
    HAVE_VISION = True
except ImportError:
    HAVE_VISION = False
try:
    import rapidocr_onnxruntime  # noqa: F401
    HAVE_OCR = HAVE_VISION
except ImportError:
    HAVE_OCR = False

from urban_rivals.vision import CanvasReader, Catalog

FRAMES = Path(__file__).parent / "fixtures" / "frames"


def frame(name):
    return Image.open(FRAMES / name).convert("RGB")


@unittest.skipUnless(HAVE_VISION, "vision extras not installed")
class NightClockTests(unittest.TestCase):
    def test_moon_is_night_where_the_clock_usually_sits(self):
        reader = CanvasReader.__new__(CanvasReader)
        self.assertIs(reader.day(frame("heal_badge_round3.png")), False)

    def test_moon_pushed_aside_by_a_badge_is_still_night(self):
        reader = CanvasReader.__new__(CanvasReader)
        self.assertIs(reader.day(frame("forfeit_partial_round4.png")), False)


@unittest.skipUnless(HAVE_OCR, "local OCR not installed")
class BadgeAttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = CanvasReader(catalog=Catalog(allow_star_fallback=True))

    def running(self, name):
        self.reader.initial_hand = None
        state = self.reader.board(frame(name), allow_mid_match=True).state
        self.assertIs(state.day, False)
        return [[(e.kind, e.minimum, e.maximum, e.owner) for e in p.effects] for p in state.players]

    def test_own_heal_without_a_drawn_limit(self):
        self.assertEqual(self.running("heal_badge_round3.png"), [[("heal", 0, 15, 0)], []])

    def test_our_poison_shown_on_the_opposing_hud(self):
        self.assertEqual(self.running("forfeit_partial_round4.png"), [[], [("poison", 3, 10000, 0)]])


if __name__ == "__main__":
    unittest.main()
