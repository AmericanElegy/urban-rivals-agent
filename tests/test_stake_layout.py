import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from urban_rivals.calibration import default_points, load_saved_calibration, save_calibration
from urban_rivals.engine import Move
from urban_rivals.vision import LocalOCR, RecognitionError, VisionSession, stake_layout
from test_vision import FakeReader


def hit(text, x, y, score=.97):
    return (text, score, x, y)


class StakeLayoutTests(unittest.TestCase):
    def test_reference_layout_when_nothing_is_found(self):
        layout = stake_layout([])
        self.assertEqual(layout["min"], (.578, .513))
        self.assertEqual(layout["plus"], (.874, .442))
        self.assertNotIn("fury", layout)
        self.assertEqual(layout["_source"]["min"], "default")

    def test_located_text_wins_and_shift_moves_icons(self):
        # The live failure: MIN drawn ~0.02 higher than the reference.
        layout = stake_layout([hit("MIN", .578, .493), hit("MAX", .874, .493)])
        self.assertEqual(layout["min"], (.578, .493))
        self.assertEqual(layout["_source"]["min"], "text")
        self.assertAlmostEqual(layout["plus"][0], .874)
        self.assertAlmostEqual(layout["plus"][1], .422)
        self.assertEqual(layout["_source"]["plus"], "layout")
        self.assertAlmostEqual(layout["confirm"][1], .655)

    def test_scaled_panel_is_fitted_per_axis(self):
        # Panel shrunk 25% about the canvas center.
        s = lambda v: .5 + (v - .5) * .75
        layout = stake_layout([hit("MIN", s(.578), s(.513)), hit("MAX", s(.874), s(.513)),
                               hit("CONFIRM THE STAKE", s(.722), s(.675))])
        self.assertAlmostEqual(layout["plus"][0], s(.874))
        self.assertAlmostEqual(layout["plus"][1], s(.442))

    def test_duplicate_labels_are_ignored(self):
        layout = stake_layout([hit("MIN", .2, .2), hit("min", .3, .3)])
        self.assertEqual(layout["_source"]["min"], "default")

    def test_fury_comes_from_text_or_calibration(self):
        self.assertEqual(stake_layout([hit("FURY", .7, .58)])["fury"], (.7, .58))
        cal = default_points()
        cal["fury_btn"] = {"x": .66, "y": .6}
        layout = stake_layout([], cal)
        self.assertEqual(layout["fury"], (.66, .6))
        self.assertEqual(layout["_source"]["fury"], "calibration")
        # Located text still beats calibration.
        self.assertEqual(stake_layout([hit("MIN", .5, .5)], cal)["min"], (.5, .5))

    def test_ability_text_mentioning_fury_is_not_a_button(self):
        self.assertNotIn("fury", stake_layout([hit("Fury: +3 Damage per turn left", .7, .5)]))

    def test_saved_calibration_only_when_file_exists(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "calibration.json"
            self.assertIsNone(load_saved_calibration(path))
            path.write_text("not json", encoding="utf-8")
            self.assertIsNone(load_saved_calibration(path))
            save_calibration(path, default_points())
            self.assertEqual(load_saved_calibration(path)["hand_0"], {"x": .2, "y": .72})


class LocateTests(unittest.TestCase):
    def test_locate_maps_boxes_back_to_canvas(self):
        from PIL import Image
        ocr = object.__new__(LocalOCR)
        seen = {}
        def detect(pixels, detail=False):
            seen["shape"] = pixels.shape
            # A word centered at padded-crop pixel (112, 62).
            return [([[102, 52], [122, 52], [122, 72], [102, 72]], "MIN", .99)], None
        ocr.detect = detect
        image = Image.new("RGB", (1318, 744))
        (text, score, x, y), = ocr.locate(image, (.5, .4, 1.0, .8))
        left, top = int(.5 * 1318), int(.4 * 744)
        self.assertEqual(text, "MIN")
        self.assertAlmostEqual(x, (left + 100) / 1318)
        self.assertAlmostEqual(y, (top + 50) / 744)

    def test_locate_drops_low_confidence(self):
        from PIL import Image
        ocr = object.__new__(LocalOCR)
        ocr.detect = lambda pixels, detail=False: ([([[0, 0], [1, 0], [1, 1], [0, 1]], "MAX", .5)], None)
        self.assertEqual(ocr.locate(Image.new("RGB", (1318, 744)), (0, 0, 1, 1)), [])


class TextReader(FakeReader):
    """FakeReader whose stake panel also exposes located buttons."""
    def __init__(self, found=()):
        super().__init__()
        self.found = list(found)
        self.damage = 4

    def number(self, image, box):
        return self.damage if box == (.74, .55, .815, .64) else self.attack

    def stake_targets(self, image, calibration=None):
        return stake_layout(self.found, calibration)


class FuryAutoPlayTests(unittest.TestCase):
    def panel_step(self, session):
        self.assertIsNone(session.step(None)["action"])
        return session.step(None)

    def open_panel(self, reader, move, pillz=5):
        reader.state = replace(reader.state, players=tuple(replace(p, pillz=pillz) for p in reader.state.players))
        s = VisionSession(reader, execute=True, iterations=10)
        s.step(None)
        s.step(None)
        s.pending = move
        reader.panel = True
        return s

    def test_fury_is_clicked_verified_then_pillz_added(self):
        r = TextReader([hit("MIN", .56, .49), hit("MAX", .85, .49), hit("FURY", .70, .58)])
        s = self.open_panel(r, Move(0, 1, True))
        self.assertEqual(self.panel_step(s)["action"]["x"], .56)          # MIN
        fury = self.panel_step(s)
        self.assertEqual((fury["action"]["x"], fury["action"]["y"]), (.70, .58))
        self.assertIn("FURY via text", fury["status"])
        r.damage = 6
        plus = self.panel_step(s)
        self.assertIn("Add one paid pill", plus["status"])
        r.attack = 14
        confirm = self.panel_step(s)
        self.assertIn("with Fury", confirm["status"])
        self.assertTrue(s.submitted.fury)

    def test_unregistered_fury_is_retried_once_then_stops(self):
        r = TextReader([hit("FURY", .70, .58)])
        s = self.open_panel(r, Move(0, 0, True))
        self.panel_step(s)                                              # MIN
        self.panel_step(s)                                              # Fury
        self.assertIn("retry once", self.panel_step(s)["status"])
        with self.assertRaisesRegex(RecognitionError, "expected 6"):
            self.panel_step(s)

    def test_missing_fury_button_submits_without_fury(self):
        r = TextReader([])
        s = self.open_panel(r, Move(0, 0, True))
        self.panel_step(s)                                              # MIN
        confirm = self.panel_step(s)
        self.assertIn("no Fury", confirm["status"])
        self.assertFalse(s.submitted.fury)

    def test_all_in_with_fury_never_uses_max(self):
        r = TextReader([hit("FURY", .70, .58)])
        s = self.open_panel(r, Move(0, 2, True), pillz=5)
        self.panel_step(s)
        self.panel_step(s)
        r.damage = 6
        self.assertIn("Add one paid pill", self.panel_step(s)["status"])

    def test_saved_calibration_drives_hand_clicks(self):
        cal = default_points()
        cal["hand_0"] = {"x": .25, "y": .71}
        s = VisionSession(FakeReader(), execute=True, iterations=10, calibration=cal)
        s.step(None)
        action = s.step(None)["action"]
        self.assertEqual((action["x"], action["y"]), (.25, .71))


if __name__ == "__main__":
    unittest.main()
