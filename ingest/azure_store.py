from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .settings import Settings

PARTITION_PREFIX = "ingest_date="
PART_FILE = "part-000.json"


def date_range(start: str, end: str):
    cursor = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while cursor <= stop:
        yield cursor.isoformat()
        cursor += timedelta(days=1)


def contiguous_runs(dates):
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
    # yearly windows keep requests under the USGS continuous 1100-day limit
    cursor = date.fromisoformat(start)
    stop = date.fromisoformat(end)
    while cursor <= stop:
        chunk_end = min(date(cursor.year, 12, 31), stop)
        yield cursor.isoformat(), chunk_end.isoformat()
        cursor = chunk_end + timedelta(days=1)


def window_start(day: str, start: str, lookback_days: int) -> str:
    candidate = (
        date.fromisoformat(day) - timedelta(days=lookback_days)
    ).isoformat()
    return max(candidate, start)


def usgs_prefix(station_site_no: str, data_type: str, parameter_code: str) -> str:
    return (
        f"usgs/{data_type}/parameter_code={parameter_code}"
        f"/station_id={station_site_no}"
    )


def open_meteo_prefix(station_site_no: str) -> str:
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


def _use_local(settings: Settings) -> bool:
    return not (settings.azure_storage_account and settings.azure_storage_container)


def existing_dates(settings: Settings, prefix: str) -> set[str]:
    if _use_local(settings):
        base = Path(settings.local_output_dir) / settings.bronze_prefix / prefix
        if not base.is_dir():
            return set()
        return {
            part.parent.name[len(PARTITION_PREFIX):]
            for part in base.glob(f"{PARTITION_PREFIX}*/{PART_FILE}")
        }

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
    relative = f"{prefix}/{PARTITION_PREFIX}{ingest_date}/{PART_FILE}"
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    if _use_local(settings):
        path = Path(settings.local_output_dir) / settings.bronze_prefix / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        return str(path)

    blob_name = f"{settings.bronze_prefix}/{relative}"
    blob = _container_client(settings).get_blob_client(blob_name)
    blob.upload_blob(body.encode("utf-8"), overwrite=True)
    return blob_name
