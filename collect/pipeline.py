"""Collection orchestration: PMU API -> SQLite, with HTML fallback for arrivals.

Usage:
    python -m collect.pipeline                 # yesterday (if incomplete) + today
    python -m collect.pipeline --date 2026-10-15
"""
import argparse
import logging
import sys
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import config
from collect import api_pmu, external_forecasts, scraper
from collect.http_client import HttpClient, PmuJsonClient, SourceUnavailable
from collect.normalize import normalize_course, normalize_partant, normalize_rapports
from db import repository as repo

log = logging.getLogger("collect")
# The API stops serving press and PMU forecasts after about 40 days.
FORECAST_HISTORY_DAYS = 40
# Collection runs every 20 minutes during racing hours. A race that has not
# started is only refreshed when it is close to the start (last odds before the
# forecasts freeze) or when its data is getting old: this keeps the load low.
NEAR_START_MIN = 60
REFRESH_HOURS = 3


def today_paris() -> date:
    return datetime.now(ZoneInfo(config.TIMEZONE)).date()


def _french_reunions(programme: dict):
    for reunion in programme.get("reunions", []):
        if (reunion.get("pays") or {}).get("code") in config.COUNTRIES:
            yield reunion


def _fallback_arrivals(conn, http: HttpClient, day: date, run_at: str):
    try:
        arrivals = scraper.fetch_arrivals(http, day)
    except Exception as exc:  # the fallback must never crash the run
        repo.log(conn, "ERROR", f"Repli HTML en échec : {exc}", day.isoformat(), run_at)
        return
    for num_reunion, num_course, arrivee in arrivals:
        repo.set_arrival(conn, f"{day.isoformat()}-R{num_reunion}C{num_course}", arrivee)
    repo.log(conn, "WARNING", f"Repli HTML utilisé : {len(arrivals)} arrivées récupérées", day.isoformat(), run_at)
    conn.commit()


def _collect_externals(conn, pmu: PmuJsonClient, day: date, row: dict, today: date, now: str, run_at: str):
    """Store third-party rankings. Failures are logged and never block the race itself."""
    cid, r, c = row["id_course"], row["num_reunion"], row["num_course"]
    before_start = row["depart_ts"] is None or time.time() * 1000 < row["depart_ts"]
    try:
        rows = external_forecasts.most_played_rows(cid, api_pmu.fetch_most_played(pmu, day, r, c), now)
        if (today - day).days <= FORECAST_HISTORY_DAYS:
            rows += external_forecasts.pmu_rows(cid, api_pmu.fetch_pmu_forecast(pmu, day, r, c), before_start, now)
            rows += external_forecasts.press_rows(cid, api_pmu.fetch_press_forecasts(pmu, day, r, c), before_start, now)
    except (SourceUnavailable, KeyError, TypeError, ValueError) as exc:
        repo.log(conn, "WARNING", f"{cid} : pronostics externes indisponibles ({exc})", day.isoformat(), run_at)
        return
    for selection in rows:
        repo.upsert_selection(conn, selection)
    if repo.course_state(conn, cid) != "new":
        repo.set_externes_ok(conn, cid)


def _needs_refresh(conn, row: dict, now_ms: float) -> bool:
    start = row["depart_ts"]
    if start is None or start <= now_ms + NEAR_START_MIN * 60_000:
        return True  # started (results pending), about to start, or unknown time
    last = repo.course_updated_at(conn, row["id_course"])
    if last is None:
        return True
    age_h = (now_ms / 1000 - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()) / 3600
    return age_h >= REFRESH_HOURS


def collect_day(conn, http: HttpClient, day: date, run_at: str, today: date) -> dict:
    """Collect one day. Returns {'courses': n, 'errors': n, 'source_down': bool}."""
    pmu = PmuJsonClient(http)
    iso = day.isoformat()
    stats = {"courses": 0, "errors": 0, "source_down": False}
    try:
        programme = api_pmu.fetch_programme(pmu, day)
    except SourceUnavailable as exc:
        repo.log(conn, "ERROR", f"API PMU indisponible (programme) : {exc}", iso, run_at)
        stats.update(errors=1, source_down=True)
        if (today - day).days <= 1:  # the HTML source only lists recent days
            _fallback_arrivals(conn, http, day, run_at)
        conn.commit()
        return stats
    if not programme:
        repo.log(conn, "WARNING", "Aucun programme publié pour cette date", iso, run_at)
        repo.mark_day(conn, iso, complete=day < today)
        conn.commit()
        return stats

    now = repo.now_iso()
    for reunion in _french_reunions(programme):
        for raw_course in reunion.get("courses", []):
            row = normalize_course(day, reunion, raw_course, now)
            cid = row["id_course"]
            state = repo.course_state(conn, cid)
            if state == "final" or (state == "new" and not _needs_refresh(conn, row, time.time() * 1000)):
                continue
            stats["courses"] += 1
            try:
                if state == "new":
                    repo.upsert_course(conn, row)
                    participants = api_pmu.fetch_participants(pmu, day, row["num_reunion"], row["num_course"])
                    for raw in participants or []:
                        repo.upsert_partant(conn, normalize_partant(cid, raw))
                    if row["arrivee"]:
                        rapports = api_pmu.fetch_rapports(pmu, day, row["num_reunion"], row["num_course"])
                        if rapports:
                            repo.replace_rapports(conn, cid, normalize_rapports(cid, rapports))
                _collect_externals(conn, pmu, day, row, today, now, run_at)
            except SourceUnavailable as exc:
                stats["errors"] += 1
                repo.log(conn, "ERROR", f"{cid} : {exc}", iso, run_at)
            conn.commit()

    complete = day < today and stats["errors"] == 0
    repo.mark_day(conn, iso, complete)
    level = "ERROR" if stats["errors"] else "INFO"
    repo.log(conn, level, f"{stats['courses']} courses mises à jour, {stats['errors']} erreurs", iso, run_at)
    conn.commit()
    return stats


def run(dates: list) -> int:
    """Collect the given dates; return a process exit code (1 if the source is down)."""
    conn = repo.connect()
    http = HttpClient()
    today = today_paris()
    run_at = repo.now_iso()
    source_down = False
    for day in dates:
        stats = collect_day(conn, http, day, run_at, today)
        log.info("%s: %s (%d requêtes cumulées)", day, stats, http.request_count)
        source_down |= stats["source_down"]
    conn.close()
    return 1 if source_down else 0


def default_dates(conn=None) -> list:
    today = today_paris()
    yesterday = today - timedelta(days=1)
    conn = conn or repo.connect()
    dates = [] if repo.day_is_complete(conn, yesterday.isoformat()) else [yesterday]
    return dates + [today]


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", type=date.fromisoformat, help="collecter uniquement cette date (AAAA-MM-JJ)")
    args = parser.parse_args(argv)
    dates = [args.date] if args.date else default_dates()
    sys.exit(run(dates))


if __name__ == "__main__":
    main()
