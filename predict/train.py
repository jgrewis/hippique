"""Weekly training: out-of-sample backtest, then refit on all history.

    python -m predict.train
"""
import json
import logging
import sys
from datetime import date, timedelta

import config
from db import repository as repo
from predict import backtest, logit_model
from predict.features import build_races

log = logging.getLogger("train")
MIN_RACES = 300
TEST_DAYS = 60


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conn = repo.connect()
    races = logit_model.trainable(build_races(conn))
    if len(races) < MIN_RACES:
        log.warning("Seulement %d courses terminées : historique insuffisant, pas de modèle.", len(races))
        return 0

    last_day = date.fromisoformat(races[-1].date_course)
    test_start = (last_day - timedelta(days=TEST_DAYS - 1)).isoformat()
    train_set = [r for r in races if r.date_course < test_start]
    test_set = [r for r in races if r.date_course >= test_start]
    if len(train_set) < MIN_RACES // 2:
        # Short history: keep 80 % for training, 20 % for testing.
        cut = int(len(races) * 0.8)
        train_set, test_set = races[:cut], races[cut:]

    bt_model = logit_model.train(train_set)
    payouts = backtest.winning_payouts(conn)
    entries = []
    for race in test_set:
        ranks, probas = backtest.rankings(race, bt_model)
        entries.append({"rankings": ranks, "probas": probas, "arrivee": race.arrivee, "rapport_gagnant": payouts.get(race.id_course)})

    final_model = logit_model.train(races)
    config.MODEL_PATH.write_text(final_model.to_json(), encoding="utf-8")
    report = {
        "genere_le": repo.now_iso(),
        "entrainement": {"du": train_set[0].date_course, "au": train_set[-1].date_course, "courses": len(train_set)},
        "test": {"du": test_set[0].date_course, "au": test_set[-1].date_course, "courses": len(test_set)},
        "metriques": backtest.evaluate(entries),
        "coefficients": dict(zip(final_model.features, (round(float(b), 3) for b in final_model.beta))),
        "melange": {"fondamental": round(float(final_model.blend[0]), 3), "marche": round(float(final_model.blend[1]), 3)},
    }
    config.BACKTEST_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Modèle entraîné sur %d courses ; backtest : %s", len(races), report["metriques"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
