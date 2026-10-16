"""Method 1: transparent form score out of 100.

Each criterion is turned into a rank within the race (0 = worst, 1 = best),
then combined with fixed weights. A missing criterion counts as average (0.5).
"""
import numpy as np

from predict.features import Race

# Weight per criterion; negative = lower is better.
WEIGHTS = {
    "forme": 0.35,
    "driver": 0.15,
    "tx_place": 0.10,
    "tx_victoire": 0.10,
    "entraineur": 0.10,
    "aptitude": 0.10,
    "gains_par_course": 0.05,
    "echecs": -0.05,
}
LABELS = {
    "forme": "Musique récente",
    "driver": "Driver / jockey (90 j)",
    "tx_place": "Taux de places (carrière)",
    "tx_victoire": "Taux de victoires (carrière)",
    "entraineur": "Entraîneur (90 j)",
    "aptitude": "Aptitude hippodrome / distance",
    "gains_par_course": "Gains par course",
    "echecs": "Disqualifications / chutes récentes",
}


def _rank01(values: list) -> np.ndarray:
    arr = np.array([np.nan if v is None else v for v in values], dtype=float)
    out = np.full(len(arr), 0.5)
    present = ~np.isnan(arr)
    if present.sum() < 2:
        return out
    order = arr[present].argsort().argsort()  # 0..k-1, ties broken by position
    out[present] = order / (present.sum() - 1)
    return out


def scores(race: Race) -> np.ndarray:
    total = np.zeros(len(race.numeros))
    for name, weight in WEIGHTS.items():
        ranks = _rank01(race.raw[name])
        total += weight * ranks if weight > 0 else -weight * (1 - ranks)
    return np.round(100 * total / sum(abs(w) for w in WEIGHTS.values()), 1)
