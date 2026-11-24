from __future__ import annotations

import threading
import time
from typing import Any

import requests

USGS_REQUESTS_PER_HOUR = 1_000
OPEN_METEO_REQUESTS_PER_HOUR = 5_000

DEFAULT_TIMEOUT = 180
DEFAULT_MAX_RETRIES = 5

RETRYABLE_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)


class RateLimiter:
    def __init__(self, requests_per_hour: int) -> None:
        if requests_per_hour <= 0:
            raise ValueError("requests_per_hour must be positive")
        self.min_interval = 3600.0 / requests_per_hour
        self._last_request = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self.min_interval - (now - self._last_request)
            if delay > 0:
                time.sleep(delay)
            self._last_request = time.monotonic()


def get_json(
    limiter: RateLimiter,
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Any:
    attempt = 0
    while True:
        limiter.wait()
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=timeout
            )
        except RETRYABLE_ERRORS:
            attempt += 1
            if attempt > max_retries:
                raise
            time.sleep(min(2**attempt, 60))
            continue

        if attempt < max_retries and (
            response.status_code == 429 or response.status_code >= 500
        ):
            attempt += 1
            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after)
            except (TypeError, ValueError):
                delay = min(2**attempt, 60)
            time.sleep(max(delay, 1.0))
            continue

        response.raise_for_status()
        return response.json()


USGS_LIMITER = RateLimiter(USGS_REQUESTS_PER_HOUR)
OPEN_METEO_LIMITER = RateLimiter(OPEN_METEO_REQUESTS_PER_HOUR)
