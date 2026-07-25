"""farewatch CLI: poll prices, scan deal feeds, report baseline status."""

import argparse
import statistics

from . import alerts, config, db, feeds, livewatch, poller


def cmd_report(conn, cfg):
    rows = conn.execute(
        """SELECT origin, dest, substr(depart_date, 1, 7) AS month,
                  COUNT(*) AS n, MIN(price) AS lo, MAX(price) AS hi
           FROM observations GROUP BY origin, dest, month
           ORDER BY origin, dest, month"""
    ).fetchall()
    if not rows:
        print("No observations yet — run `poll` a few times to build the baseline.")
        return
    min_obs = cfg["anomaly"]["min_observations"]
    ready = 0
    for r in rows:
        prices = db.route_prices(conn, r["origin"], r["dest"], r["month"])
        med = statistics.median(prices)
        status = "ready" if r["n"] >= min_obs else f"warming ({r['n']}/{min_obs})"
        if r["n"] >= min_obs:
            ready += 1
        print(f"{r['origin']}-{r['dest']} {r['month']}: n={r['n']} median={med:.0f} "
              f"range={r['lo']:.0f}-{r['hi']:.0f} [{status}]")
    print(f"\n{ready}/{len(rows)} route-months have enough data to fire alerts.")

    recent = conn.execute(
        "SELECT sent_at, kind, message FROM alerts ORDER BY sent_at DESC LIMIT 5"
    ).fetchall()
    if recent:
        print("\nRecent alerts:")
        for a in recent:
            first_line = a["message"].splitlines()[0]
            print(f"  {a['sent_at']} [{a['kind']}] {first_line}")


def main():
    parser = argparse.ArgumentParser(prog="farewatch", description="NYC anomaly-fare watcher")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("poll", help="poll cached prices and alert on anomalies")
    sub.add_parser("live", help="live Google Flights check of watched routes")
    sub.add_parser("hidden", help="Skiplagged hidden-city check of watched routes")
    sub.add_parser("feeds", help="scan deal-site feeds for NYC fares")
    sub.add_parser("report", help="show baseline coverage and recent alerts")
    alerts_p = sub.add_parser("alerts", help="show recent alerts with full details")
    alerts_p.add_argument("-n", type=int, default=10, help="how many to show")
    sub.add_parser("test-alert", help="send a test alert to verify Telegram/notifications")
    args = parser.parse_args()

    cfg = config.load()
    conn = db.connect()
    if args.command == "poll":
        poller.run(conn, cfg)
    elif args.command == "live":
        livewatch.run(conn, cfg)
    elif args.command == "hidden":
        from . import skiplagged
        skiplagged.run(conn, cfg)
    elif args.command == "feeds":
        feeds.run(conn, cfg)
    elif args.command == "report":
        cmd_report(conn, cfg)
    elif args.command == "alerts":
        rows = conn.execute(
            "SELECT sent_at, kind, message FROM alerts ORDER BY sent_at DESC LIMIT ?", (args.n,)
        ).fetchall()
        if not rows:
            print("No alerts yet.")
        for r in rows:
            print(f"--- {r['sent_at']} UTC [{r['kind']}]\n{r['message']}\n")
    elif args.command == "test-alert":
        alerts.send("farewatch test", "If you can read this, alerts are working.")


if __name__ == "__main__":
    main()
