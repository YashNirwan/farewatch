import datetime as dt

from farewatch.livewatch import _combos, _offsets, _select

CFG = {
    "origins": ["JFK", "EWR", "LGA"],
    "search_window_days": [21, 120],
    "watches": [{"destination": "SEA", "max_price": 250, "trip_days": [3, 7, 14]}],
}

REVERSED_CFG = {
    "origins": ["JFK", "EWR", "LGA"],
    "search_window_days": [21, 120],
    "watches": [
        {
            "origins": ["SEA"],
            "destinations": ["JFK", "EWR", "LGA"],
            "depart_between": ["2026-12-12", "2026-12-24"],
            "max_price": 330,
            "trip_days": [7],
        }
    ],
}


def test_combos_cover_every_origin_and_the_full_window():
    combos = _combos(CFG)
    origins = {origin for _, origin, _, _, _ in combos}
    offsets = {offset for _, _, _, offset, _ in combos}
    assert origins == set(CFG["origins"])
    assert min(offsets) == 21
    assert max(offsets) <= 120


def test_combos_default_destination_to_the_single_destination_key():
    combos = _combos(CFG)
    assert {dest for _, _, dest, _, _ in combos} == {"SEA"}


def test_select_returns_requested_count_without_duplicates():
    combos = _combos(CFG)
    picked = _select(combos, 80, shift=0)
    assert len(picked) == 80
    assert len({(o, d, off, ln) for _, o, d, off, ln in picked}) == 80


def test_select_spreads_across_the_calendar_not_a_contiguous_block():
    combos = _combos(CFG)
    picked = _select(combos, 80, shift=0)
    offsets = sorted({offset for _, _, _, offset, _ in picked})
    window = CFG["search_window_days"]
    # a contiguous slice would cluster near the start; a strided pick should
    # reach both ends of the booking window
    assert min(offsets) <= window[0] + 10
    assert max(offsets) >= window[1] - 10


def test_select_covers_all_origins_in_a_single_run():
    combos = _combos(CFG)
    picked = _select(combos, 80, shift=0)
    assert {origin for _, origin, _, _, _ in picked} == set(CFG["origins"])


def test_successive_shifts_reach_new_combos():
    combos = _combos(CFG)
    first = {(o, d, off, ln) for _, o, d, off, ln in _select(combos, 80, shift=0)}
    second = {(o, d, off, ln) for _, o, d, off, ln in _select(combos, 80, shift=1)}
    assert first != second


def test_select_returns_everything_when_budget_exceeds_combos():
    combos = _combos(CFG)
    picked = _select(combos, len(combos) + 50, shift=3)
    assert len(picked) == len(combos)


def test_watch_can_reverse_direction_with_its_own_origins():
    combos = _combos(REVERSED_CFG)
    assert {origin for _, origin, _, _, _ in combos} == {"SEA"}
    assert {dest for _, _, dest, _, _ in combos} == {"JFK", "EWR", "LGA"}


def test_pinned_date_range_is_checked_daily_and_stays_in_range():
    today = dt.date(2026, 8, 15)
    watch = REVERSED_CFG["watches"][0]
    offsets = _offsets(watch, today, 21, 120)
    dates = [today + dt.timedelta(days=o) for o in offsets]
    assert min(dates).isoformat() == "2026-12-12"
    assert max(dates).isoformat() == "2026-12-24"
    assert len(dates) == 13  # every day in the range, not every third


def test_pinned_range_can_extend_past_the_rolling_window():
    today = dt.date(2026, 8, 15)
    watch = REVERSED_CFG["watches"][0]
    # Dec 24 is ~131 days out, beyond the 120-day default ceiling
    assert max(_offsets(watch, today, 21, 120)) > 120


def test_combos_never_pair_an_airport_with_itself():
    cfg = {
        "origins": ["JFK"],
        "search_window_days": [21, 30],
        "watches": [{"origins": ["JFK", "SEA"], "destinations": ["JFK", "SEA"],
                     "max_price": 200, "trip_days": [7]}],
    }
    for _, origin, dest, _, _ in _combos(cfg):
        assert origin != dest
