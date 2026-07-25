"""Baseline math: is this price an anomaly for its route + month?"""

import statistics

from . import db


def check(conn, cfg, origin, dest, depart_date, price):
    """Return (is_anomaly, median, n_observations)."""
    rules = cfg["anomaly"]
    month = depart_date[:7]
    prices = db.route_prices(conn, origin, dest, month)
    if len(prices) < rules["min_observations"]:
        return False, None, len(prices)
    median = statistics.median(prices)
    is_anomaly = (
        price >= rules["min_price"]
        and price <= rules["ratio_threshold"] * median
    )
    return is_anomaly, median, len(prices)
