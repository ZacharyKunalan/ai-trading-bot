"""What happens after a stock falls X% below its all-time high?

An *episode* starts on the first day the price closes at least `threshold`
below its all-time high. A new episode can only start after the price has set
a fresh all-time high, so one long slide counts once, not every day.

For each episode we look at what an alert on that day would have led to:
the return 3/6/12 months later, how much further it fell first, and whether
(and how fast) it got back to its old high.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = {"3m": 63, "6m": 126, "12m": 252}


@dataclass
class Episode:
    start: pd.Timestamp
    entry: float
    prior_high: float
    ret_3m: float
    ret_6m: float
    ret_12m: float
    further_drop_12m: float  # worst close in the next 12 months vs entry (negative = fell more)
    years_to_recover: float  # NaN if it never got back to the prior high
    years_waited: float  # years to recover, or years since the dip if still waiting


def find_episodes(prices: pd.Series, threshold: float) -> list[Episode]:
    p = prices.dropna().to_numpy(dtype=float)
    idx = prices.dropna().index
    n = len(p)
    episodes: list[Episode] = []
    high = p[0]
    armed = True
    for i in range(n):
        if p[i] > high:
            high = p[i]
            armed = True
            continue
        if armed and p[i] <= high * (1 - threshold):
            armed = False
            entry = p[i]

            def fwd(h: int) -> float:
                return p[i + h] / entry - 1 if i + h < n else np.nan

            year = p[i : i + TRADING_DAYS["12m"] + 1]
            further = year.min() / entry - 1 if i + TRADING_DAYS["12m"] < n else np.nan
            later = np.nonzero(p[i:] >= high)[0]
            years = (idx[i + later[0]] - idx[i]).days / 365.25 if len(later) else np.nan
            waited = years if len(later) else (idx[-1] - idx[i]).days / 365.25
            episodes.append(Episode(idx[i], entry, high, fwd(63), fwd(126), fwd(252), further,
                                    years, waited))
    return episodes


def baseline_12m(prices: pd.Series) -> dict:
    """12-month forward returns from *every* day, for comparison."""
    p = prices.dropna()
    fwd = (p.shift(-TRADING_DAYS["12m"]) / p - 1).dropna()
    return {"median_12m": float(fwd.median()), "pct_up_12m": float((fwd > 0).mean())}


def summarise(ticker: str, prices: pd.Series, thresholds=(0.10, 0.20, 0.30)) -> pd.DataFrame:
    base = baseline_12m(prices)
    rows = []
    for t in thresholds:
        eps = find_episodes(prices, t)
        df = pd.DataFrame([e.__dict__ for e in eps])
        complete = df.dropna(subset=["ret_12m"]) if len(df) else df
        rows.append({
            "ticker": ticker,
            "dip": t,
            "episodes": len(df),
            "median_12m_after": complete["ret_12m"].median() if len(complete) else np.nan,
            "pct_up_12m_after": (complete["ret_12m"] > 0).mean() if len(complete) else np.nan,
            "pct_fell_10pct_more": (complete["further_drop_12m"] <= -0.10).mean() if len(complete) else np.nan,
            "median_further_drop": complete["further_drop_12m"].median() if len(complete) else np.nan,
            "pct_recovered_within_1y": (df["years_to_recover"] <= 1).mean() if len(df) else np.nan,
            "never_recovered": int(df["years_to_recover"].isna().sum()) if len(df) else 0,
            "longest_wait_years": df["years_waited"].max() if len(df) else np.nan,
            "longest_wait_ongoing": bool(len(df) and df.loc[df["years_waited"].idxmax(), "years_to_recover"] != df["years_waited"].max()),
            "baseline_median_12m": base["median_12m"],
            "baseline_pct_up_12m": base["pct_up_12m"],
        })
    return pd.DataFrame(rows)


def episode_table(ticker: str, prices: pd.Series, threshold: float) -> pd.DataFrame:
    df = pd.DataFrame([e.__dict__ for e in find_episodes(prices, threshold)])
    if len(df):
        df.insert(0, "ticker", ticker)
    return df
