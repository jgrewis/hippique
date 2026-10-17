"""Tell the collection relay whether payouts are still missing for races that just finished.

The PMU publishes the official finish a few minutes before the payouts. When a
collection sees an arrival without its payouts, the relay starts the next
collection sooner than the 20-minute slot (see scripts/relay.sh).

Usage:
    python -m collect.pending      # prints the count, and writes pending_rapports=<n> to $GITHUB_OUTPUT
"""
import os
import time

from db import repository as repo

# Older races are left to the normal schedule: their payouts may never come
# (all bets refunded, race cancelled after the finish).
WINDOW_MIN = 60


def pending_rapports(conn, now_ms: float) -> list:
    return repo.courses_awaiting_rapports(conn, int(now_ms - WINDOW_MIN * 60_000))


def main():
    conn = repo.connect()
    ids = pending_rapports(conn, time.time() * 1000)
    conn.close()
    print(f"Rapports en attente : {len(ids)} {' '.join(ids)}".rstrip())
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as f:
            f.write(f"pending_rapports={len(ids)}\n")


if __name__ == "__main__":
    main()
