"""SQLite access layer. All writes are idempotent upserts."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import config


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: Path = config.DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(config.SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate(conn)
    return conn


def _migrate(conn):
    """Bring a database created by an older version up to the current schema."""
    columns = {r["name"] for r in conn.execute("PRAGMA table_info(courses)")}
    if "externes_ok" not in columns:
        conn.execute("ALTER TABLE courses ADD COLUMN externes_ok INTEGER NOT NULL DEFAULT 0")
        # Finished days must be revisited once to fetch the third-party forecasts.
        conn.execute("UPDATE collect_days SET complete = 0")
        conn.commit()


def _upsert(conn, table: str, row: dict, keys: tuple):
    cols = list(row)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in keys)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
        f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {updates}",
        [row[c] for c in cols],
    )


def upsert_course(conn, row: dict):
    # Never erase a known arrival with an empty one (e.g. an inquiry in progress).
    if row.get("arrivee") is None:
        existing = conn.execute("SELECT arrivee FROM courses WHERE id_course=?", (row["id_course"],)).fetchone()
        if existing and existing["arrivee"]:
            row = {**row, "arrivee": existing["arrivee"]}
    _upsert(conn, "courses", row, ("id_course",))


def upsert_partant(conn, row: dict):
    # Keep the last known odds if the source no longer reports them.
    existing = conn.execute(
        "SELECT cote_matin, cote_actuelle FROM partants WHERE id_course=? AND numero=?",
        (row["id_course"], row["numero"]),
    ).fetchone()
    if existing:
        row = {
            **row,
            "cote_matin": row["cote_matin"] or existing["cote_matin"],
            "cote_actuelle": row["cote_actuelle"] or existing["cote_actuelle"],
        }
    _upsert(conn, "partants", row, ("id_course", "numero"))


def replace_rapports(conn, id_course: str, rows: list):
    conn.execute("DELETE FROM rapports WHERE id_course=?", (id_course,))
    for row in rows:
        _upsert(conn, "rapports", row, ("id_course", "type_pari", "libelle", "combinaison"))


def set_arrival(conn, id_course: str, arrivee: str):
    conn.execute(
        "UPDATE courses SET arrivee=?, updated_at=? WHERE id_course=? AND arrivee IS NULL",
        (arrivee, now_iso(), id_course),
    )


def course_state(conn, id_course: str) -> str:
    """'new' (to collect fully), 'externes' (finished, third-party data missing) or 'final'."""
    row = conn.execute(
        "SELECT c.arrivee IS NOT NULL AS has_arrival, c.externes_ok, "
        "(SELECT COUNT(*) FROM rapports r WHERE r.id_course=c.id_course) AS n_rapports "
        "FROM courses c WHERE c.id_course=?",
        (id_course,),
    ).fetchone()
    if not (row and row["has_arrival"] and row["n_rapports"]):
        return "new"
    return "final" if row["externes_ok"] else "externes"


def course_updated_at(conn, id_course: str):
    row = conn.execute("SELECT updated_at FROM courses WHERE id_course=?", (id_course,)).fetchone()
    return row["updated_at"] if row else None


def set_externes_ok(conn, id_course: str):
    conn.execute("UPDATE courses SET externes_ok=1 WHERE id_course=?", (id_course,))


def upsert_selection(conn, row: dict):
    # A ranking captured before the start is frozen: a later capture must not
    # replace it (it would no longer prove the forecast preceded the race).
    existing = conn.execute(
        "SELECT avant_depart FROM selections WHERE id_course=? AND source=?", (row["id_course"], row["source"])
    ).fetchone()
    if existing and existing["avant_depart"] and not row["avant_depart"]:
        return
    _upsert(conn, "selections", row, ("id_course", "source"))


def mark_day(conn, date_course: str, complete: bool):
    _upsert(conn, "collect_days", {"date_course": date_course, "complete": int(complete), "updated_at": now_iso()}, ("date_course",))


def day_is_complete(conn, date_course: str) -> bool:
    row = conn.execute("SELECT complete FROM collect_days WHERE date_course=?", (date_course,)).fetchone()
    return bool(row and row["complete"])


def log(conn, level: str, message: str, date_course: str = None, run_at: str = None):
    conn.execute(
        "INSERT INTO collect_log (run_at, date_course, level, message) VALUES (?, ?, ?, ?)",
        (run_at or now_iso(), date_course, level, message),
    )


def save_pronostics(conn, rows: list):
    for row in rows:
        _upsert(conn, "pronostics", row, ("id_course", "numero", "methode"))


# --- Read helpers used by the site builder and the models -------------------

def dates_available(conn) -> list:
    return [r[0] for r in conn.execute("SELECT DISTINCT date_course FROM courses ORDER BY date_course")]


def courses_for_day(conn, date_course: str) -> list:
    return conn.execute(
        "SELECT * FROM courses WHERE date_course=? ORDER BY num_reunion, num_course", (date_course,)
    ).fetchall()


def partants_for_course(conn, id_course: str) -> list:
    return conn.execute("SELECT * FROM partants WHERE id_course=? ORDER BY numero", (id_course,)).fetchall()


def rapports_for_course(conn, id_course: str) -> list:
    return conn.execute("SELECT * FROM rapports WHERE id_course=? ORDER BY rowid", (id_course,)).fetchall()


def pronostics_for_course(conn, id_course: str) -> dict:
    """{methode: {numero: row}}"""
    out = {}
    for r in conn.execute("SELECT * FROM pronostics WHERE id_course=?", (id_course,)):
        out.setdefault(r["methode"], {})[r["numero"]] = r
    return out


def selections_for_course(conn, id_course: str) -> list:
    return conn.execute(
        "SELECT source, famille, libelle, numeros, avant_depart FROM selections WHERE id_course=? ORDER BY famille, libelle, source",
        (id_course,),
    ).fetchall()


def all_selections(conn) -> dict:
    """{id_course: [rows]} for every course, in one query (avoids N+1 during backtests)."""
    out = {}
    for r in conn.execute("SELECT id_course, source, famille, libelle, numeros, avant_depart FROM selections"):
        out.setdefault(r["id_course"], []).append(r)
    return out


def last_run_summary(conn):
    row = conn.execute("SELECT MAX(run_at) AS run_at FROM collect_log").fetchone()
    if not row or not row["run_at"]:
        return None
    counts = {
        r["level"]: r["n"]
        for r in conn.execute(
            "SELECT level, COUNT(*) AS n FROM collect_log WHERE run_at=? GROUP BY level", (row["run_at"],)
        )
    }
    return {"run_at": row["run_at"], "errors": counts.get("ERROR", 0), "warnings": counts.get("WARNING", 0)}
