"""Poll fare providers for watchlist routes, record prices, alert on anomalies."""

import datetime as dt
import os
import random

from . import alerts, anomaly, db


def _make_client(cfg):
    if os.environ.get("TRAVELPAYOUTS_TOKEN"):
        from .travelpayouts import TravelpayoutsClient
        return TravelpayoutsClient(one_way=cfg.get("one_way", True))
    from .amadeus import AmadeusClient
    return AmadeusClient()


def _sample_dates(cfg, today):
    """Deterministic per-day sample of departure dates inside the search window."""
    lo, hi = cfg["search_window_days"]
    rng = random.Random(today.toordinal())
    offsets = rng.sample(range(lo, hi + 1), cfg["dates_per_route"])
    return [(today + dt.timedelta(days=o)).isoformat() for o in sorted(offsets)]


def _rotated_routes(cfg, today):
    """All origin/dest pairs, rotated daily so the request budget covers everything over time."""
    routes = [(o, d) for o in cfg["origins"] for d in cfg["destinations"]]
    shift = today.toordinal() % len(routes)
    return routes[shift:] + routes[:shift]


def _fare_link(origin, dest, depart_date, meta):
    """Deep link to the exact cached itinerary when the provider gives one."""
    if meta and meta.get("link"):
        return "https://www.aviasales.com" + meta["link"]
    return f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{depart_date}"


def _fare_details(depart_date, meta):
    if not meta:
        return f"depart {depart_date}"
    parts = [f"depart {depart_date}"]
    if meta.get("return_at"):
        parts.append(f"return {meta['return_at']}")
    if meta.get("airline"):
        parts.append(meta["airline"])
    return ", ".join(parts)


def _maybe_alert(conn, cfg, origin, dest, depart_date, price, median, n, meta=None):
    fingerprint = f"price:{origin}:{dest}:{depart_date}:{int(price)}"
    if db.already_alerted(conn, fingerprint):
        return False
    pct_off = 100 * (1 - price / median)
    msg = (
        f"{origin} → {dest} ({_fare_details(depart_date, meta)})\n"
        f"{price:.0f} {cfg['currency']} — {pct_off:.0f}% below the {median:.0f} {cfg['currency']} median ({n} obs)\n"
        f"{_fare_link(origin, dest, depart_date, meta)}"
    )
    alerts.send("⚡ Anomaly fare", msg)
    db.record_alert(conn, fingerprint, "price", msg)
    return True


def _check_watches(conn, cfg, origin, dest, depart_date, price, meta=None):
    for watch in cfg.get("watches", []):
        if watch["destination"] != dest or price > watch["max_price"]:
            continue
        fingerprint = f"watch:{origin}:{dest}:{depart_date}:{int(price)}"
        if db.already_alerted(conn, fingerprint):
            continue
        msg = (
            f"{origin} → {dest} ({_fare_details(depart_date, meta)})\n"
            f"{price:.0f} {cfg['currency']} — under your {watch['max_price']} {cfg['currency']} target"
            f" ({watch.get('note', '')})\n"
            f"{_fare_link(origin, dest, depart_date, meta)}"
        )
        alerts.send("🎯 Watched route hit", msg)
        db.record_alert(conn, fingerprint, "watch", msg)


def run(conn, cfg):
    client = _make_client(cfg)
    today = dt.date.today()
    dates = _sample_dates(cfg, today)
    budget = cfg["max_requests_per_run"]
    currency = cfg["currency"]
    requests_made = 0
    anomalies = 0
    queried = set()

    for origin, dest in _rotated_routes(cfg, today):
        for depart_date in dates:
            if requests_made >= budget:
                print(f"poll: budget of {budget} requests reached.")
                print(f"poll: done, {anomalies} anomaly alert(s).")
                return
            # month-granularity providers make per-date repeats within a month redundant
            key = (origin, dest, depart_date[:7])
            if key in queried:
                continue
            queried.add(key)
            try:
                observations = client.fares(origin, dest, depart_date, currency)
            except Exception as e:
                print(f"poll error {origin}-{dest} {depart_date}: {e}")
                requests_made += 1
                continue
            requests_made += 1
            if not observations:
                continue
            cheapest = min(p for _, p, _ in observations)
            for obs_date, price, meta in observations:
                is_anomaly, median, n = anomaly.check(conn, cfg, origin, dest, obs_date, price)
                db.record_observation(conn, origin, dest, obs_date, price, currency)
                _check_watches(conn, cfg, origin, dest, obs_date, price, meta)
                if is_anomaly and _maybe_alert(conn, cfg, origin, dest, obs_date, price, median, n, meta):
                    anomalies += 1
            print(f"{origin}-{dest} {depart_date[:7]}: {len(observations)} date(s), cheapest {cheapest:.0f} {currency}")

    print(f"poll: done, {requests_made} requests, {anomalies} anomaly alert(s).")
