"""Strategy comparisons: one long backtest, and many rolling windows."""

from __future__ import annotations

import pandas as pd

from . import engine, metrics, strategies


def full_period(prices, cash_rate, monthly, years):
    start = prices.index[-1] - pd.DateOffset(years=years)
    results = [engine.run(prices, s, monthly, start=str(start.date()), cash_rate=cash_rate)
               for s in strategies.default_strategies()]
    table = pd.DataFrame([metrics.summarise(r) for r in results])
    return results, table


def rolling_windows(prices, cash_rate, monthly, window_years, step_months=3):
    """Run every strategy over many overlapping windows with different start
    dates, so the conclusion doesn't hinge on one lucky or unlucky start."""
    first = prices.index[0] + pd.DateOffset(months=1)
    last_start = prices.index[-1] - pd.DateOffset(years=window_years)
    starts = pd.date_range(first, last_start, freq=f"{step_months}MS")
    rows = []
    for st in starts:
        en = st + pd.DateOffset(years=window_years) - pd.DateOffset(days=1)
        for s in strategies.default_strategies():
            r = engine.run(prices, s, monthly, start=str(st.date()), end=str(en.date()),
                           cash_rate=cash_rate)
            rows.append({"start": st.date(), "strategy": r.name,
                         "final_value": r.equity["value"].iloc[-1]})
    df = pd.DataFrame(rows)
    base = df[df.strategy == strategies.MonthlyDCA().name].set_index("start")["final_value"]
    df["vs_baseline"] = df["final_value"] / df["start"].map(base) - 1
    summary = (df.groupby("strategy", sort=False)["vs_baseline"]
                 .agg(beat_baseline=lambda x: (x > 1e-9).mean(),
                      median_vs_baseline="median",
                      worst_vs_baseline="min",
                      best_vs_baseline="max")
                 .reset_index())
    return df, summary
