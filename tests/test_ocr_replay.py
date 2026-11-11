import unittest
from urban_rivals.vision import numeric_consensus, parse_timer
from urban_rivals.replay import compare_report


class NumericConfidenceTests(unittest.TestCase):
    def test_requires_agreement_and_high_score(self):
        self.assertEqual(numeric_consensus([("7",.99)]),"")
        self.assertEqual(numeric_consensus([("7",.94),("7",.93)]),"")
        self.assertEqual(numeric_consensus([("7",.99),("7",.90)]),"7")
        self.assertEqual(numeric_consensus([("0",.99),("0",.99)]),"0")

    def test_conflicting_strong_reads_abstain_even_with_majority(self):
        self.assertEqual(numeric_consensus([("7",.99),("1",.99),("7",.99)]),"")


class ReplayScoringTests(unittest.TestCase):
    def test_wrong_values_are_separate_from_unreadable(self):
        frame=dict(phase="round_board",round=1,seconds_left=100,observed_card=0,
                   resources={"our_life":15},used=[[],[]])
        actual=dict(phase="round_board",round=1,seconds_left=None,observed_card=1,
                    resources={"our_life":15},cards=[])
        checks=compare_report(actual,frame,[[],[]])
        outcomes={c["field"]:c["result"] for c in checks}
        self.assertEqual(outcomes["seconds_left"],"unreadable")
        self.assertEqual(outcomes["observed_card"],"wrong")
        self.assertEqual(outcomes["our_life"],"pass")

    def test_missing_observation_is_not_the_same_as_no_opponent_lead(self):
        frame=dict(phase="round_board",round=1,seconds_left=100,observed_card=None,
                   resources={},used=[[],[]])
        checks=compare_report(dict(phase="round_board",round=1,seconds_left=100),frame,[[],[]])
        self.assertEqual(next(c for c in checks if c["field"]=="observed_card")["result"],"wrong")


class TimerTests(unittest.TestCase):
    def test_isolated_clock_and_seconds_bounds(self):
        for text,expected in [("01:09",69),("00:30",30),("2:00",120)]:
            self.assertEqual(parse_timer(text),expected)
        for text in ("60:10","01:99","YOUR TURN 01:09","14:26",""):
            self.assertIsNone(parse_timer(text))


class PlayedPillTests(unittest.TestCase):
    def reader(self,marker,value):
        from urban_rivals.vision import CanvasReader
        reader=object.__new__(CanvasReader)
        reader.played_marker=lambda *args: marker
        def number(*args,**kwargs):
            if isinstance(value,Exception):
                raise value
            return value
        reader.number=number
        return reader

    def test_no_marker_does_not_read_artwork_as_a_counter(self):
        self.assertIsNone(self.reader(False,AssertionError()).played_pillz(None,.4,0))

    def test_free_pill_and_two_digit_counts(self):
        self.assertEqual(self.reader(True,1).played_pillz(None,.4,0),0)
        self.assertEqual(self.reader(True,13).played_pillz(None,.4,1),12)

    def test_invalid_or_unreadable_count_stops(self):
        from urban_rivals.vision import RecognitionError
        for value in (0,100,RecognitionError("unreadable")):
            with self.assertRaises(RecognitionError):
                self.reader(True,value).played_pillz(None,.4,0)


class DetectorConfigurationTests(unittest.TestCase):
    def test_normal_and_detailed_calls_restore_shared_settings(self):
        from types import SimpleNamespace
        from urban_rivals.vision import LocalOCR
        class Model:
            text_det=SimpleNamespace(limit_side_len=333)
            fail=False
            def __call__(self,pixels):
                self.seen=self.text_det.limit_side_len
                if self.fail:
                    raise RuntimeError("inference failed")
                return [],None
        reader=object.__new__(LocalOCR)
        reader.model=Model()
        for detail,expected in ((False,192),(True,736)):
            reader.detect(None,detail)
            self.assertEqual(reader.model.seen,expected)
            self.assertEqual(reader.model.text_det.limit_side_len,333)
        reader.model.fail=True
        with self.assertRaises(RuntimeError):
            reader.detect(None,True)
        self.assertEqual(reader.model.text_det.limit_side_len,333)
