from __future__ import annotations

from typing import Iterable, Tuple


def center_of_gravity(rows: Iterable[dict]) -> Tuple[float, float]:
    weighted = [
        (row.get("geocode_lat"), row.get("geocode_lon"), row.get("weight", 1.0))
        for row in rows
        if row.get("geocode_lat") is not None and row.get("geocode_lon") is not None
    ]

    if not weighted:
        return (0.0, 0.0)

    total_weight = sum(w for _, _, w in weighted)
    lat = sum(lat * w for lat, _, w in weighted) / total_weight
    lon = sum(lon * w for _, lon, w in weighted) / total_weight
    return (lat, lon)
