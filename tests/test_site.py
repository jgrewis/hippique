import re
from html import unescape

from predict.forecast import forecast_day
from site_builder import template_filters as f
from site_builder import views
from site_builder.builder import build


def test_filters_format_french():
    assert f.fr_date("2026-10-16") == "vendredi 16 octobre 2026"
    assert f.cote(9.1) == "9,1"
    assert f.pct(0.1234) == "12,3 %"
    assert f.euros(50900) == "50 900 €"
    assert 'class="m-win"' in f.musique_html("1a")
    assert "<script>" not in str(f.musique_html("<script>1a"))


def test_build_generates_pages_with_valid_links(filled_conn, tmp_path):
    # Forecast as if it were the morning of the race, so the course page shows a forecast.
    forecast_day(filled_conn, "2026-09-15", None, now_ms=0)
    out = tmp_path / "site"
    build(filled_conn, out)
    pages = list(out.rglob("*.html"))
    assert (out / "index.html").exists()
    assert (out / "course" / "2026-09-15-R1C1.html").exists()
    course_html = (out / "course" / "2026-09-15-R1C1.html").read_text(encoding="utf-8")
    assert "Tous les pronostics" in course_html and "Le Parisien" in course_html and "CHESS" in course_html
    assert "Consensus de toutes les sources" in course_html

    # Every relative link and asset must resolve to a generated file.
    for page in pages:
        if page.name == "404.html":
            continue
        html = page.read_text(encoding="utf-8")
        for target in re.findall(r'(?:href|src)="([^"#]+)"', html):
            if target.startswith(("http", "mailto:")):
                continue
            resolved = (page.parent / target).resolve()
            assert resolved.exists(), f"{page.relative_to(out)} -> {target}"


def test_no_external_resources(filled_conn, tmp_path):
    out = tmp_path / "site"
    build(filled_conn, out)
    for page in out.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        assert not re.search(r'(?:src|href)="https?://', html), page


def test_no_third_party_text_published(filled_conn, tmp_path):
    """Journalists' and PMU comments are copyrighted: none may appear on the public site."""
    from tests.conftest import load
    detailed = load("pronostics-detailles_15092026_R1C1.json")
    texts = [detailed["commentaire"]["texte"]] + [c["commentaire"] for c in detailed["cribles"] if c.get("commentaire")]
    texts += [s["commentaire"] for s in load("pronostics_15092026_R1C1.json")["selection"] if s.get("commentaire")]
    out = tmp_path / "site"
    build(filled_conn, out)
    # Unescape so that an apostrophe rendered as &#39; cannot hide a match.
    html = unescape("".join(p.read_text(encoding="utf-8") for p in out.rglob("*.html")))
    for text in texts:
        assert text[:40] not in html


def test_course_neighbours_follow_start_order_across_meetings():
    def course(reunion, num, heure):
        return {"id_course": f"R{reunion}C{num}", "num_reunion": reunion, "num_course": num,
                "heure_depart": heure, "nom_course": f"Prix {reunion}-{num}"}

    courses = [course(2, 1, "13:00"), course(1, 2, "13:30"), course(1, 1, "13:00"), course(3, 1, None)]
    assert [c["id_course"] for c in views.chronological(courses)] == ["R1C1", "R2C1", "R1C2", "R3C1"]
    neighbours = views.course_neighbours(courses)
    assert neighbours["R1C1"][0] is None
    assert neighbours["R3C1"][1] is None
    assert neighbours["R2C1"] == (course(1, 1, "13:00"), course(1, 2, "13:30"))


def test_course_pages_get_neighbours_from_builder_data(filled_conn):
    day = filled_conn.execute("SELECT MIN(date_course) FROM courses").fetchone()[0]
    ctx = views.day_context(filled_conn, day, [day])
    ordered = views.chronological([c for r in ctx["reunions"] for c in r["courses"]])
    first, second = ordered[0], ordered[1]
    page = views.course_context(filled_conn, first, ctx["neighbours"][first["id_course"]])
    assert page["prev_course"] is None
    assert page["next_course"]["id_course"] == second["id_course"]
    last = views.course_context(filled_conn, ordered[-1], ctx["neighbours"][ordered[-1]["id_course"]])
    assert last["next_course"] is None
