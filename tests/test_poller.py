import datetime as dt

from farewatch import poller

CFG = {
    "origins": ["JFK", "EWR"],
    "destinations": ["SEA", "LAX", "MIA"],
    "search_window_days": [21, 120],
    "dates_per_route": 2,
}


def test_sample_dates_are_within_window_and_deterministic():
    today = dt.date(2026, 7, 25)
    lo, hi = CFG["search_window_days"]
    dates = poller._sample_dates(CFG, today)
    assert len(dates) == CFG["dates_per_route"]
    for d in dates:
        offset = (dt.date.fromisoformat(d) - today).days
        assert lo <= offset <= hi
    assert dates == poller._sample_dates(CFG, today)  # same day -> same sample


def test_sample_dates_change_across_days():
    dates_a = poller._sample_dates(CFG, dt.date(2026, 7, 25))
    dates_b = poller._sample_dates(CFG, dt.date(2026, 7, 26))
    assert dates_a != dates_b


def test_rotated_routes_covers_every_pair_exactly_once():
    today = dt.date(2026, 7, 25)
    routes = poller._rotated_routes(CFG, today)
    expected = {(o, d) for o in CFG["origins"] for d in CFG["destinations"]}
    assert set(routes) == expected
    assert len(routes) == len(expected)


def test_rotated_routes_shifts_daily_so_budget_reaches_every_route_eventually():
    routes_day1 = poller._rotated_routes(CFG, dt.date(2026, 7, 25))
    routes_day2 = poller._rotated_routes(CFG, dt.date(2026, 7, 26))
    assert routes_day1[0] != routes_day2[0] or len(routes_day1) == 1
