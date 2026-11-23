from __future__ import annotations

from .open_meteo import ingest_open_meteo
from .usgs import ingest_usgs


def bronze_pipeline(start_date: str | None = None) -> dict[str, list[str]]:
    open_meteo_locations = ingest_open_meteo(start_date=start_date)
    usgs_locations = ingest_usgs(start_date=start_date)

    print(
        f"Bronze ingestion complete: {len(open_meteo_locations)} Open-Meteo "
        f"partition(s), {len(usgs_locations)} USGS partition(s)"
    )

    return {"open_meteo": open_meteo_locations, "usgs": usgs_locations}


if __name__ == "__main__":
    bronze_pipeline()
