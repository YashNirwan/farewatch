import pytest

from farewatch import db


@pytest.fixture
def conn():
    return db.connect(":memory:")


def test_record_and_read_observation(conn):
    db.record_observation(conn, "JFK", "SEA", "2026-08-15", 350.0, "USD")
    assert db.route_prices(conn, "JFK", "SEA", "2026-08") == [350.0]


def test_route_prices_filters_by_month_prefix(conn):
    db.record_observation(conn, "JFK", "SEA", "2026-08-01", 300.0, "USD")
    db.record_observation(conn, "JFK", "SEA", "2026-08-31", 320.0, "USD")
    db.record_observation(conn, "JFK", "SEA", "2026-09-01", 500.0, "USD")
    assert sorted(db.route_prices(conn, "JFK", "SEA", "2026-08")) == [300.0, 320.0]


def test_alert_dedup_via_fingerprint(conn):
    fp = "price:JFK:SEA:2026-08-15:200"
    assert db.already_alerted(conn, fp) is False
    db.record_alert(conn, fp, "price", "cheap fare")
    assert db.already_alerted(conn, fp) is True


def test_record_alert_is_idempotent(conn):
    fp = "price:JFK:SEA:2026-08-15:200"
    db.record_alert(conn, fp, "price", "first message")
    db.record_alert(conn, fp, "price", "second message")  # must not raise or overwrite
    row = conn.execute("SELECT message FROM alerts WHERE fingerprint = ?", (fp,)).fetchone()
    assert row["message"] == "first message"
