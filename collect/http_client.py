"""Polite HTTP client: throttling, retries and host fallback."""
import logging
import time

import requests

import config

log = logging.getLogger(__name__)


class SourceUnavailable(Exception):
    """Every host failed for a request that should have returned data."""


class HttpClient:
    def __init__(self, delay_s: float = config.REQUEST_DELAY_S, session=None):
        self.delay_s = delay_s
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json, text/html"})
        self._last_call = 0.0
        self.request_count = 0

    def _throttle(self):
        wait = self.delay_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def get(self, url: str):
        """Return a Response with status 200/204/404, or raise after retries."""
        last_error = None
        for attempt in range(1, config.MAX_RETRIES + 1):
            self._throttle()
            self.request_count += 1
            try:
                resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT_S)
                if resp.status_code in (200, 204, 404):
                    return resp
                last_error = f"HTTP {resp.status_code}"
            except requests.RequestException as exc:
                last_error = str(exc)
            log.warning("Attempt %d failed for %s: %s", attempt, url, last_error)
            time.sleep(2 ** attempt)
        raise SourceUnavailable(f"{url}: {last_error}")


class PmuJsonClient:
    """Tries each PMU host in turn; returns None when the data does not exist (204/404)."""

    def __init__(self, http: HttpClient, hosts=config.PMU_HOSTS):
        self.http = http
        self.hosts = hosts

    def get_json(self, path: str):
        errors = []
        for host in self.hosts:
            try:
                resp = self.http.get(f"{host}/{path}")
            except SourceUnavailable as exc:
                errors.append(str(exc))
                continue
            if resp.status_code != 200 or not resp.content:
                return None
            try:
                return resp.json()
            except ValueError as exc:
                errors.append(f"{host}: invalid JSON ({exc})")
        raise SourceUnavailable(" | ".join(errors))
