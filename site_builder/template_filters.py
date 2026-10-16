"""Jinja2 filters: French formatting of dates, odds, amounts and the musique."""
import re
from datetime import date, datetime

from markupsafe import Markup, escape

DAYS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
          "septembre", "octobre", "novembre", "décembre")
BET_LABELS = {
    "QUINTE_PLUS": "Quinté+", "QUARTE_PLUS": "Quarté+", "TIERCE": "Tiercé", "MULTI": "Multi",
    "DEUX_SUR_QUATRE": "2sur4", "COUPLE_GAGNANT": "Couplé gagnant", "COUPLE_PLACE": "Couplé placé",
    "SIMPLE_GAGNANT": "Simple gagnant", "SIMPLE_PLACE": "Simple placé",
}


def _as_date(value):
    return date.fromisoformat(value) if isinstance(value, str) else value


def fr_date(value, with_day=True) -> str:
    d = _as_date(value)
    text = f"{d.day} {MONTHS[d.month - 1]} {d.year}"
    return f"{DAYS[d.weekday()]} {text}" if with_day else text


def fr_month(value) -> str:
    d = _as_date(value + "-01" if len(value) == 7 else value)
    return f"{MONTHS[d.month - 1]} {d.year}".capitalize()


def fr_datetime_utc(value) -> str:
    """'2026-10-16T06:02:11Z' -> '16/10/2026 06:02 UTC'."""
    if not value:
        return "–"
    dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%d/%m/%Y %H:%M UTC")


def fr_number(value, decimals=1) -> str:
    if value is None:
        return "–"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def cote(value) -> str:
    return fr_number(value, 1) if value else "–"


def pct(value, decimals=1) -> str:
    """0.1234 -> '12,3 %'."""
    return "–" if value is None else f"{fr_number(100 * value, decimals)} %"


def euros(value) -> str:
    return "–" if value is None else f"{fr_number(value, 0)} €"


def rapport(value) -> str:
    return "–" if value is None else f"{fr_number(value, 2)} €"


def bet_label(code: str) -> str:
    return BET_LABELS.get(code, code.replace("_", " ").capitalize())


PERF = re.compile(r"(\(\d+\))|([0-9DATR])([amphsc])", re.IGNORECASE)


def musique_html(value) -> Markup:
    """Colour wins, places and failures in the musique string."""
    if not value:
        return Markup('<span class="muted">inédit</span>')
    parts = []
    for m in PERF.finditer(value):
        if m.group(1):
            parts.append(f'<span class="m-year">{escape(m.group(1))}</span>')
            continue
        result = m.group(2).upper()
        cls = "m-win" if result == "1" else "m-place" if result in "23" else "m-fail" if result in "DATR" else "m-other"
        parts.append(f'<span class="{cls}">{escape(m.group(0))}</span>')
    return Markup("".join(parts))


def register(env):
    env.filters.update(
        fr_date=fr_date, fr_month=fr_month, fr_datetime_utc=fr_datetime_utc, fr_number=fr_number,
        cote=cote, pct=pct, euros=euros, rapport=rapport, bet_label=bet_label, musique_html=musique_html,
    )
