"""Per-runner features, computed in one chronological pass over the database.

Every feature for a race on day D only uses data known before D: the PMU
snapshot of the runner (career stats, musique, morning odds, all published
before the race) and our own history of strictly earlier days. This is what
makes the backtest honest (no look-ahead leakage).
"""
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date

import numpy as np

from predict import musique
from predict.elo import EloBook

FEATURES = ("forme", "echecs", "tx_victoire", "tx_place", "gains_par_course", "driver", "entraineur", "aptitude", "poids",
            "elo_cheval", "elo_driver")
ROLLING_DAYS = 90


@dataclass
class Race:
    id_course: str
    date_course: str
    numeros: list
    raw: dict                      # feature name -> list of float|None (one per runner)
    market: np.ndarray             # market win probabilities from morning odds (sum to 1), NaN if unknown
    arrivee: dict = field(default_factory=dict)  # numero -> final position

    @property
    def winner_index(self):
        winners = [i for i, n in enumerate(self.numeros) if self.arrivee.get(n) == 1]
        return winners[0] if winners else None

    def standardized(self, names=FEATURES, keep_missing=False) -> np.ndarray:
        """Matrix (runners x features), z-scored within the race.

        Missing values become 0 (the race mean), or stay NaN with keep_missing
        for models that handle them natively.
        """
        missing = np.nan if keep_missing else 0.0
        cols = []
        for name in names:
            values = np.array([np.nan if v is None else v for v in self.raw[name]], dtype=float)
            present = values[~np.isnan(values)]
            if len(present) < 2 or present.std() == 0:
                cols.append(np.where(np.isnan(values), missing, 0.0))
                continue
            z = (values - present.mean()) / present.std()
            cols.append(np.where(np.isnan(z), missing, z))
        return np.column_stack(cols)


class _RollingRate:
    """Wins/places over the last ROLLING_DAYS days for a driver or trainer."""

    def __init__(self):
        self.events = defaultdict(deque)  # key -> deque[(day_ordinal, won)]

    def rate(self, key, today: int, prior=0.1, strength=10):
        q = self.events.get(key)
        if q is None:
            return None
        while q and q[0][0] < today - ROLLING_DAYS:
            q.popleft()
        wins = sum(won for _, won in q)
        return (wins + prior * strength) / (len(q) + strength)

    def add(self, key, day: int, won: bool):
        if key:
            self.events[key].append((day, int(won)))


def _smoothed(successes, total, prior, strength=10):
    if total is None or successes is None:
        return None
    return (successes + prior * strength) / (total + strength)


def _market_probs(rows) -> np.ndarray:
    odds = [r["cote_matin"] or r["cote_actuelle"] for r in rows]
    if any(o is None or o <= 1 for o in odds):
        return np.full(len(rows), np.nan)
    implied = np.array([1 / o for o in odds])
    return implied / implied.sum()


def _same_conditions(past, hippodrome, distance):
    return past[0] == hippodrome or (distance and past[1] and abs(past[1] - distance) <= 0.1 * distance)


def load_rows(conn, until: str = None):
    sql = (
        "SELECT p.*, c.date_course, c.hippodrome, c.distance_m, c.discipline "
        "FROM partants p JOIN courses c USING (id_course) WHERE p.non_partant = 0"
    )
    params = []
    if until:
        sql += " AND c.date_course <= ?"
        params.append(until)
    sql += " ORDER BY c.date_course, p.id_course, p.numero"
    return conn.execute(sql, params).fetchall()


def build_races(conn, from_date: str = None, until: str = None) -> list:
    """Return Race objects for races dated >= from_date (state is warmed up on earlier days)."""
    by_day = defaultdict(lambda: defaultdict(list))
    for row in load_rows(conn, until):
        by_day[row["date_course"]][row["id_course"]].append(row)

    drivers, trainers = _RollingRate(), _RollingRate()
    horse_history = defaultdict(list)  # horse -> [(hippodrome, distance, placed)]
    horse_elo, driver_elo = EloBook(), EloBook()
    races = []

    for day in sorted(by_day):
        ordinal = date.fromisoformat(day).toordinal()
        day_races = by_day[day]
        if from_date is None or day >= from_date:
            for id_course, rows in day_races.items():
                races.append(_race_from_rows(id_course, day, rows, ordinal, drivers, trainers, horse_history, horse_elo, driver_elo))
        # Update the state only after the whole day has been featurized.
        for rows in day_races.values():
            if not any(r["arrivee"] for r in rows):
                continue
            horse_elo.update([(_horse_key(r), r["arrivee"]) for r in rows])
            driver_elo.update([(r["driver_jockey"], r["arrivee"]) for r in rows])
            for r in rows:
                won = r["arrivee"] == 1
                drivers.add(r["driver_jockey"], ordinal, won)
                trainers.add(r["entraineur"], ordinal, won)
                horse_history[_horse_key(r)].append(
                    (r["hippodrome"], r["distance_m"], int(bool(r["arrivee"]) and r["arrivee"] <= 3))
                )
    return races


def _horse_key(row):
    return row["id_cheval"] or row["nom_cheval"]


def _race_from_rows(id_course, day, rows, ordinal, drivers, trainers, horse_history, horse_elo, driver_elo) -> Race:
    raw = {name: [] for name in FEATURES}
    for r in rows:
        n = r["nb_courses"]
        raw["forme"].append(musique.form_index(r["musique"]))
        raw["echecs"].append(musique.failure_rate(r["musique"]))
        raw["tx_victoire"].append(_smoothed(r["nb_victoires"], n, prior=0.1))
        raw["tx_place"].append(_smoothed(r["nb_places"], n, prior=0.3))
        gains = r["gains_carriere"]
        raw["gains_par_course"].append(math.log1p(gains / n) if gains is not None and n else None)
        raw["driver"].append(drivers.rate(r["driver_jockey"], ordinal))
        raw["entraineur"].append(trainers.rate(r["entraineur"], ordinal))
        past = [h for h in horse_history.get(_horse_key(r), []) if _same_conditions(h, r["hippodrome"], r["distance_m"])]
        raw["aptitude"].append(_smoothed(sum(h[2] for h in past), len(past), prior=0.3, strength=3) if past else None)
        raw["poids"].append(r["poids_kg"])
        raw["elo_cheval"].append(horse_elo.get(_horse_key(r)))
        raw["elo_driver"].append(driver_elo.get(r["driver_jockey"]))
    return Race(
        id_course=id_course,
        date_course=day,
        numeros=[r["numero"] for r in rows],
        raw=raw,
        market=_market_probs(rows),
        arrivee={r["numero"]: r["arrivee"] for r in rows if r["arrivee"]},
    )
