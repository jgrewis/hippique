import math

import numpy as np
import pytest

from predict import backtest, form_score, harville, musique
from predict.features import FEATURES, Race, build_races
from predict.logit_model import LogitModel, train


def test_musique_parsing():
    assert musique.parse("0p3p2pDa(25)1a") == ["0", "3", "2", "D", "1"]
    assert musique.form_index("1a1a1a") == pytest.approx(1.0)
    assert musique.form_index("") is None
    assert musique.failure_rate("DaDa") == 1.0
    # Recent results weigh more than older ones.
    assert musique.form_index("1a0a") > musique.form_index("0a1a")


def test_harville_sums_to_one():
    p = {1: 0.5, 2: 0.3, 3: 0.2}
    total = sum(harville.prob_order(p, list(o)) for o in [(1, 2, 3), (1, 3, 2), (2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1)])
    assert total == pytest.approx(1.0)
    assert harville.prob_unordered(p, [1, 2, 3]) == pytest.approx(1.0)
    assert harville.prob_order(p, [1, 2]) == pytest.approx(0.5 * 0.3 / 0.5)
    assert harville.best_order(p, 2) == [1, 2]


def _synthetic_races(n_races=400, seed=0):
    """The horse with the best 'forme' wins more often: the model must learn a positive weight."""
    rng = np.random.default_rng(seed)
    races = []
    for i in range(n_races):
        k = 8
        forme = rng.random(k)
        utility = 3 * forme + rng.gumbel(size=k)
        winner = int(np.argmax(utility))
        raw = {name: [None] * k for name in FEATURES}
        raw["forme"] = list(forme)
        market = np.full(k, 1 / k)
        races.append(Race(f"r{i}", "2026-01-01", list(range(1, k + 1)), raw, market, {winner + 1: 1}))
    return races


def test_logit_learns_signal_and_roundtrips():
    model = train(_synthetic_races())
    assert model.beta[FEATURES.index("forme")] > 0.5
    restored = LogitModel.from_json(model.to_json())
    race = _synthetic_races(1, seed=99)[0]
    p = restored.predict(race)
    assert p.sum() == pytest.approx(1.0)
    assert np.allclose(p, model.predict(race), atol=1e-5)


def test_form_score_range_and_order():
    race = _synthetic_races(1)[0]
    scores = form_score.scores(race)
    assert scores.min() >= 0 and scores.max() <= 100
    best = int(np.argmax(race.raw["forme"]))
    assert scores[best] == scores.max()


def test_evaluate_metrics():
    entries = [
        {"rankings": {"forme": [1, 2, 3, 4]}, "probas": {}, "arrivee": {1: 1, 2: 2, 3: 3}, "rapport_gagnant": 3.0},
        {"rankings": {"forme": [4, 3, 2, 1]}, "probas": {}, "arrivee": {1: 1, 2: 2, 3: 3}, "rapport_gagnant": 2.0},
    ]
    m = backtest.evaluate(entries)["forme"]
    assert m["gagnant_pct"] == 50.0
    assert m["tierce_desordre_pct"] == 50.0
    assert m["top3_moyen"] == 2.5
    assert m["roi_simple_gagnant_pct"] == 50.0  # stake 2 €, return 3 €


def test_features_on_real_fixture(filled_conn):
    races = build_races(filled_conn)
    race = next(r for r in races if r.id_course == "2026-09-15-R1C1")
    assert len(race.numeros) == 16
    assert race.winner_index == race.numeros.index(7)
    assert math.isclose(race.market.sum(), 1.0)
    assert race.standardized().shape == (16, len(FEATURES))
