from shakespeare_geo.aggregate import center_of_gravity


def test_center_of_gravity_weighted_mean():
    rows = [
        {"geocode_lat": 10.0, "geocode_lon": 20.0, "weight": 2.0},
        {"geocode_lat": 40.0, "geocode_lon": 50.0, "weight": 1.0},
    ]

    lat, lon = center_of_gravity(rows)

    assert round(lat, 6) == 20.0
    assert round(lon, 6) == 30.0


def test_center_of_gravity_empty_rows():
    lat, lon = center_of_gravity([])
    assert lat == 0.0
    assert lon == 0.0


def test_center_of_gravity_ignores_nan_values():
    rows = [
        {"geocode_lat": float("nan"), "geocode_lon": 20.0, "weight": 1.0},
        {"geocode_lat": 30.0, "geocode_lon": float("nan"), "weight": 1.0},
        {"geocode_lat": 45.0, "geocode_lon": 10.0, "weight": 1.0},
    ]

    lat, lon = center_of_gravity(rows)
    assert lat == 45.0
    assert lon == 10.0
