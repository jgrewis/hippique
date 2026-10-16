"""Method 5: consensus of every available source (Borda count by family).

Each ranking gives TOP, TOP-1, ..., 1 points to its first TOP runners. Points
are averaged within a family (house methods, PMU, press, bettors), then the
families are summed with equal weight: fifteen newspapers must not drown the
other sources.
"""
TOP = 8
FAMILIES = ("maison", "pmu", "presse", "parieurs")


def scores(runners: list, rankings_by_family: dict) -> dict:
    """{numero: points}. rankings_by_family: {famille: [[numeros best first], ...]}."""
    total = dict.fromkeys(runners, 0.0)
    for family in FAMILIES:
        rankings = [r for r in rankings_by_family.get(family, []) if r]
        if not rankings:
            continue
        for ranking in rankings:
            for rank, numero in enumerate(ranking[:TOP]):
                if numero in total:
                    total[numero] += (TOP - rank) / len(rankings)
    return total


def ranking(runners: list, rankings_by_family: dict) -> list:
    """Runners best first; ties keep the order of their numbers."""
    points = scores(runners, rankings_by_family)
    return sorted(runners, key=lambda n: (-points[n], n))
