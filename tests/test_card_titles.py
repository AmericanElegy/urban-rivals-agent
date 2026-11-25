"""A fixed hand survives titles that are covered, garbled or raised high.

Frames are live Training captures with player names and scenery blacked out:
a Poison badge pushed the Forfeit button over the opponent's last title, which
was then read as a card named "Forfeit"; and an opponent lead raised higher
than usual was read as "KHKKHSSUK", stopping the Advisor.
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

from urban_rivals.vision import CanvasReader, Catalog

FRAMES = Path(__file__).parent / "fixtures" / "frames"


@unittest.skipUnless(HAVE_OCR, "local OCR not installed")
class CardTitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = CanvasReader(catalog=Catalog(allow_star_fallback=True))

    def setUp(self):
        self.reader.initial_hand = None

    def read(self, name):
        image = Image.open(FRAMES / name).convert("RGB")
        return self.reader.board(image, allow_mid_match=True)

    def test_high_raised_lead_is_named(self):
        board = self.read("raised_title_high.png")
        self.assertEqual((board.state.leader, board.observed_card), (1, 1))
        self.assertEqual(board.state.players[1].hand[1].name, "Karkass Cr")

    def test_garbled_title_keeps_the_known_card(self):
        known = self.read("raised_title_high.png").state.players[1].hand
        title = self.reader.title
        self.reader.raised_title = lambda *args, **kwargs: ""
        self.reader.title = lambda image, box, minimum=.8: (
            "KHKKHSSUK" if box[1] < .5 and box[0] < .4 < box[2] else title(image, box, minimum))
        try:
            board = self.read_again("raised_title_high.png")
        finally:
            del self.reader.raised_title, self.reader.title
        self.assertEqual(board.state.players[1].hand, known)

    def read_again(self, name):
        image = Image.open(FRAMES / name).convert("RGB")
        return self.reader.board(image, allow_mid_match=True)

    def test_forfeit_button_over_a_known_title_keeps_the_card(self):
        covered = self.read("advisor_round1.png").state.players[1].hand[3]
        board = self.read_again("forfeit_over_title.png")
        self.assertEqual(board.state.players[1].hand[3], covered)
        self.assertEqual(covered.name, "Igniss")

    def test_forfeit_button_before_the_hand_is_known_waits(self):
        self.assertIsNone(self.read("forfeit_over_title.png"))


if __name__ == "__main__":
    unittest.main()
