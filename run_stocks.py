"""Stage 2: does dip-buying work on individual stocks?

Two questions, for each ticker:
1. Strategy test: the same strategies as Stage 1, over rolling windows.
2. Dip episodes: every time the stock fell 10/20/30% below its high, what
   happened next? Did it bounce, or keep falling?

The watchlist is made of companies we already know became huge winners, which
flatters any "buy the dip" rule (survivorship bias). The control group is
former market leaders whose dips did not all recover quickly, as a check.

Usage:
    python run_stocks.py
    python run_stocks.py --watchlist MSFT AAPL --control INTC --window 5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent / "src"))

from backtest import data, dips  # noqa: E402
from backtest.compare import rolling_windows  # noqa: E402

OUT = Path(__file__).parent / "results" / "stocks"
WATCHLIST = ["MSFT", "AAPL", "NVDA", "AMZN", "VUAG.L"]
CONTROL = ["CSCO", "INTC", "BA", "PYPL"]
FOCUS = ["Buy only on 10% dips", "Sell at highs, rebuy on 5% dips", "Invest 67% monthly, rest on 10% dips"]


def pct(v, signed=False):
    if pd.isna(v):
        return "–"
    return f"{v:+.1%}" if signed else f"{v:.0%}"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--watchlist", nargs="+", default=WATCHLIST)
    p.add_argument("--control", nargs="+", default=CONTROL)
    p.add_argument("--monthly", type=float, default=150.0)
    p.add_argument("--window", type=int, default=5, help="rolling window length in years")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--no-chart", action="store_true")
    args = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    groups = {t: "watchlist" for t in args.watchlist} | {t: "control" for t in args.control}
    strat_rows, dip_rows, episode_rows = [], [], []

    for ticker, group in groups.items():
        prices = data.load_prices(ticker, refresh=args.refresh)
        cash = data.load_cash_rate(prices.index, args.refresh)
        years = (prices.index[-1] - prices.index[0]).days / 365.25
        print(f"{ticker:7s} {group:9s} {prices.index[0].date()} to {prices.index[-1].date()} ({years:.0f} years)")

        _, summary = rolling_windows(prices, cash, args.monthly, args.window)
        summary.insert(0, "ticker", ticker)
        summary.insert(1, "group", group)
        summary["windows"] = len(pd.date_range(prices.index[0] + pd.DateOffset(months=1),
                                               prices.index[-1] - pd.DateOffset(years=args.window),
                                               freq="3MS"))
        strat_rows.append(summary)

        d = dips.summarise(ticker, prices)
        d.insert(1, "group", group)
        dip_rows.append(d)
        episode_rows.append(dips.episode_table(ticker, prices, 0.20))

    strat = pd.concat(strat_rows, ignore_index=True)
    dip = pd.concat(dip_rows, ignore_index=True)
    episodes = pd.concat(episode_rows, ignore_index=True)
    strat.to_csv(OUT / "strategy_summary.csv", index=False)
    dip.to_csv(OUT / "dip_summary.csv", index=False)
    episodes.to_csv(OUT / "episodes_20pct.csv", index=False)

    # Strategy table: median result vs plain monthly investing, per ticker.
    focus = strat[strat.strategy.isin(FOCUS)]
    wide = focus.pivot(index="ticker", columns="strategy", values="median_vs_baseline")[FOCUS]
    beat = focus.pivot(index="ticker", columns="strategy", values="beat_baseline")[FOCUS]
    order = list(groups)
    lines = [f"Median ending value vs plain monthly investing, rolling {args.window}-year windows "
             f"(% of windows where it won in brackets)\n",
             "| Ticker | Group | Windows | " + " | ".join(FOCUS) + " |",
             "|:--|:--|--:|" + "--:|" * len(FOCUS)]
    for t in order:
        n = int(strat.loc[strat.ticker == t, "windows"].iloc[0])
        cells = [f"{pct(wide.loc[t, s], True)} ({pct(beat.loc[t, s])})" for s in FOCUS]
        lines.append(f"| {t} | {groups[t]} | {n} | " + " | ".join(cells) + " |")
    strat_md = "\n".join(lines)

    # Dip table at 20%.
    d20 = dip[dip.dip == 0.20].set_index("ticker").loc[order]
    lines = ["Every time the stock fell 20% below its all-time high\n",
             "| Ticker | Group | Times | Up 12m later | Median 12m return | Typical 12m from any day | "
             "Fell another 10%+ within 12m | Back at old high within 1y | Still below old high | Longest wait for old high |",
             "|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for t, r in d20.iterrows():
        longest = "–" if pd.isna(r.longest_wait_years) else f"{r.longest_wait_years:.1f} yrs"
        if r.longest_wait_ongoing:
            longest += " (still waiting)"
        lines.append(
            f"| {t} | {r.group} | {r.episodes} | {pct(r.pct_up_12m_after)} | {r.median_12m_after:+.0%} | "
            f"{r.baseline_median_12m:+.0%} | {pct(r.pct_fell_10pct_more)} | {pct(r.pct_recovered_within_1y)} | "
            f"{r.never_recovered} | {longest} |")
    dip_md = "\n".join(lines)

    report = f"# Stage 2 results\n\n## Strategies\n\n{strat_md}\n\n## Dips\n\n{dip_md}\n"
    (OUT / "report.md").write_text(report)
    print("\n" + report)

    if not args.no_chart:
        from backtest.charts import plot_stocks
        out = plot_stocks(strat, dip, groups, args.window, OUT / "stocks.png")
        print(f"Chart saved to {out}")


if __name__ == "__main__":
    main()
