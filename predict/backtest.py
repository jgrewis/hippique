"""Reliability metrics shared by the historical backtest and the live track record."""
import math

import numpy as np

from predict import form_score
from predict.features import Race

METHOD_LABELS = {
    "logit": "Modèle logit",
    "forme": "Score de forme",
    "favori": "Favori (cote la plus basse)",
}


def rankings(race: Race, model=None) -> tuple:
    """Return ({methode: [numeros best first]}, {methode: {numero: proba}})."""
    ranks, probas = {}, {}
    scores = form_score.scores(race)
    ranks["forme"] = [race.numeros[i] for i in np.argsort(-scores, kind="stable")]
    if not np.isnan(race.market).any():
        ranks["favori"] = [race.numeros[i] for i in np.argsort(-race.market, kind="stable")]
        probas["marche"] = dict(zip(race.numeros, race.market))
    if model is not None:
        p = model.predict(race)
        ranks["logit"] = [race.numeros[i] for i in np.argsort(-p, kind="stable")]
        probas["logit"] = dict(zip(race.numeros, p))
    return ranks, probas


def evaluate(entries: list) -> dict:
    """entries: [{'rankings', 'probas', 'arrivee': {num: pos}, 'rapport_gagnant': float|None}]."""
    out = {}
    methods = sorted({m for e in entries for m in e["rankings"]}, key=list(METHOD_LABELS).index)
    for method in methods:
        rows = [e for e in entries if method in e["rankings"]]
        wins = top3_hits = tierce_set = stakes = returns = 0
        for e in rows:
            picks = e["rankings"][method]
            podium = {n for n, pos in e["arrivee"].items() if pos <= 3}
            wins += e["arrivee"].get(picks[0]) == 1
            top3_hits += len(set(picks[:3]) & podium)
            tierce_set += len(podium) == 3 and set(picks[:3]) == podium
            if e.get("rapport_gagnant") is not None:
                stakes += 1
                if e["arrivee"].get(picks[0]) == 1:
                    returns += e["rapport_gagnant"]
        n = len(rows)
        out[method] = {
            "label": METHOD_LABELS[method],
            "courses": n,
            "gagnant_pct": round(100 * wins / n, 1) if n else None,
            "top3_moyen": round(top3_hits / n, 2) if n else None,
            "tierce_desordre_pct": round(100 * tierce_set / n, 1) if n else None,
            "roi_simple_gagnant_pct": round(100 * (returns - stakes) / stakes, 1) if stakes else None,
        }
    for method in ("logit", "marche"):
        losses = [
            -math.log(max(e["probas"][method].get(_winner(e), 1e-9), 1e-9))
            for e in entries if method in e.get("probas", {}) and _winner(e) is not None
        ]
        if losses:
            out.setdefault("log_loss", {})[method] = round(sum(losses) / len(losses), 4)
    random_win = [1 / len(e["rankings"]["forme"]) for e in entries if "forme" in e["rankings"]]
    if random_win:
        out["hasard_gagnant_pct"] = round(100 * sum(random_win) / len(random_win), 1)
    return out


def _winner(entry):
    return next((n for n, pos in entry["arrivee"].items() if pos == 1), None)


def winning_payouts(conn) -> dict:
    """{id_course: rapport simple gagnant per 1 €}."""
    return {
        r["id_course"]: r["rapport"]
        for r in conn.execute(
            "SELECT id_course, MAX(rapport) AS rapport FROM rapports WHERE type_pari='SIMPLE_GAGNANT' GROUP BY id_course"
        )
    }
