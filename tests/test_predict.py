import math

import numpy as np
import pytest

from predict import backtest, boosting, consensus, elo, form_score, harville, musique, sources
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


def _ranking(key, numeros, family="maison"):
    return sources.SourceRanking(key, key, family, numeros)


def test_evaluate_metrics():
    arrival = {1: 1, 2: 2, 3: 3}
    entries = [
        backtest.entry([_ranking("forme", [1, 2, 3, 4]), _ranking("pmu", [3, 1, 2], "pmu")], arrival, 3.0, 4),
        backtest.entry([_ranking("forme", [4, 3, 2, 1])], arrival, 2.0, 4),
    ]
    result = backtest.evaluate(entries)
    forme = next(s for s in result["sources"] if s["key"] == "forme")
    assert forme["gagnant_pct"] == 50.0
    assert forme["tierce_desordre_pct"] == 50.0
    assert forme["top3_moyen"] == 2.5
    assert forme["roi_simple_gagnant_pct"] == 50.0  # stake 2 €, return 3 €
    pmu = next(s for s in result["sources"] if s["key"] == "pmu")
    assert pmu["courses"] == 1 and not pmu["suffisant"]
    assert result["hasard_gagnant_pct"] == 25.0


def test_elo_rewards_winner_and_ignores_unseen():
    book = elo.EloBook()
    assert book.get("A") is None
    book.update([("A", 1), ("B", 2), ("C", None)])
    assert book.get("A") > elo.INITIAL > book.get("C")
    assert sum(book.ratings.values()) == pytest.approx(3 * elo.INITIAL)


def test_consensus_weights_families_equally():
    runners = [1, 2, 3]
    # Ten press sources for 3 must not outweigh one family each for 1.
    rankings = {"maison": [[1, 2, 3]], "pmu": [[1, 3, 2]], "parieurs": [[1, 2, 3]], "presse": [[3, 2, 1]] * 10}
    assert consensus.ranking(runners, rankings)[0] == 1


def test_external_rankings_filter_and_combine():
    rows = [
        {"source": "pmu", "famille": "pmu", "libelle": "PMU", "numeros": "7-99-8-7", "avant_depart": 0},
        {"source": "synthese:OUTSIDERS", "famille": "synthese", "libelle": "o", "numeros": "3", "avant_depart": 1},
        {"source": "synthese:FAVORIS", "famille": "synthese", "libelle": "f", "numeros": "8-7", "avant_depart": 1},
        {"source": "joues:TIERCE:1", "famille": "combinaisons", "libelle": "t", "numeros": "1-2-3", "avant_depart": 1},
    ]
    out = {r.key: r.numeros for r in sources.external_rankings([3, 7, 8], rows)}
    assert out == {"pmu": [7, 8], "synthese": [8, 7, 3]}  # unknown and repeated runners dropped, combos ignored
    only_before = {r.key for r in sources.external_rankings([3, 7, 8], rows, only_before_start=True)}
    assert only_before == {"synthese"}


def test_boosting_learns_and_normalises():
    model = boosting.train(_synthetic_races())
    race = _synthetic_races(1, seed=7)[0]
    p = model.predict(race)
    assert p.sum() == pytest.approx(1.0)
    assert int(np.argmax(p)) == int(np.argmax(race.raw["forme"])) or p[int(np.argmax(race.raw["forme"]))] > 1 / len(p)


def test_features_on_real_fixture(filled_conn):
    races = build_races(filled_conn)
    race = next(r for r in races if r.id_course == "2026-09-15-R1C1")
    assert len(race.numeros) == 16
    assert race.winner_index == race.numeros.index(7)
    assert math.isclose(race.market.sum(), 1.0)
    assert race.standardized().shape == (16, len(FEATURES))
