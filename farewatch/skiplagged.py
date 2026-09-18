"""Skiplagged one-way search — surfaces hidden-city fares Google won't show.

Hidden-city tickets are one-way, carry-on-only in practice, and you exit at
the layover. Prices here are never mixed into the published-fare baseline.
"""

import json
import time

API = "https://skiplagged.com/api/search.php"


class SkiplaggedClient:
    def __init__(self):
        from primp import Client
        self.client = Client(impersonate="chrome_131", timeout=30)

    def cheapest_oneway(self, origin, dest, depart_date, nonstop=False):
        """Cheapest one-way for the date: dict(price, hidden, final, stops) or None.

        With nonstop=True only single-segment itineraries count — which also
        rules out hidden-city fares, since those need a layover to exit at.
        """
        url = f"{API}?from={origin}&to={dest}&depart={depart_date}&format=v3"
        resp = self.client.get(url)
        if resp.status_code != 200:
            raise RuntimeError(f"skiplagged HTTP {resp.status_code}")
        payload = json.loads(resp.text)
        flights = payload.get("flights", {})
        best = None
        for itin in payload.get("itineraries", {}).get("outbound", []):
            cents = itin.get("one_way_price")
            segments = flights.get(itin.get("flight"), {}).get("segments", [])
            if not cents or not segments:
                continue
            if nonstop and len(segments) != 1:
                continue
            final = segments[-1]["arrival"]["airport"]
            candidate = {
                "price": cents / 100.0,
                "hidden": final != dest,
                "final": final,
                "stops": len(segments) - 1,
            }
            if best is None or candidate["price"] < best["price"]:
                best = candidate
        return best


def run(conn, cfg):
    from . import alerts, db
    from .livewatch import _combos, _select
    import datetime as dt

    combos = _combos(cfg)
    if not combos:
        print("hidden: no watches configured.")
        return
    budget = cfg.get("hidden_max_requests", 5)
    today = dt.date.today()
    shift = int(time.time() // 3600) % len(combos)  # new slice each hour

    client = SkiplaggedClient()
    checked = 0
    hits = 0
    for watch, origin, dest, offset, length in _select(combos, budget, shift):
        depart = today + dt.timedelta(days=offset)
        ret = depart + dt.timedelta(days=length)
        nonstop = bool(watch.get("nonstop"))
        try:
            out = client.cheapest_oneway(origin, dest, depart.isoformat(), nonstop)
            time.sleep(3)
            back = client.cheapest_oneway(dest, origin, ret.isoformat(), nonstop)
        except Exception as e:
            print(f"hidden error {origin}-{dest} {depart}: {str(e)[:120]}")
            time.sleep(5)
            continue
        checked += 1
        if not out or not back:
            continue
        total = out["price"] + back["price"]
        tags = []
        if out["hidden"]:
            tags.append(f"out hidden-city (ticketed to {out['final']})")
        if back["hidden"]:
            tags.append(f"return hidden-city (ticketed to {back['final']})")
        if nonstop:
            tags.append("nonstop")
        tag = "; ".join(tags) if tags else "normal fares"
        print(f"{origin}-{dest} {depart}+{length}d: {out['price']:.0f}+{back['price']:.0f} = {total:.0f} USD [{tag}]")
        if total <= watch["max_price"]:
            fingerprint = f"hidden:{origin}:{dest}:{depart}:{int(total)}"
            if not db.already_alerted(conn, fingerprint):
                msg = (
                    f"{origin} → {dest}, {depart} to {ret} — two one-ways totaling {total:.0f} USD\n"
                    f"Out {out['price']:.0f} / back {back['price']:.0f} ({tag})\n"
                    f"Hidden-city rules: book each leg separately on Skiplagged, carry-on only, "
                    f"exit at your stop.\n"
                    f"https://skiplagged.com/flights/{origin}/{dest}/{depart}\n"
                    f"https://skiplagged.com/flights/{dest}/{origin}/{ret}"
                )
                alerts.send("🕳️ Hidden-city pair", msg)
                db.record_alert(conn, fingerprint, "hidden", msg)
                hits += 1
        time.sleep(3)

    print(f"hidden: {checked} checked, {hits} hit(s).")
