"""Compute and store today's forecasts for races that have not started yet.

    python -m predict.forecast
"""
import logging
import time

import config
from collect.pipeline import today_paris
from db import repository as repo
from predict import boosting, sources
from predict.features import build_races
from predict.logit_model import LogitModel, trainable

log = logging.getLogger("forecast")


def load_model():
    if config.MODEL_PATH.exists():
        return LogitModel.from_json(config.MODEL_PATH.read_text(encoding="utf-8"))
    return None


def _rows(ranking, id_course: str, created: str) -> list:
    return [
        {
            "id_course": id_course, "numero": n, "methode": ranking.key,
            "score": ranking.scores.get(n), "proba": ranking.probas.get(n),
            "rang": rank, "created_at": created,
        }
        for rank, n in enumerate(ranking.numeros, start=1)
    ]


def forecast_day(conn, day: str, model, now_ms: float, boost_model=None) -> int:
    """Store the house forecasts for the races of `day` not started at `now_ms`; return how many."""
    departures = {r["id_course"]: r["depart_ts"] for r in repo.courses_for_day(conn, day)}
    created = repo.now_iso()
    count = 0
    for race in build_races(conn, from_date=day, until=day):
        start = departures.get(race.id_course)
        # Frozen once the race has started: forecasts are never rewritten afterwards.
        if start is None or start <= now_ms or len(race.numeros) < 2:
            continue
        selections = repo.selections_for_course(conn, race.id_course)
        rows = []
        for ranking in sources.all_rankings(race, model, boost_model, selections):
            if ranking.key in sources.HOUSE_LABELS:
                rows += _rows(ranking, race.id_course, created)
        # Runners withdrawn since the previous run must not keep a stale forecast.
        conn.execute("DELETE FROM pronostics WHERE id_course=?", (race.id_course,))
        repo.save_pronostics(conn, rows)
        count += 1
    conn.commit()
    return count


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = repo.connect()
    day = today_paris().isoformat()
    model = load_model()
    history = [r for r in trainable(build_races(conn, until=day)) if r.date_course < day]
    boost_model = boosting.train(history)
    count = forecast_day(conn, day, model, time.time() * 1000, boost_model)
    log.info("Pronostics enregistrés pour %d courses (logit : %s, boosting : %s)",
             count, "oui" if model else "non", f"{boost_model.n_races} courses" if boost_model else "non")


if __name__ == "__main__":
    main()
