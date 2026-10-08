"""A small, deterministic daily backtester for monthly-contribution strategies.

Assumptions (kept deliberately simple and stated in the README):
- A fixed amount is deposited on the first trading day of every month.
- Fractional shares, no fees, no tax, trades fill at the day's close.
- Idle cash earns a cash rate (default: the 13-week T-bill yield).
- Deposits are in the same currency as the price series (no FX effects).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass
class Trade:
    date: date
    side: str  # "BUY" or "SELL"
    price: float
    amount: float  # cash value of the trade
    reason: str


@dataclass
class Portfolio:
    cash: float = 0.0
    units: float = 0.0
    cost_basis: float = 0.0  # cash spent on the units currently held
    contributed: float = 0.0
    trades: list[Trade] = field(default_factory=list)

    def deposit(self, amount: float) -> None:
        self.cash += amount
        self.contributed += amount

    def buy(self, day: date, price: float, amount: float, reason: str) -> None:
        amount = min(amount, self.cash)
        if amount <= 1e-9:
            return
        self.cash -= amount
        self.units += amount / price
        self.cost_basis += amount
        self.trades.append(Trade(day, "BUY", price, amount, reason))

    def sell_all(self, day: date, price: float, reason: str) -> None:
        if self.units <= 1e-12:
            return
        proceeds = self.units * price
        self.cash += proceeds
        self.units = 0.0
        self.cost_basis = 0.0
        self.trades.append(Trade(day, "SELL", price, proceeds, reason))

    def value(self, price: float) -> float:
        return self.cash + self.units * price

    @property
    def avg_cost(self) -> float:
        return self.cost_basis / self.units if self.units > 0 else float("nan")


@dataclass
class Context:
    """What a strategy can see on a given day. No future data is exposed."""

    date: date
    price: float
    all_time_high: float  # highest close up to and including today
    drawdown: float  # fraction below the all-time high (0.10 = 10% below)
    new_high: bool  # today's close set a new all-time high
    deposit: float  # amount deposited today (0 on non-deposit days)


@dataclass
class Result:
    name: str
    equity: pd.DataFrame  # columns: price, value, cash, units, contributed
    trades: list[Trade]
    cashflows: list[tuple[date, float]]  # investor's deposits (-) and final value (+)


def run(prices: pd.Series, strategy, monthly: float = 150.0,
        start: str | None = None, end: str | None = None,
        cash_rate: pd.Series | None = None) -> Result:
    """Run `strategy` over `prices` between `start` and `end`.

    The all-time high is computed over the full price history, so a backtest
    starting in 2010 still knows the 2007 peak, just as a real investor would.
    """
    prices = prices.sort_index()
    ath = prices.cummax()
    prev_ath = ath.shift(1)
    window = prices.loc[start:end]
    if window.empty:
        raise ValueError("No prices in the requested window")

    pf = Portfolio()
    rows = []
    cashflows: list[tuple[date, float]] = []
    prev_day = None
    prev_month = None

    for ts, price in window.items():
        day = ts.date()

        # Interest on idle cash, accrued by calendar days since the last close.
        if cash_rate is not None and prev_day is not None and pf.cash > 0:
            rate = float(cash_rate.get(ts, 0.0))
            pf.cash *= 1 + rate * (day - prev_day).days / 365.0

        deposit = 0.0
        if (day.year, day.month) != prev_month:
            deposit = monthly
            pf.deposit(deposit)
            cashflows.append((day, -deposit))
            prev_month = (day.year, day.month)

        high = float(ath.loc[ts])
        prev_high = prev_ath.loc[ts]
        ctx = Context(
            date=day,
            price=float(price),
            all_time_high=high,
            drawdown=1 - price / high,
            new_high=bool(pd.notna(prev_high) and price > prev_high),
            deposit=deposit,
        )
        strategy.step(ctx, pf)

        rows.append((ts, float(price), pf.value(price), pf.cash, pf.units, pf.contributed))
        prev_day = day

    equity = pd.DataFrame(rows, columns=["date", "price", "value", "cash", "units", "contributed"])
    equity = equity.set_index("date")
    cashflows.append((prev_day, float(equity["value"].iloc[-1])))
    return Result(strategy.name, equity, pf.trades, cashflows)
