"""Assemble template contexts from the database."""
import json
from itertools import groupby

import config
from db import repository as repo
from predict import backtest, harville
from predict.form_score import LABELS as FORM_LABELS

RAPPORT_ORDER = ("QUINTE_PLUS", "QUARTE_PLUS", "TIERCE", "MULTI", "DEUX_SUR_QUATRE",
                 "COUPLE_GAGNANT", "COUPLE_PLACE", "SIMPLE_GAGNANT", "SIMPLE_PLACE")
DISTANCE_BUCKETS = ((1600, "< 1 600 m"), (2100, "1 600 – 2 099 m"), (2700, "2 100 – 2 699 m"), (10 ** 6, "≥ 2 700 m"))


def distance_bucket(distance):
    if not distance:
        return ""
    return next(label for limit, label in DISTANCE_BUCKETS if distance < limit)


def _market_probs(partants: list) -> dict:
    odds = {p["numero"]: p["cote_matin"] or p["cote_actuelle"] for p in partants if not p["non_partant"]}
    if not odds or any(o is None or o <= 1 for o in odds.values()):
        return {}
    total = sum(1 / o for o in odds.values())
    return {n: (1 / o) / total for n, o in odds.items()}


def _arrival_numbers(arrivee: str) -> list:
    return [int(n) for n in arrivee.replace("=", "-").split("-")] if arrivee else []


def day_context(conn, day: str, dates: list) -> dict:
    courses = [dict(c) for c in repo.courses_for_day(conn, day)]
    for c in courses:
        c["distance_bucket"] = distance_bucket(c["distance_m"])
        c["paris_list"] = [p for p in (c["paris"] or "").split(",") if p]
    reunions = [
        {"num": num, "hippodrome": group[0]["hippodrome"], "courses": group}
        for num, items in groupby(courses, key=lambda c: c["num_reunion"])
        for group in [list(items)]
    ]
    quinte = next((c for c in courses if c["is_quinte"]), None)
    idx = dates.index(day)
    return {
        "day": day,
        "reunions": reunions,
        "nb_courses": len(courses),
        "quinte": quinte,
        "quinte_detail": course_context(conn, quinte) if quinte else None,
        "prev_day": dates[idx - 1] if idx > 0 else None,
        "next_day": dates[idx + 1] if idx + 1 < len(dates) else None,
        "first_day": dates[0],
        "last_day": dates[-1],
        "hippodromes": sorted({c["hippodrome"] for c in courses}),
        "disciplines": sorted({c["discipline"] for c in courses if c["discipline"]}),
        "distance_buckets": [label for _, label in DISTANCE_BUCKETS if any(c["distance_bucket"] == label for c in courses)],
    }


def course_context(conn, course) -> dict:
    course = dict(course)
    partants = [dict(p) for p in repo.partants_for_course(conn, course["id_course"])]
    pronos = repo.pronostics_for_course(conn, course["id_course"])
    market = _market_probs(partants)
    for p in partants:
        p["forme"] = pronos.get("forme", {}).get(p["numero"])
        p["logit"] = pronos.get("logit", {}).get(p["numero"])
        p["proba_marche"] = market.get(p["numero"])
        p["valeur"] = (p["logit"]["proba"] / p["proba_marche"]) if p["logit"] and p["proba_marche"] else None

    by_num = {p["numero"]: p for p in partants}
    arrival = [by_num.get(n, {"numero": n, "nom_cheval": "?"}) for n in _arrival_numbers(course["arrivee"])]

    rapports = sorted(
        (dict(r) for r in repo.rapports_for_course(conn, course["id_course"])),
        key=lambda r: RAPPORT_ORDER.index(r["type_pari"]) if r["type_pari"] in RAPPORT_ORDER else 99,
    )
    rapport_groups = [{"type": t, "rows": list(rows)} for t, rows in groupby(rapports, key=lambda r: r["type_pari"])]
    return {
        "course": course,
        "partants": partants,
        "arrival": arrival,
        "rapport_groups": rapport_groups,
        "pronostic": _pronostic_summary(pronos, by_num, course),
    }


def _pronostic_summary(pronos: dict, by_num: dict, course: dict):
    if not pronos:
        return None
    method = "logit" if "logit" in pronos else "forme"
    ordered = sorted(pronos[method].values(), key=lambda r: r["rang"])
    picks = [by_num[r["numero"]] for r in ordered if r["numero"] in by_num]
    summary = {"methode": method, "selection": picks[:5], "chances": []}
    if method == "logit":
        p = {n: r["proba"] for n, r in pronos["logit"].items()}
        top = [x["numero"] for x in picks]
        summary["chances"].append(("Tiercé dans le désordre", harville.prob_unordered(p, top[:3])))
        summary["chances"].append(("Tiercé dans l'ordre", harville.prob_order(p, top[:3])))
        if course["is_quinte"] and len(top) >= 5:
            summary["chances"].append(("Quinté+ dans le désordre", harville.prob_unordered(p, top[:5])))
    return summary


def archives_context(conn) -> dict:
    rows = conn.execute(
        "SELECT date_course, COUNT(*) AS n, MAX(CASE WHEN is_quinte THEN hippodrome END) AS quinte "
        "FROM courses GROUP BY date_course ORDER BY date_course DESC"
    ).fetchall()
    months = [{"month": m, "days": list(items)} for m, items in groupby(rows, key=lambda r: r["date_course"][:7])]
    return {"months": months}


def _live_entries(conn) -> list:
    """Forecasts made before the race, joined with the official arrival."""
    payouts = backtest.winning_payouts(conn)
    ids = [r[0] for r in conn.execute(
        "SELECT DISTINCT p.id_course FROM pronostics p JOIN courses c USING (id_course) WHERE c.arrivee IS NOT NULL"
    )]
    entries = []
    for cid in ids:
        partants = [dict(p) for p in repo.partants_for_course(conn, cid)]
        arrivee = {p["numero"]: p["arrivee"] for p in partants if p["arrivee"]}
        if not arrivee:
            continue
        pronos = repo.pronostics_for_course(conn, cid)
        ranks = {m: [r["numero"] for r in sorted(rows.values(), key=lambda r: r["rang"])] for m, rows in pronos.items()}
        probas = {"logit": {n: r["proba"] for n, r in pronos["logit"].items()}} if "logit" in pronos else {}
        market = _market_probs(partants)
        if market:
            ranks["favori"] = sorted(market, key=market.get, reverse=True)
            probas["marche"] = market
        entries.append({"rankings": ranks, "probas": probas, "arrivee": arrivee, "rapport_gagnant": payouts.get(cid)})
    return entries


def reliability_context(conn) -> dict:
    report = json.loads(config.BACKTEST_PATH.read_text(encoding="utf-8")) if config.BACKTEST_PATH.exists() else None
    entries = _live_entries(conn)
    return {
        "backtest": report,
        "live": backtest.evaluate(entries) if entries else None,
        "live_count": len(entries),
        "feature_labels": FORM_LABELS | {"poids": "Poids porté"},
    }
