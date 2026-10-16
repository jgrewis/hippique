"""Reliability metrics, identical for every source (house methods, PMU, press, bettors)."""
import math

from predict.sources import FAMILY_LABELS, FAMILY_ORDER

MIN_COURSES = 20   # below this, a source's figures are shown as "too few races"


def entry(rankings: list, arrivee: dict, rapport_gagnant, partants: int) -> dict:
    """One evaluated race. rankings: list of SourceRanking."""
    return {
        "partants": partants,
        "rankings": {r.key: r.numeros for r in rankings},
        "probas": {r.key: r.probas for r in rankings if r.probas},
        "labels": {r.key: (r.label, r.family) for r in rankings},
        "arrivee": arrivee,
        "rapport_gagnant": rapport_gagnant,
    }


def _winner(e):
    return next((n for n, pos in e["arrivee"].items() if pos == 1), None)


def _source_metrics(rows: list, key: str) -> dict:
    wins = top3_hits = tierce_set = stakes = returns = 0
    for e in rows:
        picks = e["rankings"][key]
        podium = {n for n, pos in e["arrivee"].items() if pos <= 3}
        wins += e["arrivee"].get(picks[0]) == 1
        top3_hits += len(set(picks[:3]) & podium)
        tierce_set += len(podium) == 3 and set(picks[:3]) == podium
        if e.get("rapport_gagnant") is not None:
            stakes += 1
            if e["arrivee"].get(picks[0]) == 1:
                returns += e["rapport_gagnant"]
    n = len(rows)
    return {
        "courses": n,
        "suffisant": n >= MIN_COURSES,
        "gagnant_pct": round(100 * wins / n, 1),
        "top3_moyen": round(top3_hits / n, 2),
        "tierce_desordre_pct": round(100 * tierce_set / n, 1),
        "roi_simple_gagnant_pct": round(100 * (returns - stakes) / stakes, 1) if stakes else None,
    }


def evaluate(entries: list) -> dict:
    """{'sources': [metrics sorted by family then success], 'log_loss': {...}, 'hasard_gagnant_pct': x}."""
    labels = {}
    for e in entries:
        labels.update(e["labels"])
    sources = []
    for key, (label, family) in labels.items():
        rows = [e for e in entries if e["rankings"].get(key)]
        if rows:
            sources.append({"key": key, "label": label, "famille": family,
                            "famille_label": FAMILY_LABELS[family], **_source_metrics(rows, key)})
    sources.sort(key=lambda s: (FAMILY_ORDER.index(s["famille"]), not s["suffisant"], -s["gagnant_pct"], s["label"]))

    log_loss = {}
    for key in {k for e in entries for k in e["probas"]}:
        losses = [
            -math.log(max(e["probas"][key].get(_winner(e), 1e-9), 1e-9))
            for e in entries if key in e["probas"] and _winner(e) is not None
        ]
        if losses:
            log_loss[labels[key][0]] = round(sum(losses) / len(losses), 4)
    random_win = [1 / e["partants"] for e in entries if e["partants"]]
    return {
        "sources": sources,
        "log_loss": dict(sorted(log_loss.items(), key=lambda kv: kv[1])),
        "hasard_gagnant_pct": round(100 * sum(random_win) / len(random_win), 1) if random_win else None,
    }


def winning_payouts(conn) -> dict:
    """{id_course: rapport simple gagnant per 1 €}."""
    return {
        r["id_course"]: r["rapport"]
        for r in conn.execute(
            "SELECT id_course, MAX(rapport) AS rapport FROM rapports WHERE type_pari='SIMPLE_GAGNANT' GROUP BY id_course"
        )
    }
