"""Short clocks and a partly covered title during a live Advisor match.

The frame is round 4 of a Training-screen match joined late: the Forfeit button
covered part of an already played opposing card, read as "SEL Forfei", and the
Advisor then stopped for having under 12 seconds although it never clicks.
Player names and scenery are blacked out.
"""
import unittest
from pathlib import Path

try:
    import cv2  # noqa: F401
    import rapidocr_onnxruntime  # noqa: F401
    from PIL import Image
    HAVE_OCR = True
except ImportError:
    HAVE_OCR = False

from urban_rivals.vision import CanvasReader, Catalog, RecognitionError

FRAME = Path(__file__).parent / "fixtures" / "frames" / "forfeit_partial_round4.png"


@unittest.skipUnless(HAVE_OCR, "local OCR not installed")
class AdvisorClockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = CanvasReader(catalog=Catalog(allow_star_fallback=True))
        cls.image = Image.open(FRAME).convert("RGB")

    def setUp(self):
        self.reader.initial_hand = None
        self.reader.turn_seconds = lambda image: 9

    def test_advisor_reads_a_board_with_a_short_clock(self):
        board = self.reader.board(self.image, allow_mid_match=True)
        self.assertEqual((board.state.round, board.seconds_left), (4, 9))
        covered = board.state.players[1].hand[3]
        self.assertEqual(covered.name, "Played-1-4")
        self.assertIn(3, board.state.players[1].used)

    def test_auto_play_still_stops_with_a_short_clock(self):
        with self.assertRaises(RecognitionError):
            self.reader.board(self.image)


if __name__ == "__main__":
    unittest.main()
