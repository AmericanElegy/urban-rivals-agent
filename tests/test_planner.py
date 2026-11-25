import os
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest import mock

from urban_rivals.engine import Card, Move, Player, State, parse_effect, resolve
from urban_rivals.mode_policy import recommend_move
from urban_rivals.planner import plan, win_probability


def card(name, power, damage, clan="Plain", bonus=""):
    return Card(name, power, damage, 3, clan, (), parse_effect(bonus))


PLAIN = tuple(card(f"P{i}", 7, 4) for i in range(4))


class PlannerTests(unittest.TestCase):
    def test_symmetric_start_is_near_even_and_not_all_in(self):
        s = State((Player(PLAIN), Player(PLAIN)))
        p = plan(s, 0)
        self.assertAlmostEqual(p.win_probability, .5, delta=.12)
        best = max(zip(p.probabilities, p.moves), key=lambda x: x[0])[1]
        # Spending all 12 in round 1 leaves rounds 2-4 unwinnable.
        self.assertLess(best.pillz, 12)

    def test_finished_match_is_exact(self):
        a = Player(PLAIN[:1], life=5, pillz=0, used=(0,))
        b = Player(PLAIN[:1], life=3, pillz=0, used=(0,))
        self.assertEqual(win_probability(State((a, b), round=2)), 1.0)

    def test_rollouts_see_poison_ticking_later(self):
        theirs = tuple(card(f"O{i}", 7, 4, "Other") for i in range(4))
        freaks = tuple(card(f"F{i}", 7, 4, "Freaks", "Poison 2, Min 3") for i in range(4))
        plain = tuple(card(f"Q{i}", 7, 4, "Freaks") for i in range(4))
        # Same round-1 win; only the Poison differs.
        won_with_poison = resolve(State((Player(freaks), Player(theirs))), Move(0, 3), Move(0, 0))
        won_plain = resolve(State((Player(plain), Player(theirs))), Move(0, 3), Move(0, 0))
        self.assertEqual([e.kind for e in won_with_poison.players[1].effects], ["poison"])
        self.assertGreater(win_probability(won_with_poison, 64), win_probability(won_plain, 64))

    def test_unverified_later_pairing_does_not_stop_planning(self):
        state = State((Player(PLAIN), Player(PLAIN)))
        with mock.patch("urban_rivals.planner.resolve", side_effect=ValueError("not verified")):
            self.assertEqual(win_probability(state, 3), .5)

    def test_responder_answers_the_observed_card(self):
        s = State((Player(PLAIN), Player(PLAIN)), leader=1)
        p = plan(s, 0, observed_card=2)
        self.assertTrue(all(m.card in range(4) for m in p.moves))
        self.assertEqual(p.lead_card, 2)

    def test_recommendation_reports_planner_odds_quickly(self):
        s = State((Player(PLAIN), Player(PLAIN)), day=True)
        start = time.perf_counter()
        rec = recommend_move(s, 0, mode="training")
        self.assertLess(time.perf_counter() - start, 15)
        self.assertTrue(0 < rec.win_prob < 1)
        self.assertEqual(rec.value, rec.win_prob)
        again = recommend_move(s, 0, mode="training")
        self.assertEqual((again.card_index, again.pillz, again.fury), (rec.card_index, rec.pillz, rec.fury))


class WorkerCleanupTests(unittest.TestCase):
    def test_workers_exit_when_the_bridge_is_killed(self):
        script = textwrap.dedent("""
            import os, time
            from urban_rivals import planner
            if __name__ == '__main__':
                planner.enable_parallel(2)
                print(planner._POOL.submit(os.getpid).result(), flush=True)
                time.sleep(60)
        """)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "parent.py"
            path.write_text(script, encoding="utf-8")
            root = str(Path(__file__).resolve().parents[1])
            # The venv launcher would be killed instead of the real parent.
            python = getattr(sys, "_base_executable", sys.executable)
            parent = subprocess.Popen([python, str(path)], stdout=subprocess.PIPE, text=True,
                                      env={**os.environ, "PYTHONPATH": root})
            try:
                worker = int(parent.stdout.readline())
                # A failing run must not leave the worker holding test output open.
                self.addCleanup(_stop, worker)
                self.assertTrue(_alive(worker))
            finally:
                parent.kill()
                parent.wait(10)
                parent.stdout.close()
            deadline = time.monotonic() + 10
            while _alive(worker) and time.monotonic() < deadline:
                time.sleep(.1)
            self.assertFalse(_alive(worker))


def _stop(pid):
    if _alive(pid):
        os.kill(pid, signal.SIGTERM)


def _alive(pid):
    if os.name == "nt":
        listing = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                 capture_output=True, text=True).stdout
        return str(pid) in listing.split()
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


if __name__ == "__main__":
    unittest.main()
