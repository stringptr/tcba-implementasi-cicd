from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Station:
    id: str
    site_no: str
    name: str
    latitude: float
    longitude: float


STATIONS: tuple[Station, ...] = (
    Station(
        id="USGS-11525670",
        site_no="11525670",
        name="Indian C near Douglas City, CA",
        latitude=40.65178087,
        longitude=-122.9144343,
    ),
    Station(
        id="USGS-11150500",
        site_no="11150500",
        name="Salinas River near Bradley, CA",
        latitude=35.9302434,
        longitude=-120.8687915,
    ),
    Station(
        id="USGS-11454000",
        site_no="11454000",
        name="Putah Creek near Winters, CA",
        latitude=38.5151562,
        longitude=-122.0818793,
    ),
)


def get_stations() -> tuple[Station, ...]:
    raw = os.getenv("STATIONS")
    if not raw:
        return STATIONS

    wanted = {token.strip() for token in raw.split(",") if token.strip()}
    selected = tuple(
        station
        for station in STATIONS
        if station.id in wanted or station.site_no in wanted
    )
    return selected or STATIONS
