"""Unofficial PMU JSON API endpoints (see DOCUMENTATION.md)."""
from datetime import date

from collect.http_client import PmuJsonClient


def _pmu_date(day: date) -> str:
    return day.strftime("%d%m%Y")


def fetch_programme(client: PmuJsonClient, day: date):
    data = client.get_json(f"programme/{_pmu_date(day)}")
    return (data or {}).get("programme")


def fetch_participants(client: PmuJsonClient, day: date, reunion: int, course: int):
    data = client.get_json(f"programme/{_pmu_date(day)}/R{reunion}/C{course}/participants")
    return (data or {}).get("participants")


def fetch_rapports(client: PmuJsonClient, day: date, reunion: int, course: int):
    return client.get_json(f"programme/{_pmu_date(day)}/R{reunion}/C{course}/rapports-definitifs")
