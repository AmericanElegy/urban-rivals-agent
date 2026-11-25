"""Whole-match planner: this round's hidden-bid game, scored by match win odds.

The old solver scored the state after one round with a life/pillz formula, so
it could not see that spending every pill in round 1 leaves nothing for rounds
2-4, or that a Poison won now keeps ticking. Here every outcome of this round
is scored by playing the rest of the match out many times (Monte Carlo
rollouts) and counting wins, using the full engine, Poison included.

The rollout policy stands in for "how players usually play" and is the place
where learned tendencies from recorded matches will plug in later.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
import multiprocessing
import os
import random
import threading
import zlib

from .engine import Move, State, resolve

ROLLOUTS = 16
ITERATIONS = 400


def _final(state: State) -> float:
    """Side-0 result of a finished match: 1 win, 0 loss, .5 tie."""
    a, b = state.players
    return 1.0 if a.life > b.life else 0.0 if a.life < b.life else 0.5


def rollout_move(rng: random.Random, state: State, side: int) -> Move:
    """A plausible, non-strategic move: random card, pillz paced over the rounds left."""
    p = state.players[side]
    cards = [i for i in range(len(p.hand)) if i not in p.used]
    card = rng.choice(cards)
    rounds_left = len(cards)
    if rounds_left == 1:
        fury = p.pillz >= 3 and rng.random() < .5
        return Move(card, p.pillz - 3 * fury, fury)
    pace = p.pillz / rounds_left
    pillz = min(p.pillz, max(0, round(rng.uniform(0, 2 * pace))))
    fury = p.pillz - pillz >= 3 and rng.random() < .1
    return Move(card, pillz, fury)


@lru_cache(maxsize=200_000)
def win_probability(state: State, rollouts: int = ROLLOUTS) -> float:
    """Estimated chance side 0 wins from this public state (ties count half)."""
    if state.terminal:
        return _final(state)
    # Seeded from the state's text so every worker process agrees.
    rng = random.Random(zlib.crc32(repr(state).encode()))
    return sum(_rollout(rng, state) for _ in range(rollouts)) / rollouts


def _rollout(rng: random.Random, state: State) -> float:
    """One random finish of the match, scored for side 0.

    The engine refuses card pairings it has not verified. A later, hypothetical
    round must not end the Advisor, so draw again and, if no pairing can be
    resolved, score the match on the life reached so far.
    """
    while not state.terminal:
        for _ in range(8):
            try:
                state = resolve(state, rollout_move(rng, state, 0), rollout_move(rng, state, 1))
                break
            except ValueError:
                continue
        else:
            break
    return _final(state)


_POOL: ProcessPoolExecutor | None = None


def _exit_with_parent() -> None:
    """Worker setup: a force-stopped bridge must not leave workers running."""
    parent = multiprocessing.parent_process()

    def watch():
        parent.join()
        os._exit(0)

    threading.Thread(target=watch, daemon=True).start()


def enable_parallel(workers: int | None = None) -> int:
    """Spread leaf rollouts over CPU cores (kept alive by the bridge process)."""
    global _POOL
    if _POOL is None:
        workers = workers or max(1, (os.cpu_count() or 2) - 1)
        if workers > 1:
            _POOL = ProcessPoolExecutor(max_workers=workers, initializer=_exit_with_parent)
    return getattr(_POOL, "_max_workers", 1)


def _leaf(args):
    state, rollouts = args
    return win_probability(state, rollouts)


_LEAF_CACHE: dict = {}


def _evaluate_all(states, rollouts):
    """Win odds for many leaf states, using every core when enabled.

    Results are cached in this (parent) process so repeated frames of the same
    board are instant even when the work ran in pool workers.
    """
    known = {}
    todo = []
    for s in dict.fromkeys(states):
        key = (s, rollouts)
        if key in _LEAF_CACHE:
            known[s] = _LEAF_CACHE[key]
        else:
            todo.append(s)
    if _POOL is not None and len(todo) > 64:
        values = list(_POOL.map(_leaf, [(s, rollouts) for s in todo],
                                chunksize=max(8, len(todo) // 64)))
    else:
        values = [win_probability(s, rollouts) for s in todo]
    if len(_LEAF_CACHE) > 300_000:
        _LEAF_CACHE.clear()
    for s, v in zip(todo, values):
        _LEAF_CACHE[(s, rollouts)] = v
        known[s] = v
    return known


OUR_BIDS = (0, 1, 2, 3, 4, 5, 6, 8, 10)
THEIR_BIDS = (0, 1, 2, 3, 4, 6, 8)
SECONDS_BUDGET = 6.0
SECONDS_PER_RESOLVE = 150e-6


def _bid_levels(pillz: int, levels) -> list[int]:
    """Bids considered: the listed levels that are affordable, plus all-in."""
    return sorted({n for n in levels if n <= pillz} | {pillz})


def _moves(state: State, side: int, levels, card: int | None = None,
           allow_fury: bool = True) -> tuple[Move, ...]:
    p = state.players[side]
    moves = []
    for i in range(len(p.hand)):
        if i in p.used or (card is not None and i != card):
            continue
        moves += [Move(i, n) for n in _bid_levels(p.pillz, levels)]
        if allow_fury and p.pillz >= 3:
            moves += [Move(i, n, True) for n in _bid_levels(p.pillz - 3, levels)]
    return tuple(moves)


def _solve(matrix, iterations=ITERATIONS):
    """Averaged regret matching for the row player of a zero-sum matrix."""
    try:
        import numpy as np
    except ImportError:  # pragma: no cover - vision extras always include numpy
        from .solver import matrix_game
        eq = matrix_game(matrix, iterations)
        return list(eq.row), list(eq.column), eq.value
    m = np.asarray(matrix, dtype=float)
    n, k = m.shape
    regret_r, regret_c = np.zeros(n), np.zeros(k)
    total_r, total_c = np.zeros(n), np.zeros(k)
    for _ in range(iterations):
        pr = np.maximum(regret_r, 0)
        pr = pr / pr.sum() if pr.sum() > 0 else np.full(n, 1 / n)
        pc = np.maximum(regret_c, 0)
        pc = pc / pc.sum() if pc.sum() > 0 else np.full(k, 1 / k)
        rv = m @ pc
        cv = pr @ m
        value = pr @ rv
        regret_r += rv - value
        regret_c += value - cv
        total_r += pr
        total_c += pc
    pr, pc = total_r / iterations, total_c / iterations
    return pr.tolist(), pc.tolist(), float(pr @ m @ pc)


@dataclass(frozen=True)
class Plan:
    moves: tuple[Move, ...]
    probabilities: tuple[float, ...]
    win_probability: float
    lead_card: int


@lru_cache(maxsize=256)
def plan(state: State, side: int = 0, observed_card: int | None = None,
         allow_fury: bool = True, rollouts: int = ROLLOUTS) -> Plan:
    """Best mixed strategy for `side` this round, valued by match win odds."""
    if state.terminal or side not in (0, 1):
        raise ValueError("Require a nonterminal state and side 0 or 1")
    leader = state.leader
    if side != leader and observed_card is None:
        raise ValueError("Responder must supply the observed opponent card")
    if side == leader and observed_card is not None:
        raise ValueError("Leader cannot observe an opponent lead card")
    me = state.players[side]
    if side == leader:
        games = [(_moves(state, side, OUR_BIDS, card, allow_fury), _moves(state, 1 - side, THEIR_BIDS))
                 for card in range(len(me.hand)) if card not in me.used]
    else:
        games = [(_moves(state, side, OUR_BIDS, None, allow_fury),
                  _moves(state, 1 - side, THEIR_BIDS, observed_card))]
    outcomes = {}
    for rows, cols in games:
        for a in rows:
            for b in cols:
                outcomes[(a, b)] = resolve(state, *((a, b) if side == 0 else (b, a)))
    leaves = set(outcomes.values())
    # Keep the first frame inside the bridge's deadline: fewer rollouts when
    # there are many leaves and few cores, never fewer than 4.
    rounds_left = max(1, 4 - state.round)
    cost = (
        len(leaves) * rounds_left * SECONDS_PER_RESOLVE / max(1, getattr(_POOL, "_max_workers", 1)))
    rollouts = max(4, min(rollouts, int(SECONDS_BUDGET / cost))) if cost else rollouts
    odds = _evaluate_all(leaves, rollouts)

    def value(mine: Move, theirs: Move) -> float:
        p0 = odds[outcomes[(mine, theirs)]]
        return p0 if side == 0 else 1 - p0

    if side == leader:
        # The responder sees our card before bidding: one game per card we might lead.
        best = None
        for rows, cols in games:
            card = rows[0].card
            matrix = [[value(a, b) for b in cols] for a in rows]
            pr, _, v = _solve(matrix)
            if best is None or v > best[0]:
                best = (v, rows, pr, card)
        v, rows, pr, card = best
        return Plan(rows, tuple(pr), v, card)
    rows, cols = games[0]
    matrix = [[value(a, b) for b in cols] for a in rows]
    pr, _, v = _solve(matrix)
    return Plan(rows, tuple(pr), v, observed_card)
