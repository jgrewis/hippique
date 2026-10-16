import re

from predict.forecast import forecast_day
from site_builder import template_filters as f
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
    assert "Pronostic statistique" in course_html and "CHESS" in course_html

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
