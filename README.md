# farewatch

Personal anomaly-fare watcher for NYC airports (JFK / EWR / LGA). Three detectors:

1. **Price poller** — samples fares on a 96-route watchlist via the Travelpayouts (Aviasales) cached-prices API, stores every observation in SQLite, and alerts when a fare drops below **45% of the rolling median** for that route + departure month. One call returns cached fares for a whole route-month, so the baseline builds fast.
2. **Live watcher** — checks Google Flights prices directly (via `fast-flights`) for `watches` routes every 30 minutes, rotating through departure dates and trip lengths so the whole window gets swept several times a day. Alerts the moment a round trip crosses the watch's `max_price`. This is the "catch the mistake fare while it's alive" tier.
3. **Hidden-city watcher** — checks Skiplagged hourly for `watches` routes, pricing the trip as two one-ways (hidden-city fares Google never shows). Alerts when the pair total crosses `max_price`. Hidden-city caveats apply: carry-on only, book legs separately, exit at your stop, don't make it a habit on one airline. These prices are never mixed into the published-fare baseline.
4. **Feed monitor** — scans The Flight Deal (NYC category), Fly4free, and r/flightdeals for NYC-keyword deals. Works on day one, while the price baseline is still warming up.

## Setup

```bash
cd ~/Projects/farewatch
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Get a free API token: sign up at [travelpayouts.com](https://www.travelpayouts.com) (it's Aviasales' affiliate network — the flight-data API is free to use), then **Profile → API token**. Create `.env`:

```
TRAVELPAYOUTS_TOKEN=your_token

# optional — Telegram push alerts (falls back to macOS notifications without these)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

> **Data caveat:** Travelpayouts serves *cached* prices from recent Aviasales searches — popular routes (which NYC routes are) refresh constantly, but a hit needs verification before booking. That's fine: the alert links straight to Google Flights to confirm.
>
> **Alternative provider:** the code also supports the Amadeus Self-Service API (`AMADEUS_CLIENT_ID`/`AMADEUS_CLIENT_SECRET`/`AMADEUS_ENV` in `.env`, used only when `TRAVELPAYOUTS_TOKEN` is absent) — but as of mid-2026 their portal has no working self-service signup, so Travelpayouts is the default.

## Usage

```bash
.venv/bin/python -m farewatch.cli test-alert   # verify notifications
.venv/bin/python -m farewatch.cli feeds        # scan deal feeds now
.venv/bin/python -m farewatch.cli poll         # poll prices, build baseline, alert on anomalies
.venv/bin/python -m farewatch.cli report       # baseline coverage + recent alerts
```

## Scheduling (launchd)

Four LaunchAgents in `~/Library/LaunchAgents` keep it running (launchd, not cron, so macOS notifications work): `com.farewatch.live` (every 30 min), `com.farewatch.feeds` (every 20 min), `com.farewatch.hidden` (hourly), `com.farewatch.poll` (every 6 h). Logs land in `logs/`.

```bash
launchctl list | grep farewatch                                   # status
launchctl bootout gui/$(id -u)/com.farewatch.live                  # stop one
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.farewatch.live.plist  # start again
```

Alerts arrive as macOS Notification Center banners (with sound); add `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` to `.env` if you ever want phone push too.

## Tuning (`config.json`)

- `destinations` — add/remove airports you'd actually fly to.
- `one_way` (false) — fares are round-trip totals by default; set true for one-way pricing. Changing it mid-stream poisons the baseline — wipe the `observations` table if you flip it.
- `watches` — absolute price targets that alert regardless of the statistical baseline, e.g. `{"destination": "SEA", "max_price": 250}`. For "I want to go to X and I'm waiting for a deal" routes.
- `max_requests_per_run` (60) × 4 runs/day ≈ 7,200 calls/month. Routes rotate daily so the whole watchlist gets covered even under the budget. Lower it if you want to stay inside the free quota.
- `dates_per_route` (2) — departure dates sampled per route per run, drawn from `search_window_days` (21–120 days out).
- `anomaly.ratio_threshold` (0.45) — alert when price ≤ 45% of median. Raise to ~0.55 to also catch strong sales; lower to ~0.35 for near-certain mistake fares only.
- `anomaly.min_observations` (8) — a route-month needs this many data points before it can alert. Expect **2–3 weeks of warm-up** before price alerts start firing; the feed monitor covers you meanwhile.

## When an alert fires

1. Book **directly with the airline**, immediately. OTAs cancel mistake fares faster.
2. Don't book hotels or anything non-refundable for ~72 hours — airlines may cancel a true error fare (they must refund you, but the ticket can die).
3. Don't call the airline to ask about the fare. Just book it.
