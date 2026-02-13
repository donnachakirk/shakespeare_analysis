from __future__ import annotations

import math
from typing import Iterable

import folium


def build_map(
    center_lat: float,
    center_lon: float,
    places: Iterable[dict],
    output_path: str,
) -> None:
    if not math.isfinite(center_lat) or not math.isfinite(center_lon):
        center_lat, center_lon = 0.0, 0.0

    m = folium.Map(location=[center_lat, center_lon], zoom_start=5)

    for place in places:
        lat = place.get("geocode_lat")
        lon = place.get("geocode_lon")
        if lat is None or lon is None:
            continue
        if not math.isfinite(lat) or not math.isfinite(lon):
            continue

        name = place.get("geocode_name") or place.get("normalized_place")
        count = place.get("mention_count", 1)
        popup = f"{name} (mentions: {count})"
        folium.CircleMarker(
            location=[lat, lon],
            radius=4 + min(count, 10),
            popup=popup,
            color="#1f77b4",
            fill=True,
            fill_opacity=0.7,
        ).add_to(m)

    m.save(output_path)
