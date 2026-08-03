from farewatch.livewatch import _combos, _select

CFG = {
    "origins": ["JFK", "EWR", "LGA"],
    "search_window_days": [21, 120],
    "watches": [{"destination": "SEA", "max_price": 250, "trip_days": [3, 7, 14]}],
}


def test_combos_cover_every_origin_and_the_full_window():
    combos = _combos(CFG)
    origins = {origin for _, origin, _, _ in combos}
    offsets = {offset for _, _, offset, _ in combos}
    assert origins == set(CFG["origins"])
    assert min(offsets) == 21
    assert max(offsets) <= 120


def test_select_returns_requested_count_without_duplicates():
    combos = _combos(CFG)
    picked = _select(combos, 80, shift=0)
    assert len(picked) == 80
    assert len({(o, off, ln) for _, o, off, ln in picked}) == 80


def test_select_spreads_across_the_calendar_not_a_contiguous_block():
    combos = _combos(CFG)
    picked = _select(combos, 80, shift=0)
    offsets = sorted({offset for _, _, offset, _ in picked})
    window = CFG["search_window_days"]
    # a contiguous slice would cluster near the start; a strided pick should
    # reach both ends of the booking window
    assert min(offsets) <= window[0] + 10
    assert max(offsets) >= window[1] - 10


def test_select_covers_all_origins_in_a_single_run():
    combos = _combos(CFG)
    picked = _select(combos, 80, shift=0)
    assert {origin for _, origin, _, _ in picked} == set(CFG["origins"])


def test_successive_shifts_reach_new_combos():
    combos = _combos(CFG)
    first = {(o, off, ln) for _, o, off, ln in _select(combos, 80, shift=0)}
    second = {(o, off, ln) for _, o, off, ln in _select(combos, 80, shift=1)}
    assert first != second


def test_select_returns_everything_when_budget_exceeds_combos():
    combos = _combos(CFG)
    picked = _select(combos, len(combos) + 50, shift=3)
    assert len(picked) == len(combos)
