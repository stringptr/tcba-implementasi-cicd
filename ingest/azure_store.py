"""Helpers for writing raw JSON bronze partitions to Azure Data Lake Storage.

Bronze stores the payload returned by the source APIs verbatim (no column
renames, no metadata columns). Partitions use the bare-value hierarchy:

* USGS: ``usgs/{daily|continuous}/parameter_code={code}/station_id={id}``
* Open-Meteo: ``open-meteo/station_id={id}``

Blob names are ``{BRONZE_PREFIX}/{relative}/ingest_date=YYYY-MM-DD/part-000.json``
inside a single ADLS container. Every calendar day is stored as its own
``ingest_date`` partition containing that day **plus the previous
``LOOKBACK_DAYS`` days** (default 7), so a partition is an 8-day rolling window
clipped at the dataset start. All dates are UTC. Writing is idempotent: existing
parts are skipped so a backfill can be stopped and resumed later.

Authentication uses ``DefaultAzureCredential``, which in GitHub Actions picks up
the federated token that ``azure/login`` exports (no client secret).
"""

from __future__ import annotations

import json
from datetime import date, timedelta

from .settings import Settings

PARTITION_PREFIX = "ingest_date="
PART_FILE = "part-000.json"


def date_range(start: str, end: str):
    """Yield every ISO date from ``start`` to ``end`` (inclusive)."""

    cursor = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while cursor <= stop:
        yield cursor.isoformat()
        cursor += timedelta(days=1)


def contiguous_runs(dates):
    """Yield ``(start, end)`` tuples for runs of consecutive ISO dates."""

    ordered = sorted(dates)
    if not ordered:
        return

    run_start = run_end = date.fromisoformat(ordered[0])
    for raw in ordered[1:]:
        current = date.fromisoformat(raw)
        if current == run_end + timedelta(days=1):
            run_end = current
            continue
        yield run_start.isoformat(), run_end.isoformat()
        run_start = run_end = current
    yield run_start.isoformat(), run_end.isoformat()


def year_chunks(start: str, end: str):
    """Yield calendar-year windows covering ``start..end``.

    The USGS ``continuous`` collection rejects ranges longer than 1100 days, so
    yearly windows keep every request safely below that limit.
    """

    cursor = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while cursor <= stop:
        chunk_end = min(date(cursor.year, 12, 31), stop)
        yield cursor.isoformat(), chunk_end.isoformat()
        cursor = chunk_end + timedelta(days=1)


def window_start(day: str, start: str, lookback_days: int) -> str:
    """Return the first date of the lookback window for ``day``.

    The window is clipped at the dataset ``start`` so the earliest partitions
    contain fewer than ``lookback_days + 1`` days.
    """

    candidate = (
        date.fromisoformat(day) - timedelta(days=lookback_days)
    ).isoformat()
    return max(candidate, start)


def usgs_prefix(station_site_no: str, data_type: str, parameter_code: str) -> str:
    """Relative partition prefix for a USGS parameter/station."""

    return (
        f"usgs/{data_type}/parameter_code={parameter_code}"
        f"/station_id={station_site_no}"
    )


def open_meteo_prefix(station_site_no: str) -> str:
    """Relative partition prefix for an Open-Meteo station."""

    return f"open-meteo/station_id={station_site_no}"


_CLIENTS: dict[tuple, object] = {}


def _container_client(settings: Settings):
    if not settings.azure_storage_account or not settings.azure_storage_container:
        raise RuntimeError(
            "AZURE_STORAGE_ACCOUNT and AZURE_STORAGE_CONTAINER must be set to "
            "write to Azure Data Lake Storage"
        )

    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    cache_key = (settings.azure_storage_account, settings.azure_storage_container)
    client = _CLIENTS.get(cache_key)
    if client is None:
        account_url = f"https://{settings.azure_storage_account}.blob.core.windows.net"
        service = BlobServiceClient(account_url, credential=DefaultAzureCredential())
        client = service.get_container_client(settings.azure_storage_container)
        _CLIENTS[cache_key] = client
    return client


def _blob_prefix(settings: Settings, prefix: str) -> str:
    return f"{settings.bronze_prefix}/{prefix}"


def existing_dates(settings: Settings, prefix: str) -> set[str]:
    """Return the set of ``ingest_date`` values that already have a part file."""

    container = _container_client(settings)
    blob_prefix = f"{_blob_prefix(settings, prefix)}/{PARTITION_PREFIX}"
    dates: set[str] = set()
    for blob in container.list_blobs(name_starts_with=blob_prefix):
        if not blob.name.endswith(f"/{PART_FILE}"):
            continue
        for segment in blob.name.split("/"):
            if segment.startswith(PARTITION_PREFIX):
                dates.add(segment[len(PARTITION_PREFIX):])
    return dates


def write_payload(
    settings: Settings,
    prefix: str,
    ingest_date: str,
    payload: dict,
) -> str:
    """Write ``payload`` as ``{prefix}/ingest_date=<date>/part-000.json``.

    Returns the blob name that was written.
    """

    blob_name = (
        f"{_blob_prefix(settings, prefix)}/"
        f"{PARTITION_PREFIX}{ingest_date}/{PART_FILE}"
    )
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    blob = _container_client(settings).get_blob_client(blob_name)
    blob.upload_blob(body.encode("utf-8"), overwrite=True)
    return blob_name
