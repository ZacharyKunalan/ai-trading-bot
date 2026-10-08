import sys
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backtest import engine, metrics, strategies  # noqa: E402


def prices(values, start="2020-01-01", freq="MS"):
    """One price per month start, so every bar is a deposit day."""
    idx = pd.date_range(start, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, dtype=float)


def test_dca_buys_every_deposit():
    r = engine.run(prices([100, 100, 100]), strategies.MonthlyDCA(), monthly=150)
    assert r.equity["contributed"].iloc[-1] == 450
    assert r.equity["units"].iloc[-1] == pytest.approx(4.5)
    assert r.equity["cash"].iloc[-1] == pytest.approx(0)


def test_dip_buyer_waits_for_dip_then_buys_everything():
    # Price never drops 10% until the third month.
    r = engine.run(prices([100, 95, 85]), strategies.DipBuyer(0.10), monthly=100)
    eq = r.equity
    assert eq["units"].iloc[1] == 0  # still waiting at 5% down
    assert eq["units"].iloc[2] == pytest.approx(300 / 85)
    assert len(r.trades) == 1


def test_sell_high_sells_on_new_high_with_gain():
    s = strategies.SellHighBuyDip(dip=0.10, min_gain=0.03)
    # Month 1 at ATH: no dip, waits. Month 2: 20% dip, buys. Month 3: new high, sells.
    r = engine.run(prices([100, 80, 110]), s, monthly=100)
    sides = [t.side for t in r.trades]
    assert sides == ["BUY", "SELL"]
    assert r.equity["units"].iloc[-1] == 0
    # 200 bought at 80 = 2.5 units, sold at 110 = 275, plus month-3 deposit of 100.
    assert r.equity["cash"].iloc[-1] == pytest.approx(375)


def test_all_time_high_uses_history_before_start():
    # Peak of 200 happens before the window starts; at 150 we are 25% below it.
    p = prices([200, 150, 150])
    r = engine.run(p, strategies.DipBuyer(0.20), monthly=100, start="2020-02-01")
    # Buys on the very first day of the window, because it knows about the old peak.
    assert r.trades[0].date == date(2020, 2, 1)
    assert all(t.side == "BUY" for t in r.trades)


def test_cash_interest_accrues():
    p = prices([100] * 13)
    rate = pd.Series(0.05, index=p.index)
    r = engine.run(p, strategies.DipBuyer(0.5), monthly=0, cash_rate=rate)
    assert r.equity["cash"].iloc[-1] == 0  # nothing deposited, nothing earned
    r = engine.run(p.iloc[:2], strategies.DipBuyer(0.5), monthly=100, cash_rate=rate)
    # Second month: first 100 earns 31 days of interest, then another 100 arrives.
    assert r.equity["cash"].iloc[-1] == pytest.approx(100 * (1 + 0.05 * 31 / 365) + 100)


def test_xirr_matches_known_rate():
    flows = [(date(2020, 1, 1), -100.0), (date(2021, 1, 1), 110.0)]
    assert metrics.xirr(flows) == pytest.approx(0.10 * 365 / 366 + 0.10 * (1 - 365 / 366), abs=1e-3)
