"""Thin Amadeus Self-Service API client (Flight Offers Search)."""

import os
import time

import requests

_HOSTS = {
    "test": "https://test.api.amadeus.com",
    "production": "https://api.amadeus.com",
}


class AmadeusClient:
    def __init__(self):
        self.client_id = os.environ.get("AMADEUS_CLIENT_ID")
        self.client_secret = os.environ.get("AMADEUS_CLIENT_SECRET")
        if not self.client_id or not self.client_secret:
            raise SystemExit(
                "Set AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET (in .env or the environment).\n"
                "Free keys: https://developers.amadeus.com"
            )
        self.host = _HOSTS[os.environ.get("AMADEUS_ENV", "test")]
        self._token = None
        self._token_expiry = 0

    def _access_token(self):
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        resp = requests.post(
            f"{self.host}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expiry = time.time() + payload.get("expires_in", 1800)
        return self._token

    def cheapest_fare(self, origin, dest, depart_date, currency="USD"):
        """Return the cheapest round-trip-less (one-way) grand total for a date, or None."""
        resp = requests.get(
            f"{self.host}/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {self._access_token()}"},
            params={
                "originLocationCode": origin,
                "destinationLocationCode": dest,
                "departureDate": depart_date,
                "adults": 1,
                "currencyCode": currency,
                "max": 5,
            },
            timeout=60,
        )
        if resp.status_code == 429:
            time.sleep(2)
            return self.cheapest_fare(origin, dest, depart_date, currency)
        resp.raise_for_status()
        offers = resp.json().get("data", [])
        if not offers:
            return None
        return min(float(o["price"]["grandTotal"]) for o in offers)

    def fares(self, origin, dest, depart_date, currency="USD"):
        """Provider interface: [(depart_date, price), ...] (single date for Amadeus)."""
        price = self.cheapest_fare(origin, dest, depart_date, currency)
        return [(depart_date, price)] if price is not None else []
