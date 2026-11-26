"""Star counts on live cards: a green star bar and bright art beside the bar.

Carcharine's highlighted (green) bar was counted as one star instead of three,
and yellow art beside Soushee's bar made its two stars unreadable. Levels with
identical printed stats depend on this count. Player names and scenery are
blacked out.
"""
import unittest
from pathlib import Path

try:
    import cv2  # noqa: F401
    from PIL import Image
    HAVE_VISION = True
except ImportError:
    HAVE_VISION = False

from urban_rivals.vision import CanvasReader

FRAMES = Path(__file__).parent / "fixtures" / "frames"


@unittest.skipUnless(HAVE_VISION, "vision extras not installed")
class LiveStarTests(unittest.TestCase):
    def stars(self, name, slot, y):
        image = Image.open(FRAMES / name).convert("RGB")
        return CanvasReader.stars(CanvasReader.__new__(CanvasReader), image,
                                  CanvasReader.CENTERS[slot], y)

    def test_green_highlighted_bar(self):
        self.assertEqual(self.stars("green_star_bar_round1.png", 1, .335), 3)

    def test_bright_art_beside_the_bar(self):
        self.assertEqual(self.stars("advisor_round1.png", 1, .785), 2)

    def test_lit_stars_exclude_the_grey_unearned_one(self):
        self.assertEqual(self.stars("advisor_round1.png", 1, .335), 3)


if __name__ == "__main__":
    unittest.main()
