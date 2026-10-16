"""Assemble template contexts from the database."""
import json
from itertools import groupby

import config
from db import repository as repo
from predict import backtest, harville, sources
from predict.form_score import LABELS as FORM_LABELS

RAPPORT_ORDER = ("QUINTE_PLUS", "QUARTE_PLUS", "TIERCE", "MULTI", "DEUX_SUR_QUATRE",
                 "COUPLE_GAGNANT", "COUPLE_PLACE", "SIMPLE_GAGNANT", "SIMPLE_PLACE")
PICKS_SHOWN = 8
DISPLAY_FAMILIES = (
    ("maison", "Méthodes maison"),
    ("pmu", "PMU"),
    ("synthese", "Synthèse de la presse"),
    ("presse", "Presse et experts"),
    ("parieurs", "Parieurs"),
    ("combinaisons", "Combinaisons les plus jouées"),
)
DISTANCE_BUCKETS = ((1600, "< 1 600 m"), (2100, "1 600 – 2 099 m"), (2700, "2 100 – 2 699 m"), (10 ** 6, "≥ 2 700 m"))


def distance_bucket(distance):
    if not distance:
        return ""
    return next(label for limit, label in DISTANCE_BUCKETS if distance < limit)


def _paris_list(course: dict) -> list:
    return [p for p in (course["paris"] or "").split(",") if p]


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
        c["paris_list"] = _paris_list(c)
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
    course["paris_list"] = _paris_list(course)
    partants = [dict(p) for p in repo.partants_for_course(conn, course["id_course"])]
    pronos = repo.pronostics_for_course(conn, course["id_course"])
    market = _market_probs(partants)
    selections = repo.selections_for_course(conn, course["id_course"])
    press = [s for s in selections if s["famille"] == "presse"]
    for p in partants:
        p["logit"] = pronos.get("logit", {}).get(p["numero"])
        p["boosting"] = pronos.get("boosting", {}).get(p["numero"])
        p["proba_marche"] = market.get(p["numero"])
        p["valeur"] = (p["logit"]["proba"] / p["proba_marche"]) if p["logit"] and p["proba_marche"] else None
        p["citations"] = sum(str(p["numero"]) in s["numeros"].split("-") for s in press)

    by_num = {p["numero"]: p for p in partants}
    arrival_numbers = _arrival_numbers(course["arrivee"])
    arrival = [by_num.get(n, {"numero": n, "nom_cheval": "?"}) for n in arrival_numbers]

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
        "pronostic_groups": _pronostic_groups(pronos, selections, market, _places(course["arrivee"])),
        "nb_presse": len(press),
    }


def _house_rankings(pronos: dict) -> list:
    """Stored house forecasts as SourceRanking objects, best method first."""
    out = []
    for key, label in sources.HOUSE_LABELS.items():
        if key in pronos:
            rows = sorted(pronos[key].values(), key=lambda r: r["rang"])
            out.append(sources.SourceRanking(
                key, label, "maison", [r["numero"] for r in rows],
                probas={r["numero"]: r["proba"] for r in rows if r["proba"] is not None},
            ))
    return out


def _places(arrivee: str) -> dict:
    """{numero: place} for the first five places (dead heats share a place)."""
    places = {}
    for place, group in enumerate((arrivee or "").split("-")[:5], start=1):
        for n in group.split("="):
            if n.isdigit():
                places[int(n)] = place
    return places


