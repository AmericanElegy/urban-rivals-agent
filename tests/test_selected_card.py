"""Our selected (enlarged) card must not be mistaken for a played card.

The frame is a live Training capture, round 3, with Brittany selected: its
purple and orange art matched the pill marker while its lit stars sat below
the resting star window, so the Advisor stopped with "Resource or attack
count is unreadable". Player names and unused scenery are blacked out.
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

FRAME = Path(__file__).parent / "fixtures" / "frames" / "selected_card_round3.png"


@unittest.skipUnless(HAVE_VISION, "vision extras not installed")
class SelectedCardMarkerTests(unittest.TestCase):
    def test_only_the_dimmed_cards_are_played(self):
        image = Image.open(FRAME).convert("RGB")
        for side in (0, 1):
            with self.subTest(side=side):
                self.assertEqual([CanvasReader.played_marker(image, x, side) for x in CanvasReader.CENTERS],
                                 [True, True, False, False])


@unittest.skipUnless(HAVE_OCR, "local OCR not installed")
class SelectedCardBoardTests(unittest.TestCase):
    def test_mid_match_board_reads_with_a_selected_card(self):
        reader = CanvasReader(catalog=Catalog(allow_star_fallback=True))
        board = reader.board(Image.open(FRAME).convert("RGB"), allow_mid_match=True)
        ours, theirs = board.state.players
        self.assertEqual((board.state.round, board.observed_card), (3, 2))
        self.assertEqual(board.spent, ((9, 0, None, None), (0, 5, None, None)))
        self.assertEqual((ours.life, ours.pillz, theirs.life, theirs.pillz), (12, 0, 8, 7))
        selected = ours.hand[2]
        self.assertEqual((selected.name, selected.power, selected.damage, selected.stars),
                         ("Brittany", 6, 2, 2))


if __name__ == "__main__":
    unittest.main()
