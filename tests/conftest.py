import json
from datetime import date
from pathlib import Path

import pytest

from collect.pipeline import collect_day
from db import repository as repo

FIXTURES = Path(__file__).parent / "fixtures"
DAY = date(2026, 9, 15)
TODAY = date(2026, 10, 16)


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload=None, status=200):
        self.status_code = status if payload is not None else 204
        self._payload = payload
        self.content = json.dumps(payload).encode() if payload is not None else b""
        self.text = self.content.decode()

    def json(self):
        return self._payload


class FakeHttp:
    """Serves recorded PMU responses: only R1C1 of 15/09/2026 has data (participants, payouts, forecasts)."""

    def __init__(self):
        self.request_count = 0
        self.urls = []

    def get(self, url):
        self.request_count += 1
        self.urls.append(url)
        if url.endswith("/programme/15092026"):
            return FakeResponse(load("programme_15092026.json"))
        if url.endswith("/15092026/R1/C1/participants"):
            return FakeResponse(load("participants_15092026_R1C1.json"))
        if url.endswith("/15092026/R1/C1/rapports-definitifs"):
            return FakeResponse(load("rapports_15092026_R1C1.json"))
        for endpoint in ("pronostics", "pronostics-detailles", "combinaisons"):
            if url.endswith(f"/15092026/R1/C1/{endpoint}"):
                return FakeResponse(load(f"{endpoint}_15092026_R1C1.json"))
        return FakeResponse(None)


@pytest.fixture
def conn(tmp_path):
    connection = repo.connect(tmp_path / "test.db")
    yield connection
    connection.close()


@pytest.fixture
def filled_conn(conn):
    collect_day(conn, FakeHttp(), DAY, repo.now_iso(), today=TODAY)
    return conn
