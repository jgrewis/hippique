"""Fallback HTML scraper (turf-fr.com) used only when the PMU JSON API is down.

It recovers official arrivals for today's races (the site only lists recent
days). Programmes and odds are not scraped: the page structure is too
volatile to be worth it for a fallback.
"""
import re
from datetime import date
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

import config
from collect.http_client import HttpClient

RACE_LINK = re.compile(r"/courses-pmu/arrivees-rapports/r\d+-[\w-]+-\d+$")
RACE_CODE = re.compile(r"R(\d+)C(\d+)")
FR_DATE = re.compile(r"(\d{1,2})\s+([a-zéû]+)\s+(\d{4})", re.IGNORECASE)
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre")


def parse_race_links(index_html: str, base_url: str = config.TURFFR_RESULTS_INDEX) -> list:
    """Absolute race URLs, restricted to the index's own host (no request to arbitrary hosts)."""
    soup = BeautifulSoup(index_html, "html.parser")
    host = urlparse(base_url).netloc
    links = set()
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a["href"])
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.netloc == host and RACE_LINK.search(parsed.path):
            links.add(url)
    return sorted(links)


def _page_date(soup):
    meta = soup.find("meta", attrs={"name": "description"})
    match = FR_DATE.search(meta.get("content", "")) if meta else None
    if not match or match.group(2).lower() not in MONTHS:
        return None
    return date(int(match.group(3)), MONTHS.index(match.group(2).lower()) + 1, int(match.group(1)))


def parse_arrival_page(page_html: str):
    """Return (race date, num_reunion, num_course, "8-11-9-12-17") or None if not available."""
    soup = BeautifulSoup(page_html, "html.parser")
    title = soup.find("h1", id="current-page-breadcrumb")
    arrival = soup.find("input", id="coursearrivee")
    if not title or not arrival or not arrival.get("value", "").strip():
        return None
    code = RACE_CODE.search(title.get_text())
    numbers = re.findall(r"\d+", arrival["value"])
    day = _page_date(soup)
    if not code or not numbers or not day:
        return None
    return day, int(code.group(1)), int(code.group(2)), "-".join(numbers[:5])


def fetch_arrivals(http: HttpClient, day: date) -> list:
    """Return [(num_reunion, num_course, arrivee)] for `day` (the index only lists recent days)."""
    index = http.get(config.TURFFR_RESULTS_INDEX)
    if index.status_code != 200:
        return []
    results = []
    for url in parse_race_links(index.text):
        page = http.get(url)
        if page.status_code == 200:
            parsed = parse_arrival_page(page.text)
            # The index mixes several days: keep only the requested one.
            if parsed and parsed[0] == day:
                results.append(parsed[1:])
    return results
