from datetime import date

from collect.normalize import normalize_partant, normalize_rapports
from collect.pipeline import collect_day
from collect import scraper
from db import repository as repo
from tests.conftest import DAY, FIXTURES, FakeHttp, load


def test_collect_day_stores_french_races_only(filled_conn):
    hippodromes = {r[0] for r in filled_conn.execute("SELECT DISTINCT hippodrome FROM courses")}
    assert hippodromes == {"COMPIEGNE", "LYON-PARILLY", "VINCENNES"}
    assert repo.day_is_complete(filled_conn, DAY.isoformat())


def test_quinte_course_normalized(filled_conn):
    c = filled_conn.execute("SELECT * FROM courses WHERE id_course='2026-09-15-R1C1'").fetchone()
    assert c["is_quinte"] == 1
    assert c["discipline"] == "Plat"
    assert c["distance_m"] == 2800
    assert c["heure_depart"] == "13:55"
    assert c["arrivee"] == "7-8-6-4-12"
    assert c["paris"] == "QUARTE_PLUS,QUINTE_PLUS,TIERCE"


def test_partants_and_payouts(filled_conn):
    rows = repo.partants_for_course(filled_conn, "2026-09-15-R1C1")
    assert len(rows) == 16
    chess = rows[0]
    assert chess["nom_cheval"] == "CHESS"
    assert chess["cote_matin"] == 6.5 and chess["cote_actuelle"] == 9.1
    assert chess["gains_carriere"] == 113452
    assert chess["poids_kg"] == 61.0
    rapports = {(r["type_pari"], r["libelle"]): r for r in repo.rapports_for_course(filled_conn, "2026-09-15-R1C1")}
    assert rapports[("SIMPLE_GAGNANT", "Simple gagnant")]["rapport"] == 4.2
    assert rapports[("QUINTE_PLUS", "Quinté+ Ordre")]["rapport"] == 795.4


def test_collect_is_idempotent(filled_conn):
    before = filled_conn.execute("SELECT COUNT(*) FROM partants").fetchone()[0]
    http = FakeHttp()
    collect_day(filled_conn, http, DAY, repo.now_iso(), today=date(2026, 10, 16))
    after = filled_conn.execute("SELECT COUNT(*) FROM partants").fetchone()[0]
    assert before == after
    # The finished race (arrival + payouts stored) is not requested again.
    assert not any("/R1/C1/" in url for url in http.urls)


def test_non_partant_and_missing_fields():
    raw = {"numPmu": 3, "nom": "X", "statut": "NON_PARTANT"}
    row = normalize_partant("id", raw)
    assert row["non_partant"] == 1
    assert row["cote_matin"] is None and row["gains_carriere"] is None


def test_refunded_bets_are_skipped():
    raw = load("rapports_15092026_R1C1.json")
    raw[0]["rembourse"] = True
    types = {r["type_pari"] for r in normalize_rapports("id", raw)}
    assert raw[0]["typePari"] not in types


def test_scraper_parses_recorded_pages():
    links = scraper.parse_race_links((FIXTURES / "turffr_index.html").read_text(encoding="utf-8"))
    assert links and all("/arrivees-rapports/" in link for link in links)
    parsed = scraper.parse_arrival_page((FIXTURES / "turffr_arrivee.html").read_text(encoding="utf-8"))
    assert parsed == (date(2026, 10, 16), 1, 6, "8-11-9-12-17")
