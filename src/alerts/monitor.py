"""Daily watchlist check: has anything just fallen past an alert threshold?

The check is stateless. An alert fires when a new dip *episode* (as defined in
`backtest.dips`) started on the latest trading day, so the same slide never
alerts twice and nothing needs saving between runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from backtest import dips


@dataclass
class Status:
    ticker: str
    name: str
    date: pd.Timestamp
    price: float
    all_time_high: float
    drawdown: float
    day_change: float


@dataclass
class Alert:
    status: Status
    threshold: float
    history: dict  # Stage 2 stats for this ticker and threshold


def load_watchlist(path: Path) -> list[dict]:
    return json.loads(Path(path).read_text())["stocks"]


def status_of(ticker: str, name: str, prices: pd.Series) -> Status:
    p = prices.dropna()
    high = float(p.max())
    return Status(ticker, name, p.index[-1], float(p.iloc[-1]), high,
                  1 - float(p.iloc[-1]) / high, float(p.iloc[-1] / p.iloc[-2] - 1))


def new_alerts(ticker: str, name: str, prices: pd.Series, thresholds: list[float],
               lookback_bars: int = 1) -> list[Alert]:
    """Alerts for thresholds whose episode started in the last `lookback_bars` days."""
    p = prices.dropna()
    recent = set(p.index[-lookback_bars:])
    status = status_of(ticker, name, p)
    out = []
    for t in sorted(thresholds):
        eps = dips.find_episodes(p, t)
        if eps and eps[-1].start in recent:
            hist = dips.summarise(ticker, p, thresholds=(t,)).iloc[0].to_dict()
            hist["since"] = p.index[0].year
            hist["past_episodes"] = int(hist["episodes"]) - 1  # exclude the one happening now
            out.append(Alert(status, t, hist))
    return out
