"""Top level bronze ingestion pipeline.

Orchestrates the two source ingestions. Silver/gold transformations are
intentionally deferred; this stage only populates the bronze prefix of the
Azure Data Lake Storage container.
"""

from __future__ import annotations

from .open_meteo import ingest_open_meteo
from .usgs import ingest_usgs


def bronze_pipeline(start_date: str | None = None) -> dict[str, list[str]]:
    """Ingest Open-Meteo and USGS data into bronze for all active stations."""

    open_meteo_locations = ingest_open_meteo(start_date=start_date)
    usgs_locations = ingest_usgs(start_date=start_date)

    print(
        f"Bronze ingestion complete: {len(open_meteo_locations)} Open-Meteo "
        f"partition(s), {len(usgs_locations)} USGS partition(s)"
    )

    return {"open_meteo": open_meteo_locations, "usgs": usgs_locations}


if __name__ == "__main__":
    bronze_pipeline()
