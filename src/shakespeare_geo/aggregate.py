from __future__ import annotations

import math
from typing import Iterable, Tuple


def center_of_gravity(rows: Iterable[dict]) -> Tuple[float, float]:
    weighted = []
    for row in rows:
        lat = row.get("geocode_lat")
        lon = row.get("geocode_lon")
        weight = row.get("weight", 1.0)

        if lat is None or lon is None:
            continue
        if not math.isfinite(lat) or not math.isfinite(lon):
            continue
        if not math.isfinite(weight) or weight <= 0:
            continue

        weighted.append((lat, lon, weight))

    if not weighted:
        return (0.0, 0.0)

    total_weight = sum(w for _, _, w in weighted)
    lat = sum(lat * w for lat, _, w in weighted) / total_weight
    lon = sum(lon * w for _, lon, w in weighted) / total_weight
    return (lat, lon)
