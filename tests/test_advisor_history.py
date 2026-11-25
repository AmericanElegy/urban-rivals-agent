"""The Advisor must carry round results forward although it never clicks.

Frames are rounds 1 and 2 of a live Training match: Brittany (no paid pillz)
lost to Ghenom (one paid pill). The Advisor never records a submitted move, so
it dropped who won the last round and every running effect. Player names and
unused scenery are blacked out.
"""
import unittest
from dataclasses import replace
from pathlib import Path

try:
    import cv2  # noqa: F401
    import rapidocr_onnxruntime  # noqa: F401
    from PIL import Image
    HAVE_OCR = True
except ImportError:
    HAVE_OCR = False

from urban_rivals.engine import Persistent
from urban_rivals.vision import CanvasReader, Catalog

FRAMES = Path(__file__).parent / "fixtures" / "frames"


@unittest.skipUnless(HAVE_OCR, "local OCR not installed")
class AdvisorHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = CanvasReader(catalog=Catalog(allow_star_fallback=True))
        cls.first = Image.open(FRAMES / "advisor_round1.png").convert("RGB")
        cls.second = Image.open(FRAMES / "advisor_round2.png").convert("RGB")

    def setUp(self):
        self.reader.initial_hand = None

    def read(self, image, previous=None):
        return self.reader.board(image, previous, None, allow_mid_match=True)

    def test_round_result_is_reconstructed_from_the_dimmed_cards(self):
        opening = self.read(self.first).state
        self.assertEqual((opening.round, opening.leader), (1, 1))
        state = self.read(self.second, opening).state
        self.assertEqual((state.round, state.leader), (2, 0))
        self.assertEqual([p.last_won for p in state.players], [False, True])
        self.assertEqual([p.life for p in state.players], [8, 9])

    def test_running_effects_survive_a_second_read_of_the_round(self):
        settled = self.read(self.second, self.read(self.first).state).state
        poison = Persistent("poison", "poison", -2, 0, 3, 10000, 1)
        ours = replace(settled.players[0], effects=(poison,))
        settled = replace(settled, players=(ours, settled.players[1]))
        again = self.read(self.second, settled).state
        self.assertEqual(again, settled)


if __name__ == "__main__":
    unittest.main()
