"""A foil card with purple art is not a played card.

The frame is round 1 of a live Training match: Selsya Cr's purple foil art
matched the pill marker and hid its stars, so the Advisor stopped with
"Resource or attack count is unreadable". Player names and scenery are
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
try:
    import rapidocr_onnxruntime  # noqa: F401
    HAVE_OCR = HAVE_VISION
except ImportError:
    HAVE_OCR = False

from urban_rivals.vision import CanvasReader, Catalog

FRAME = Path(__file__).parent / "fixtures" / "frames" / "foil_card_round1.png"


@unittest.skipUnless(HAVE_VISION, "vision extras not installed")
class FoilCardMarkerTests(unittest.TestCase):
    def test_no_card_is_played_in_the_opening(self):
        image = Image.open(FRAME).convert("RGB")
        for side in (0, 1):
            with self.subTest(side=side):
                self.assertEqual([CanvasReader.played_marker(image, x, side) for x in CanvasReader.CENTERS],
                                 [False] * 4)


@unittest.skipUnless(HAVE_OCR, "local OCR not installed")
class FoilCardBoardTests(unittest.TestCase):
    def test_opening_board_reads(self):
        reader = CanvasReader(catalog=Catalog(allow_star_fallback=True))
        board = reader.board(Image.open(FRAME).convert("RGB"), allow_mid_match=True)
        foil = board.state.players[1].hand[3]
        self.assertEqual((foil.name, foil.power, foil.damage), ("Selsya Cr", 1, 3))
        self.assertEqual(board.spent, ((None,) * 4, (None,) * 4))


if __name__ == "__main__":
    unittest.main()
