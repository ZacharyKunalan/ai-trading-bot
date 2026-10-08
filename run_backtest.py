"""Does buying the dip beat plain monthly investing?

Usage:
    python run_backtest.py                 # SPY, last 20 years + rolling 10-year windows
    python run_backtest.py --ticker QQQ    # any Yahoo Finance ticker
    python run_backtest.py --monthly 150 --years 20 --window 10 --no-cash-interest
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))

from backtest import data  # noqa: E402
from backtest.compare import full_period, rolling_windows  # noqa: E402

RESULTS = Path(__file__).parent / "results"


def fmt_table(table: pd.DataFrame) -> str:
    t = table.copy()
    for c in ("contributed", "final_value", "profit"):
        t[c] = t[c].map(lambda v: f"£{v:,.0f}")
    t["annual_return"] = t["annual_return"].map(lambda v: f"{v:.1%}")
    t["avg_in_cash"] = t["avg_in_cash"].map(lambda v: f"{v:.0%}")
    return t.to_markdown(index=False)


def fmt_rolling(summary: pd.DataFrame) -> str:
    s = summary.copy()
    s["beat_baseline"] = s["beat_baseline"].map(lambda v: f"{v:.0%}")
    for c in ("median_vs_baseline", "worst_vs_baseline", "best_vs_baseline"):
        s[c] = s[c].map(lambda v: f"{v:+.1%}")
    return s.to_markdown(index=False)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ticker", default="SPY")
    p.add_argument("--monthly", type=float, default=150.0)
    p.add_argument("--years", type=int, default=20, help="length of the headline backtest")
    p.add_argument("--window", type=int, default=10, help="length of each rolling window")
    p.add_argument("--no-cash-interest", action="store_true", help="idle cash earns nothing")
    p.add_argument("--refresh", action="store_true", help="re-download price data")
    p.add_argument("--no-chart", action="store_true")
    args = p.parse_args()

    prices = data.load_prices(args.ticker, refresh=args.refresh)
    cash_rate = None if args.no_cash_interest else data.load_cash_rate(prices.index, args.refresh)
    RESULTS.mkdir(exist_ok=True)

    results, table = full_period(prices, cash_rate, args.monthly, args.years)
    start, end = results[0].equity.index[0], results[0].equity.index[-1]
    print(f"\n{args.ticker}, £{args.monthly:.0f}/month, {start} to {end}\n")
    print(fmt_table(table))
    table.to_csv(RESULTS / "full_period.csv", index=False)

    df, summary = rolling_windows(prices, cash_rate, args.monthly, args.window)
    n = df["start"].nunique()
    print(f"\nRolling {args.window}-year windows ({n} start dates, every 3 months):\n")
    print(fmt_rolling(summary))
    df.to_csv(RESULTS / "rolling_windows.csv", index=False)
    summary.to_csv(RESULTS / "rolling_summary.csv", index=False)

    if not args.no_chart:
        from backtest.charts import plot_results
        out = plot_results(results, df, args.ticker, args.window, RESULTS / "backtest.png")
        print(f"\nChart saved to {out}")


if __name__ == "__main__":
    main()
