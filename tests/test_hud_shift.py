"""Resource counters shifted by a running-effect badge (live Tourney capture)."""
import unittest

from urban_rivals.vision import CanvasReader, RecognitionError


class ShiftedHudOCR:
    """Counters as measured on a 1318x744 board with a "+1 HEAL - MAX 15" badge."""
    def __init__(self, name_left=.6836, badge=("+1", "HEAL·MAX15")):
        self.name_left = name_left
        self.badge = badge

    def number(self, image, box):
        x = (box[0] + box[2]) / 2
        y = (box[1] + box[3]) / 2
        if y < .5:
            return "12" if x < .275 else "6"
        if .53 <= x <= .56:
            return "12"
        if .605 <= x <= .64:
            return "9"
        return ""

    def tokens(self, image, box, minimum=.5):
        if box[1] < .5:
            return []
        found = [("12", .527, .99), ("Elegy", self.name_left, .99)]
        if self.badge:
            found += [(self.badge[0], .873, .92), (self.badge[1], .899, .95)]
        return [t for t in found if box[0] <= t[1] <= box[2]]


class HudShiftTests(unittest.TestCase):
    def reader(self, ocr):
        reader = CanvasReader.__new__(CanvasReader)
        reader.ocr = ocr
        return reader

    def test_badge_shift_is_followed_from_the_name_anchor(self):
        self.assertEqual(self.reader(ShiftedHudOCR()).read_resources(None),
                         {"our_life": 9, "opponent_life": 12, "our_pillz": 12, "opponent_pillz": 6})

    def test_unconfirmed_shift_still_stops(self):
        # An anchor that would place the counters elsewhere never reads both.
        with self.assertRaises(RecognitionError):
            self.reader(ShiftedHudOCR(name_left=.95)).read_resources(None)

    def test_running_effect_badge_is_read_for_mid_match_starts(self):
        ours, theirs = self.reader(ShiftedHudOCR()).effect_badges(None)
        self.assertEqual((ours[0].kind, ours[0].life, ours[0].maximum, ours[0].owner), ("heal", 1, 15, 0))
        self.assertEqual(theirs, ())

    def test_inconsistent_badge_is_ignored(self):
        ours, _ = self.reader(ShiftedHudOCR(badge=("-1", "HEAL·MAX15"))).effect_badges(None)
        self.assertEqual(ours, ())


if __name__ == "__main__":
    unittest.main()
