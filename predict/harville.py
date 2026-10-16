"""Harville formulas: from win probabilities to finishing-order probabilities."""
from itertools import permutations


def prob_order(p: dict, order: list) -> float:
    """P(horses finish exactly in `order` for the first len(order) places)."""
    prob, remaining = 1.0, 1.0
    for n in order:
        if remaining <= 0:
            return 0.0
        prob *= p[n] / remaining
        remaining -= p[n]
    return prob


def prob_unordered(p: dict, horses: list) -> float:
    """P(the given horses take the first len(horses) places, in any order)."""
    return sum(prob_order(p, list(perm)) for perm in permutations(horses))

