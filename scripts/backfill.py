"""One-off history collection, resumable and time-boxed.

Days already complete are skipped, so the script can be relaunched until done.
Most recent days are collected first: they are the most useful.

    python -m scripts.backfill --days 365 --budget-minutes 330
"""
import argparse
import logging
import os
import time
from datetime import timedelta

from collect.http_client import HttpClient
from collect.pipeline import collect_day, today_paris
from db import repository as repo

log = logging.getLogger("backfill")


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=365, help="profondeur d'historique en jours")
    parser.add_argument("--budget-minutes", type=float, default=330, help="arrêt propre après ce délai")
    args = parser.parse_args(argv)

    deadline = time.monotonic() + args.budget_minutes * 60
    conn = repo.connect()
    http = HttpClient()
    today = today_paris()
    run_at = repo.now_iso()
    pending = [
        today - timedelta(days=n)
        for n in range(1, args.days + 1)
        if not repo.day_is_complete(conn, (today - timedelta(days=n)).isoformat())
    ]
    log.info("%d jours à collecter", len(pending))
    done = 0
    for day in pending:
        if time.monotonic() > deadline:
            break
        stats = collect_day(conn, http, day, run_at, today)
        done += 1
        log.info("%s: %s (%d/%d)", day, stats, done, len(pending))

    remaining = sum(
        1 for n in range(1, args.days + 1)
        if not repo.day_is_complete(conn, (today - timedelta(days=n)).isoformat())
    )
    conn.close()
    log.info("Jours restants : %d", remaining)
    # Lets the GitHub workflow decide whether to chain another run. Without
    # progress (source down, permanent errors) chaining would loop forever.
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"remaining={remaining}\nprogressed={str(remaining < len(pending)).lower()}\n")


if __name__ == "__main__":
    main()
