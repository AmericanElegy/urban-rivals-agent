"""Zero-sum hidden-bid solver using averaged regret matching.

Each public lead card has its own simultaneous payoff matrix. The responder
observes that card, never its pillz/fury. This avoids perfect-information leakage.
"""
from dataclasses import dataclass
from .engine import State, Move, legal_moves, resolve, evaluate


@dataclass(frozen=True)
class Equilibrium:
    row: tuple[float, ...]
    column: tuple[float, ...]
    value: float
    gap: float


def matrix_game(matrix, iterations=2000):
    if iterations < 1 or not matrix or not matrix[0] or any(len(r) != len(matrix[0]) for r in matrix):
        raise ValueError("Require a rectangular nonempty matrix and positive iterations")
    n, m = len(matrix), len(matrix[0])
    regrets = [[0.] * n, [0.] * m]
    totals = [[0.] * n, [0.] * m]
    for _ in range(iterations):
        policies = []
        for r in regrets:
            positive = [max(0., x) for x in r]
            total = sum(positive)
            policies.append([x / total for x in positive] if total else [1 / len(r)] * len(r))
        p, q = policies
        rv = [sum(x * y for x, y in zip(row, q)) for row in matrix]
        cv = [sum(p[i] * matrix[i][j] for i in range(n)) for j in range(m)]
        value = sum(x * y for x, y in zip(p, rv))
        for i in range(n):
            regrets[0][i] += rv[i] - value
            totals[0][i] += p[i]
        for j in range(m):
            regrets[1][j] += value - cv[j]
            totals[1][j] += q[j]
    p, q = [tuple(x / iterations for x in t) for t in totals]
    lower = min(sum(p[i] * matrix[i][j] for i in range(n)) for j in range(m))
    upper = max(sum(x * y for x, y in zip(row, q)) for row in matrix)
    value = sum(p[i] * matrix[i][j] * q[j] for i in range(n) for j in range(m))
    return Equilibrium(p, q, value, upper - lower)


@dataclass(frozen=True)
class Advice:
    moves: tuple[Move, ...]
    probabilities: tuple[float, ...]
    value: float
    gap: float
    lead_card: int


def advise(state: State, side: int = 0, observed_card: int | None = None, iterations: int = 2000,
           allow_fury: bool = True):
    if state.terminal or side not in (0, 1):
        raise ValueError("Require a nonterminal state and side 0 or 1")
    if side != state.leader and observed_card is None:
        raise ValueError("Responder must supply the observed opponent card")
    if side == state.leader and observed_card is not None:
        raise ValueError("Leader cannot observe an opponent lead card")
    leader_moves = legal_moves(state, state.leader, observed_card)
    cards = sorted({m.card for m in leader_moves})
    if not cards:
        raise ValueError("Observed lead card is unavailable")
    candidates = []
    for card in cards:
        rows = legal_moves(state, state.leader, card)
        columns = legal_moves(state, 1 - state.leader)
        if not allow_fury:
            if side == state.leader:
                rows = tuple(m for m in rows if not m.fury)
            else:
                columns = tuple(m for m in columns if not m.fury)
        matrix = []
        for a in rows:
            row = []
            for b in columns:
                moves = (a, b) if state.leader == 0 else (b, a)
                row.append(evaluate(resolve(state, *moves)) * (1 if state.leader == 0 else -1))
            matrix.append(row)
        eq = matrix_game(matrix, iterations)
        candidates.append((eq.value, card, rows, columns, eq))
    _, card, rows, columns, eq = max(candidates, key=lambda x: x[0])
    return Advice(rows if side == state.leader else columns,
                  eq.row if side == state.leader else eq.column,
                  eq.value * (1 if side == state.leader else -1), eq.gap, card)
