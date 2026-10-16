"""Static site generation.

    python -m site_builder.builder [--output output/]
"""
import argparse
import logging
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

import config
from collect.pipeline import today_paris
from db import repository as repo
from site_builder import template_filters, views

HERE = Path(__file__).resolve().parent
log = logging.getLogger("builder")


def make_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(HERE / "templates"),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template_filters.register(env)
    return env


def _write(path: Path, html: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def build(conn, out: Path):
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(HERE / "static", out / "assets")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")

    env = make_env()
    common = {"site_title": config.SITE_TITLE, "last_run": repo.last_run_summary(conn), "today": today_paris().isoformat()}

    def render(template, path, root, active, **ctx):
        _write(out / path, env.get_template(template).render(root=root, active=active, **common, **ctx))

    dates = repo.dates_available(conn)
    pages = 0
    for day in dates:
        ctx = views.day_context(conn, day, dates)
        render("day.html", f"jour/{day}.html", "../", "jour", **ctx)
        pages += 1
        for reunion in ctx["reunions"]:
            for course in reunion["courses"]:
                render("course.html", f"course/{course['id_course']}.html", "../", "jour", **views.course_context(conn, course))
                pages += 1

    # Home page: today if collected, otherwise the most recent day available.
    home_day = common["today"] if common["today"] in dates else (dates[-1] if dates else None)
    if home_day:
        render("day.html", "index.html", "", "jour", previous=views.previous_results(conn, home_day, dates),
               **views.day_context(conn, home_day, dates))
    else:
        render("empty.html", "index.html", "", "jour")
    render("archives.html", "archives.html", "", "archives", **views.archives_context(conn))
    render("reliability.html", "fiabilite.html", "", "fiabilite", **views.reliability_context(conn))
    render("methodology.html", "methodo.html", "", "methodo")
    render("not_found.html", "404.html", config.SITE_BASE_PATH, "")
    log.info("Site généré : %d pages dans %s", pages + 5, out)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=config.OUTPUT_DIR)
    args = parser.parse_args()
    conn = repo.connect()
    build(conn, args.output)


if __name__ == "__main__":
    main()
