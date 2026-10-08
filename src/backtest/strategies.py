"""Strategies to compare. Each has a `name` and a `step(ctx, portfolio)` method.

The engine deposits the monthly amount into cash before `step` is called, so
a strategy only decides what to do with the cash and units it holds.
"""

from __future__ import annotations

from .engine import Context, Portfolio


class MonthlyDCA:
    """Invest every deposit straight away. The baseline."""

    def __init__(self) -> None:
        self.name = "Monthly investing (baseline)"

    def step(self, ctx: Context, pf: Portfolio) -> None:
        if ctx.deposit:
            pf.buy(ctx.date, ctx.price, pf.cash, "monthly deposit")


class DipBuyer:
    """Save deposits as cash; invest it all only when the index is at least
    `dip` below its all-time high. Never sells."""

    def __init__(self, dip: float) -> None:
        self.dip = dip
        self.name = f"Buy only on {dip:.0%} dips"

    def step(self, ctx: Context, pf: Portfolio) -> None:
        if ctx.drawdown >= self.dip and pf.cash > 0:
            pf.buy(ctx.date, ctx.price, pf.cash, f"{ctx.drawdown:.1%} below high")


class SellHighBuyDip(DipBuyer):
    """The current plan: sell everything when the index hits a new all-time
    high (and the position is up at least `min_gain`), then hold cash until
    it falls `dip` below the high, and buy back in."""

    def __init__(self, dip: float, min_gain: float = 0.03) -> None:
        super().__init__(dip)
        self.min_gain = min_gain
        self.name = f"Sell at highs, rebuy on {dip:.0%} dips"

    def step(self, ctx: Context, pf: Portfolio) -> None:
        if pf.units > 0 and ctx.new_high and ctx.price >= pf.avg_cost * (1 + self.min_gain):
            pf.sell_all(ctx.date, ctx.price, "new all-time high")
            return
        super().step(ctx, pf)


class DCAWithDipReserve:
    """Invest `core` of each deposit straight away and keep the rest as a
    reserve that is only spent when the index is `dip` below its high."""

    def __init__(self, core: float = 2 / 3, dip: float = 0.10) -> None:
        self.core = core
        self.dip = dip
        self.name = f"Invest {core:.0%} monthly, rest on {dip:.0%} dips"

    def step(self, ctx: Context, pf: Portfolio) -> None:
        if ctx.deposit:
            pf.buy(ctx.date, ctx.price, ctx.deposit * self.core, "monthly core")
        if ctx.drawdown >= self.dip and pf.cash > 0:
            pf.buy(ctx.date, ctx.price, pf.cash, f"reserve, {ctx.drawdown:.1%} below high")


def default_strategies() -> list:
    return [
        MonthlyDCA(),
        DCAWithDipReserve(core=2 / 3, dip=0.10),
        DipBuyer(0.05),
        DipBuyer(0.10),
        SellHighBuyDip(0.05),
        SellHighBuyDip(0.10),
    ]
