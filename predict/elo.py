"""Multi-competitor Elo ratings for horses and drivers.

After each race, every runner is compared with every other one: finishing
ahead counts as a win. Unclassified runners (disqualified, fell...) are
ranked last, without comparing them with each other. K is divided by
(n - 1) so that a race weighs the same whatever the field size.
"""
import math

INITIAL = 1500.0
K = 24.0
SCALE = 400.0


class EloBook:
    def __init__(self):
        self.ratings = {}

    def get(self, key):
        """Rating, or None if never seen (treated as missing, not as average)."""
        return self.ratings.get(key)

    def update(self, finish: list):
        """finish: [(key, position or None)] for one race."""
        runners = [(k, p) for k, p in finish if k]
        n = len(runners)
        if n < 2:
            return
        before = {k: self.ratings.get(k, INITIAL) for k, _ in runners}
        k_eff = K / (n - 1)
        delta = dict.fromkeys(before, 0.0)
        for i, (a, pa) in enumerate(runners):
            for b, pb in runners[i + 1:]:
                if pa is None and pb is None:
                    continue
                if pb is None or (pa is not None and pa < pb):
                    score_a = 1.0
                elif pa == pb:
                    score_a = 0.5
                else:
                    score_a = 0.0
                expected_a = 1 / (1 + 10 ** ((before[b] - before[a]) / SCALE))
                delta[a] += k_eff * (score_a - expected_a)
                delta[b] -= k_eff * (score_a - expected_a)
        for key, d in delta.items():
            self.ratings[key] = before[key] + d


def combined_score(horse_rating, driver_rating) -> float:
    """Deviation from the initial rating; the driver counts half."""
    horse = (horse_rating or INITIAL) - INITIAL
    driver = (driver_rating or INITIAL) - INITIAL
    return horse + 0.5 * driver


def win_probabilities(scores: list) -> list:
    """Elo-consistent softmax: a 400-point gap means 10:1 odds."""
    factor = math.log(10) / SCALE
    m = max(scores)
    weights = [math.exp((s - m) * factor) for s in scores]
    total = sum(weights)
    return [w / total for w in weights]
