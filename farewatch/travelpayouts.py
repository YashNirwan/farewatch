"""Travelpayouts (Aviasales) cached-prices client.

One call per route+month returns cheapest cached fares for many departure
dates, which builds the baseline much faster than per-date lookups.
"""

import os

import requests

API_URL = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


class TravelpayoutsClient:
    def __init__(self, one_way=True):
        self.token = os.environ.get("TRAVELPAYOUTS_TOKEN")
        self.one_way = one_way
        if not self.token:
            raise SystemExit(
                "Set TRAVELPAYOUTS_TOKEN (in .env or the environment).\n"
                "Free token: https://www.travelpayouts.com — Profile → API token."
            )

    def fares(self, origin, dest, depart_date, currency="USD"):
        """Return [(depart_date, price, meta), ...] for the month containing depart_date."""
        resp = requests.get(
            API_URL,
            params={
                "origin": origin,
                "destination": dest,
                "departure_at": depart_date[:7],
                "one_way": "true" if self.one_way else "false",
                "unique": "false",
                "sorting": "price",
                "limit": 100,
                "currency": currency.lower(),
                "token": self.token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success", False):
            raise RuntimeError(f"travelpayouts error: {payload}")
        best = {}
        for entry in payload.get("data", []):
            date = (entry.get("departure_at") or "")[:10]
            price = entry.get("price")
            if not date or price is None:
                continue
            if date not in best or price < best[date][0]:
                best[date] = (
                    float(price),
                    {
                        "return_at": (entry.get("return_at") or "")[:10],
                        "airline": entry.get("airline"),
                        "link": entry.get("link"),
                    },
                )
        return [(date, price, meta) for date, (price, meta) in sorted(best.items())]
