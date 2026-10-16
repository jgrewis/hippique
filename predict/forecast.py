"""Compute and store today's forecasts for races that have not started yet.

    python -m predict.forecast
"""
import logging
import time

import numpy as np

import config
from collect.pipeline import today_paris
from db import repository as repo
from predict import form_score
from predict.features import build_races
from predict.logit_model import LogitModel

log = logging.getLogger("forecast")


def load_model():
    if config.MODEL_PATH.exists():
        return LogitModel.from_json(config.MODEL_PATH.read_text(encoding="utf-8"))
    return None


def _ranks(values: np.ndarray) -> list:
    return list(np.argsort(np.argsort(-values, kind="stable")) + 1)


def forecast_day(conn, day: str, model, now_ms: float) -> int:
    """Store forecasts for the races of `day` not started at `now_ms`; return how many."""
    departures = {r["id_course"]: r["depart_ts"] for r in repo.courses_for_day(conn, day)}
    created = repo.now_iso()
    count = 0
    for race in build_races(conn, from_date=day, until=day):
        start = departures.get(race.id_course)
        # Frozen once the race has started: forecasts are never rewritten afterwards.
        if start is None or start <= now_ms or len(race.numeros) < 2:
            continue
        scores = form_score.scores(race)
        rows = [
            {"id_course": race.id_course, "numero": n, "methode": "forme", "score": float(s), "proba": None, "rang": int(k), "created_at": created}
            for n, s, k in zip(race.numeros, scores, _ranks(scores))
        ]
        if model is not None:
            probas = model.predict(race)
            rows += [
                {"id_course": race.id_course, "numero": n, "methode": "logit", "score": None, "proba": float(p), "rang": int(k), "created_at": created}
                for n, p, k in zip(race.numeros, probas, _ranks(probas))
            ]
        # Runners withdrawn since the previous run must not keep a stale forecast.
        conn.execute("DELETE FROM pronostics WHERE id_course=?", (race.id_course,))
        repo.save_pronostics(conn, rows)
        count += 1
    conn.commit()
    return count


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = repo.connect()
    model = load_model()
    count = forecast_day(conn, today_paris().isoformat(), model, time.time() * 1000)
    log.info("Pronostics enregistrés pour %d courses (modèle logit : %s)", count, "oui" if model else "non")


if __name__ == "__main__":
    main()
