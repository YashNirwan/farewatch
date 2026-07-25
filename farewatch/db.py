"""SQLite storage for price observations and sent alerts."""

import sqlite3

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    origin TEXT NOT NULL,
    dest TEXT NOT NULL,
    depart_date TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    observed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_obs_route ON observations (origin, dest, depart_date);

CREATE TABLE IF NOT EXISTS alerts (
    fingerprint TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def record_observation(conn, origin, dest, depart_date, price, currency):
    conn.execute(
        "INSERT INTO observations (origin, dest, depart_date, price, currency) VALUES (?, ?, ?, ?, ?)",
        (origin, dest, depart_date, price, currency),
    )
    conn.commit()


def route_prices(conn, origin, dest, depart_month):
    """All observed prices for a route in a given departure month (YYYY-MM)."""
    rows = conn.execute(
        "SELECT price FROM observations WHERE origin = ? AND dest = ? AND depart_date LIKE ?",
        (origin, dest, depart_month + "%"),
    ).fetchall()
    return [r["price"] for r in rows]


def already_alerted(conn, fingerprint):
    return conn.execute(
        "SELECT 1 FROM alerts WHERE fingerprint = ?", (fingerprint,)
    ).fetchone() is not None


def record_alert(conn, fingerprint, kind, message):
    conn.execute(
        "INSERT OR IGNORE INTO alerts (fingerprint, kind, message) VALUES (?, ?, ?)",
        (fingerprint, kind, message),
    )
    conn.commit()
