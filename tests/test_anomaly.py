import pytest

from farewatch import anomaly, db

CFG = {
    "anomaly": {"ratio_threshold": 0.50, "min_observations": 8, "min_price": 40},
}


@pytest.fixture
def conn():
    return db.connect(":memory:")


def seed(conn, origin, dest, month, prices):
    for i, price in enumerate(prices):
        db.record_observation(conn, origin, dest, f"{month}-{i + 1:02d}", price, "USD")


def test_no_baseline_yet_is_never_an_anomaly(conn):
    is_anomaly, median, n = anomaly.check(conn, CFG, "JFK", "SEA", "2026-08-15", 50)
    assert is_anomaly is False
    assert median is None
    assert n == 0


def test_below_min_observations_does_not_alert(conn):
    seed(conn, "JFK", "SEA", "2026-08", [400, 410, 420, 430, 440, 450, 460])  # 7 < min 8
    is_anomaly, median, n = anomaly.check(conn, CFG, "JFK", "SEA", "2026-08-20", 50)
    assert is_anomaly is False
    assert n == 7


def test_price_at_exactly_the_ratio_threshold_alerts(conn):
    seed(conn, "JFK", "SEA", "2026-08", [400] * 8)  # median 400, threshold 0.5 -> 200
    is_anomaly, median, n = anomaly.check(conn, CFG, "JFK", "SEA", "2026-08-20", 200)
    assert median == 400
    assert is_anomaly is True


def test_price_just_above_threshold_does_not_alert(conn):
    seed(conn, "JFK", "SEA", "2026-08", [400] * 8)
    is_anomaly, _, _ = anomaly.check(conn, CFG, "JFK", "SEA", "2026-08-20", 201)
    assert is_anomaly is False


def test_normal_price_does_not_alert(conn):
    seed(conn, "JFK", "SEA", "2026-08", [610, 655, 640, 700, 610, 665, 645, 630])
    is_anomaly, median, n = anomaly.check(conn, CFG, "JFK", "SEA", "2026-08-20", 610)
    assert is_anomaly is False
    assert median == pytest.approx(642.5)


def test_deep_discount_alerts(conn):
    seed(conn, "JFK", "SEA", "2026-08", [610, 655, 640, 700, 610, 665, 645, 630])
    is_anomaly, median, n = anomaly.check(conn, CFG, "JFK", "SEA", "2026-08-22", 129)
    assert is_anomaly is True
    assert n == 8


def test_price_below_min_price_floor_never_alerts(conn):
    # guards against junk/zero fares masquerading as "anomalies"
    seed(conn, "JFK", "SEA", "2026-08", [610, 655, 640, 700, 610, 665, 645, 630])
    is_anomaly, _, _ = anomaly.check(conn, CFG, "JFK", "SEA", "2026-08-22", 15)
    assert is_anomaly is False


def test_only_same_route_and_month_feed_the_baseline(conn):
    seed(conn, "JFK", "SEA", "2026-08", [600] * 8)
    seed(conn, "JFK", "MIA", "2026-08", [100] * 8)  # different dest, must not leak in
    seed(conn, "JFK", "SEA", "2026-09", [50] * 8)  # different month, must not leak in
    is_anomaly, median, n = anomaly.check(conn, CFG, "JFK", "SEA", "2026-08-20", 290)
    assert median == 600
    assert n == 8
    assert is_anomaly is True