def _pronostic_groups(pronos: dict, selections: list, market: dict, places: dict) -> list:
    """Every source's selection, grouped by family, for display, with each runner's final place (top 5)."""
    rows_by_family = {family: [] for family, _ in DISPLAY_FAMILIES}
    for ranking in _house_rankings(pronos):
        rows_by_family["maison"].append((ranking.label, ranking.numeros))
    favourite = sources.market_ranking(market)
    if favourite:
        rows_by_family["parieurs"].append((favourite.label, favourite.numeros))
    order = {key: i for i, key in enumerate(sources.SYNTHESIS_ORDER)}
    for s in sorted(selections, key=lambda s: order.get(s["source"], len(order))):
        if s["famille"] in rows_by_family:
            rows_by_family[s["famille"]].append((s["libelle"], [int(n) for n in s["numeros"].split("-") if n.isdigit()]))
    groups = []
    for family, title in DISPLAY_FAMILIES:
        rows = [
            {"label": label, "picks": [{"numero": n, "place": places.get(n)} for n in numeros[:PICKS_SHOWN]]}
            for label, numeros in rows_by_family[family] if numeros
        ]
        if rows:
            groups.append({"key": family, "title": title, "rows": rows})
    return groups


def _pronostic_summary(pronos: dict, by_num: dict, course: dict):
    """Headline forecast: the consensus when available, with Harville odds from a probabilistic model."""
    if not pronos:
        return None
    method = next((m for m in ("consensus", "logit", "boosting", "forme") if m in pronos), None)
    if method is None:
        return None
    ordered = sorted(pronos[method].values(), key=lambda r: r["rang"])
    picks = [by_num[r["numero"]] for r in ordered if r["numero"] in by_num]
    summary = {"methode": sources.HOUSE_LABELS[method], "selection": picks[:5], "chances": []}
    model = next((m for m in ("logit", "boosting") if m in pronos), None)
    if model:
        p = {n: r["proba"] for n, r in pronos[model].items()}
        top = [x["numero"] for x in picks]
        summary["chances"].append(("Tiercé dans le désordre", harville.prob_unordered(p, top[:3])))
        summary["chances"].append(("Tiercé dans l'ordre", harville.prob_order(p, top[:3])))
        if course["is_quinte"] and len(top) >= 5:
            summary["chances"].append(("Quinté+ dans le désordre", harville.prob_unordered(p, top[:5])))
        summary["modele_probas"] = sources.HOUSE_LABELS[model]
    return summary


def archives_context(conn) -> dict:
    rows = conn.execute(
        "SELECT date_course, COUNT(*) AS n, MAX(CASE WHEN is_quinte THEN hippodrome END) AS quinte "
        "FROM courses GROUP BY date_course ORDER BY date_course DESC"
    ).fetchall()
    months = [{"month": m, "days": list(items)} for m, items in groupby(rows, key=lambda r: r["date_course"][:7])]
    return {"months": months}


def _live_entries(conn) -> list:
    """Forecasts published before the race (house and third-party), joined with the official arrival."""
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
        runners = [p["numero"] for p in partants if not p["non_partant"]]
        rankings = _house_rankings(repo.pronostics_for_course(conn, cid))
        favourite = sources.market_ranking(_market_probs(partants))
        if favourite:
            rankings.append(favourite)
        rankings += sources.external_rankings(runners, repo.selections_for_course(conn, cid), only_before_start=True)
        entries.append(backtest.entry(rankings, arrivee, payouts.get(cid), len(runners)))
    return entries


def with_groups(metrics: dict) -> dict:
    """Add [(family label, [sources])] in the order computed by the evaluation."""
    groups = [(label, list(rows)) for label, rows in groupby(metrics["sources"], key=lambda m: m["famille_label"])]
    return {**metrics, "groupes": groups}


def _load_backtest():
    if not config.BACKTEST_PATH.exists():
        return None
    report = json.loads(config.BACKTEST_PATH.read_text(encoding="utf-8"))
    # Reports written before every source was compared have another shape.
    if "sources" not in report.get("metriques", {}):
        return None
    return {**report, "metriques": with_groups(report["metriques"])}


def reliability_context(conn) -> dict:
    entries = _live_entries(conn)
    return {
        "backtest": _load_backtest(),
        "live": with_groups(backtest.evaluate(entries)) if entries else None,
        "live_count": len(entries),
        "min_courses": backtest.MIN_COURSES,
        "feature_labels": FORM_LABELS | {"poids": "Poids porté", "elo_cheval": "Elo du cheval", "elo_driver": "Elo du driver / jockey"},
    }
