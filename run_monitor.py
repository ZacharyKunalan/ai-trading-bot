"""Stage 3: check the watchlist and email an alert when a dip threshold is crossed.

Usage:
    python run_monitor.py --dry-run          # print the result, write results/alert_preview.html
    python run_monitor.py                    # send an email only if there's a new alert
    python run_monitor.py --always           # send a status email even with no alerts (to test setup)
    python run_monitor.py --dry-run --simulate MSFT:0.20   # preview what an alert looks like
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from alerts import emailer, monitor  # noqa: E402
from backtest import data, dips  # noqa: E402

ROOT = Path(__file__).parent


def load_env(path: Path) -> None:
    """Minimal .env loader so local runs work without extra packages."""
    import os
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--watchlist", default=str(ROOT / "watchlist.json"))
    p.add_argument("--dry-run", action="store_true", help="don't send, just print and save a preview")
    p.add_argument("--always", action="store_true", help="send a status email even with no alerts")
    p.add_argument("--lookback", type=int, default=1, help="trading days to look back for new crossings")
    p.add_argument("--simulate", metavar="TICKER:DIP", help="fake an alert to preview the email")
    args = p.parse_args()
    load_env(ROOT / ".env")

    alerts, statuses = [], []
    for item in monitor.load_watchlist(Path(args.watchlist)):
        prices = data.load_prices(item["ticker"], refresh=True)
        statuses.append(monitor.status_of(item["ticker"], item["name"], prices))
        alerts += monitor.new_alerts(item["ticker"], item["name"], prices, item["thresholds"], args.lookback)

    if args.simulate:
        ticker, dip = args.simulate.split(":")
        st = next(s for s in statuses if s.ticker == ticker)
        prices = data.load_prices(ticker)
        hist = dips.summarise(ticker, prices, thresholds=(float(dip),)).iloc[0].to_dict()
        hist.update(since=prices.index[0].year, past_episodes=int(hist["episodes"]))
        fake = monitor.Status(st.ticker, st.name, st.date, st.all_time_high * (1 - float(dip)),
                              st.all_time_high, float(dip), -0.034)
        alerts.insert(0, monitor.Alert(fake, float(dip), hist))

    for s in statuses:
        print(f"{s.ticker:7s} {s.date.date()}  {emailer.money(s.ticker, s.price):>11s}  "
              f"{s.drawdown:6.1%} below high  {s.day_change:+.1%} today")
    print(f"\n{len(alerts)} new alert(s)")
    for a in alerts:
        print(f"  - {a.status.ticker} crossed {a.threshold:.0%} below its high")

    subj, plain, html = emailer.build(alerts, statuses)
    if args.simulate:
        subj = "[SIMULATED] " + subj
    if args.dry_run:
        out = ROOT / "results" / "alert_preview.html"
        out.parent.mkdir(exist_ok=True)
        out.write_text(html)
        print(f"\nSubject: {subj}\nPreview saved to {out}")
        return
    if alerts or args.always:
        to = emailer.send(subj, plain, html)
        print(f"\nEmail sent to {to}")
    else:
        print("\nNothing to send.")


if __name__ == "__main__":
    main()
