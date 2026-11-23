from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

DEFAULT_HISTORIC_START_DATE = "2023-01-01"
DEFAULT_LOCAL_DIR = "./data"
DEFAULT_BRONZE_PREFIX = "bronze"
DEFAULT_EMPTY_GRACE_DAYS = 3
DEFAULT_LOOKBACK_DAYS = 7


def _env(name: str, default: str | None = None) -> str | None:
    # empty string is treated as unset
    value = os.getenv(name)
    return value if value not in (None, "") else default


def _yesterday_utc() -> str:
    return (datetime.now(UTC).date() - timedelta(days=1)).isoformat()


@dataclass(frozen=True)
class Settings:
    usgs_historic_start_date: str
    open_meteo_historic_start_date: str
    end_date: str
    usgs_api_key: str | None
    azure_storage_account: str
    azure_storage_container: str
    local_output_dir: str
    bronze_prefix: str
    empty_grace_days: int
    lookback_days: int


def get_settings(start_date: str | None = None) -> Settings:
    # end date is always yesterday (UTC) so the current day is never ingested
    return Settings(
        usgs_historic_start_date=start_date
        or _env("USGS_HISTORIC_START_DATE", DEFAULT_HISTORIC_START_DATE),
        open_meteo_historic_start_date=start_date
        or _env("OPEN_METEO_HISTORIC_START_DATE", DEFAULT_HISTORIC_START_DATE),
        end_date=_yesterday_utc(),
        usgs_api_key=_env("USGS_API_KEY"),
        azure_storage_account=_env("AZURE_STORAGE_ACCOUNT", ""),
        azure_storage_container=_env("AZURE_STORAGE_CONTAINER", ""),
        local_output_dir=_env("BRONZE_LOCAL_DIR", DEFAULT_LOCAL_DIR),
        bronze_prefix=_env("BRONZE_PREFIX", DEFAULT_BRONZE_PREFIX),
        empty_grace_days=int(
            _env("EMPTY_GRACE_DAYS", str(DEFAULT_EMPTY_GRACE_DAYS))
        ),
        lookback_days=int(_env("LOOKBACK_DAYS", str(DEFAULT_LOOKBACK_DAYS))),
    )
