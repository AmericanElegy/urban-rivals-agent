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
