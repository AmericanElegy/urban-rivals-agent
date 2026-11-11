"""Transport-independent automatic turn controller.

The vision adapter must provide a public state plus stable match/turn IDs.
An action is submitted at most once per turn. Unknown submit outcomes are never
retried automatically: a refreshed observation/receipt is required.
"""
from dataclasses import dataclass
import random
from typing import Protocol
from .engine import State, Move
from .solver import advise


@dataclass(frozen=True)
class Observation:
    match_id: str
    state: State
    side: int
    our_turn: bool
    observed_card: int | None = None
    mode: str = "training"
    confidence: float = 1.0


class Adapter(Protocol):
    def observe(self) -> Observation: ...
    def submit(self, move: Move, observation: Observation) -> None: ...


class Controller:
    def __init__(self, adapter: Adapter, iterations=1000, seed=None):
        self.adapter = adapter
        self.iterations = iterations
        self.rng = random.Random(seed)
        self.attempted = set()

    def step(self):
        obs = self.adapter.observe()
        if obs.mode != "training":
            raise ValueError("Live test controller is limited to Training Bot")
        if not obs.match_id or not 0.99 <= obs.confidence <= 1:
            raise ValueError("Uncertain game observation; stop for review")
        if not obs.our_turn or obs.state.terminal:
            return None
        key = (obs.match_id, obs.state.round, obs.side)
        if key in self.attempted:
            return None
        advice = advise(obs.state, obs.side, obs.observed_card, self.iterations)
        move = self.rng.choices(advice.moves, weights=advice.probabilities, k=1)[0]
        # Reobserve after computation. Never send a move based on a stale screen.
        if self.adapter.observe() != obs:
            raise ValueError("Game changed during calculation; recompute on next step")
        self.attempted.add(key)
        self.adapter.submit(move, obs)
        return move
