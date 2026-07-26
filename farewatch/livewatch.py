"""Live Google Flights checks for watched routes via fast-flights.

Each run checks a rotating slice of (origin, departure date, trip length)
combos for every watch, so back-to-back runs sweep the whole date window a
few times a day while staying polite to Google.
"""

import datetime as dt
import re
import time

from . import alerts, db


def _price_to_float(s):
    m = re.search(r"[\d,]+", s or "")
    return float(m.group().replace(",", "")) if m else None


def _combos(cfg):
    lo, hi = cfg["search_window_days"]
    out = []
    for watch in cfg.get("watches", []):
        for origin in cfg["origins"]:
            for offset in range(lo, hi + 1, 3):
                for length in watch.get("trip_days", [3]):
                    out.append((watch, origin, offset, length))
    return out


def run(conn, cfg):
    try:
        from fast_flights import FlightData, Passengers, create_filter, get_flights_from_filter
    except ImportError:
        raise SystemExit("fast-flights not installed: .venv/bin/pip install fast-flights")

    combos = _combos(cfg)
    if not combos:
        print("live: no watches configured in config.json.")
        return
    budget = cfg.get("live_max_requests", 40)
    today = dt.date.today()
    shift = int(time.time() // 1800) % len(combos)  # new slice every ~30 min
    combos = combos[shift:] + combos[:shift]

    checked = 0
    hits = 0
    for watch, origin, offset, length in combos[:budget]:
        depart = today + dt.timedelta(days=offset)
        ret = depart + dt.timedelta(days=length)
        dest = watch["destination"]
        flight_filter = create_filter(
            flight_data=[
                FlightData(date=depart.isoformat(), from_airport=origin, to_airport=dest),
                FlightData(date=ret.isoformat(), from_airport=dest, to_airport=origin),
            ],
            trip="round-trip",
            seat="economy",
            passengers=Passengers(adults=1),
        )
        try:
            result = get_flights_from_filter(flight_filter)
        except Exception as e:
            err = " ".join(str(e).split())[:120]  # fast-flights dumps whole pages into exceptions
            print(f"live error {origin}-{dest} {depart}: {err}")
            time.sleep(2)
            continue
        priced = [(p, f) for f in result.flights
                  for p in [_price_to_float(f.price)] if p and p > 30]
        checked += 1
        if not priced:
            continue
        cheapest, best = min(priced, key=lambda pf: pf[0])
        db.record_observation(conn, origin, dest, depart.isoformat(), cheapest, cfg["currency"])
        print(f"{origin}-{dest} {depart}+{length}d: {cheapest:.0f} {cfg['currency']} [{result.current_price}]")
        if cheapest <= watch["max_price"]:
            fingerprint = f"live:{origin}:{dest}:{depart}:{int(cheapest)}"
            if not db.already_alerted(conn, fingerprint):
                # tfs param pins the exact round-trip search Google Flights uses internally
                url = f"https://www.google.com/travel/flights?tfs={flight_filter.as_b64().decode()}"
                msg = (
                    f"{origin} → {dest}, {depart} to {ret} ({length} days)\n"
                    f"{cheapest:.0f} {cfg['currency']} round trip — {best.name}, "
                    f"{best.stops} stop(s), departs {best.departure}\n"
                    f"Under your {watch['max_price']} target ({watch.get('note', '')})\n"
                    f"{url}"
                )
                alerts.send("🎯 Live fare hit", msg)
                db.record_alert(conn, fingerprint, "live", msg)
                hits += 1
        time.sleep(1)

    print(f"live: {checked} checked, {hits} hit(s).")
