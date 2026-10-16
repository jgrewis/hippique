"""Parse the PMU "musique" (recent performance string), e.g. "0p3p2pDa(25)1a".

Each performance is <result><discipline letter>. Results: 1-9 = place,
0 = 10th or worse, D = disqualified, A = stopped, T = fell, R = refused/ran out.
"(25)" marks the start of an earlier year. Most recent race comes first.
"""
import re

PERF = re.compile(r"([0-9DATR])([amphsc])", re.IGNORECASE)
YEAR = re.compile(r"\(\d+\)")

# Points per result: place-based, decreasing; failures score zero.
POINTS = {"1": 1.0, "2": 0.8, "3": 0.65, "4": 0.5, "5": 0.4, "6": 0.3, "7": 0.2, "8": 0.15, "9": 0.1, "0": 0.05}
DECAY = 0.8
WINDOW = 6


def parse(musique: str) -> list:
    """Return results most recent first, e.g. ['0', '3', '2', 'D']."""
    if not musique:
        return []
    return [m.group(1).upper() for m in PERF.finditer(YEAR.sub("", musique))]


def form_index(musique: str):
    """Recency-weighted mean of points over the last races, in [0, 1]; None if no history."""
    results = parse(musique)[:WINDOW]
    if not results:
        return None
    weights = [DECAY ** i for i in range(len(results))]
    total = sum(w * POINTS.get(r, 0.0) for w, r in zip(weights, results))
    return total / sum(weights)


def failure_rate(musique: str):
    """Share of disqualifications/falls among recent races; None if no history."""
    results = parse(musique)[:WINDOW]
    if not results:
        return None
    return sum(r in "DATR" for r in results) / len(results)
