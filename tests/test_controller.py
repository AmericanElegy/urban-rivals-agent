import unittest
from dataclasses import replace
from urban_rivals.controller import Controller, Observation
from urban_rivals.engine import Card, Player, State


class FakeAdapter:
    def __init__(self):
        card = Card("Test", 7, 4, 3, "Test")
        self.obs = Observation("test-match", State((Player((card,), pillz=1), Player((card,), pillz=1))), 0, True)
        self.sent = []
        self.fail = False

    def observe(self):
        return self.obs

    def submit(self, move, observation):
        self.sent.append(move)
        if self.fail:
            raise OSError("Unknown submission outcome")


class ControllerTests(unittest.TestCase):
    def test_submits_once(self):
        a = FakeAdapter()
        c = Controller(a, iterations=30, seed=1)
        self.assertIsNotNone(c.step())
        self.assertIsNone(c.step())
        self.assertEqual(len(a.sent), 1)

    def test_unknown_outcome_not_retried(self):
        a = FakeAdapter()
        a.fail = True
        c = Controller(a, iterations=30)
        with self.assertRaises(OSError):
            c.step()
        self.assertIsNone(c.step())
        self.assertEqual(len(a.sent), 1)

    def test_blocks_other_modes_and_uncertain_screen(self):
        a = FakeAdapter()
        c = Controller(a)
        for obs in (replace(a.obs, mode="efc"), replace(a.obs, confidence=.5)):
            a.obs = obs
            with self.assertRaises(ValueError):
                c.step()
        self.assertFalse(a.sent)

    def test_does_not_play_opponent_turn(self):
        a = FakeAdapter()
        a.obs = replace(a.obs, our_turn=False)
        self.assertIsNone(Controller(a).step())

    def test_changed_screen_not_submitted(self):
        a = FakeAdapter()
        initial = a.obs
        observations = iter((initial, replace(initial, our_turn=False)))
        a.observe = lambda: next(observations)
        with self.assertRaises(ValueError):
            Controller(a, iterations=30).step()
        self.assertFalse(a.sent)
