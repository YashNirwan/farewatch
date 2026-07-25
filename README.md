# farewatch

A flight-price anomaly detector that polls multiple travel data sources, builds a statistical baseline per route, and alerts when a fare drops far enough below it to be worth booking — including fares that never surface on mainstream aggregators.

Built because error/mistake fares and deep fare-war pricing live for a few hours before airlines correct them; catching them requires polling continuously and comparing against a route's normal price range, not just eyeballing Google Flights once a day.

## Architecture

Four independent watchers, each hitting a different data source, coordinated through a shared SQLite store (`observations`, `alerts`):

| Watcher | Source | Cadence | Trigger |
|---|---|---|---|
| **Baseline poller** | Travelpayouts (Aviasales cached-prices API) | every 6 h | price ≤ `ratio_threshold` × rolling median for that route + month |
| **Live watcher** | Google Flights (via `fast-flights`) | every 30 min | price ≤ an absolute target for a specific watched route |
| **Hidden-city watcher** | Skiplagged | hourly | same target, priced as two independent one-way tickets |
| **Feed monitor** | RSS from deal-tracking sites (The Flight Deal, Fly4free, r/flightdeals) | every 20 min | keyword match on tracked airports |

The baseline poller builds statistical context across a wide multi-route watchlist (one call returns cached fares for an entire route-month, so the baseline fills in fast). The live and hidden-city watchers apply the same idea to specific routes a user cares about right now, checked against real-time data instead of a cache — this is what catches a fare while it's still bookable rather than after a deal site has already posted it. Providers are swappable behind a common `fares(origin, dest, date) -> [(date, price)]` interface (`travelpayouts.py`, `amadeus.py`), so adding a new price source doesn't touch the scheduling or alerting logic.

Alerts are deduplicated via a fingerprint (route + date + price bucket) stored in `alerts`, and delivered through a fallback chain: Telegram (if configured) → `terminal-notifier` → AppleScript notification, so clicking an alert opens the relevant booking page directly.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Get a free API token at [travelpayouts.com](https://www.travelpayouts.com) (Profile → API token) and create `.env`:

```
TRAVELPAYOUTS_TOKEN=your_token

# optional — Telegram push (falls back to a local OS notification without these)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

> Travelpayouts serves *cached* prices from recent searches, which is why the baseline poller pairs with the live watcher for routes worth checking in real time. The code also supports the Amadeus Self-Service API as an alternate provider (`AMADEUS_CLIENT_ID`/`AMADEUS_CLIENT_SECRET`) behind the same interface.

## Usage

```bash
.venv/bin/python -m farewatch.cli poll     # poll baseline prices, alert on anomalies
.venv/bin/python -m farewatch.cli live     # live-check watched routes via Google Flights
.venv/bin/python -m farewatch.cli hidden   # check watched routes via Skiplagged
.venv/bin/python -m farewatch.cli feeds    # scan deal feeds
.venv/bin/python -m farewatch.cli report   # baseline coverage + recent alerts
.venv/bin/python -m farewatch.cli alerts   # full alert history
```

## Testing

```bash
.venv/bin/pip install pytest
.venv/bin/pytest tests/ -v
```

Unit tests cover the anomaly-detection thresholds (`test_anomaly.py`), storage/dedup logic (`test_db.py`), deterministic date/route sampling (`test_poller.py`), and the RSS/Atom feed parser (`test_feeds.py`) — the pure-function core of the system, independent of any live network calls.

## Scheduling

Runs as four `launchd` LaunchAgents (macOS) so scheduled jobs can still trigger OS notifications, which cron cannot. Config lives in `~/Library/LaunchAgents/com.farewatch.*.plist`; see `launchctl list | grep farewatch` for status.

## Configuration (`config.json`)

- `origins` / `destinations` — the route watchlist for the baseline poller.
- `watches` — routes checked live against an absolute price target, independent of the statistical baseline, e.g. `{"destination": "SEA", "max_price": 250, "trip_days": [3, 7, 14]}`.
- `anomaly.ratio_threshold` — alert when price ≤ this fraction of the route's rolling median (e.g. `0.6` alerts at 40%+ off).
- `anomaly.min_observations` — a route-month needs this many samples before it can alert; the feed monitor covers the warm-up gap.
- `one_way` — round-trip totals by default; changing it mid-stream requires clearing `observations` since the baseline isn't comparable across modes.

## Notes on hidden-city fares

The Skiplagged watcher surfaces hidden-city itineraries (booking through a layover city and not flying the final leg), which are legal for the traveler but against most airlines' contracts of carriage. It's included here as one more data source in the price-comparison model, not a recommendation to rely on it — the usual caveats apply (carry-on only, book each direction separately, don't do it repeatedly on one airline/frequent-flyer account).
