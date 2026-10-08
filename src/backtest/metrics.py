"""Performance metrics for a backtest Result."""

from __future__ import annotations

from datetime import date

from .engine import Result


def xirr(cashflows: list[tuple[date, float]]) -> float:
    """Money-weighted annual return: the rate that makes the cashflows sum to 0.

    This is the fair way to compare strategies with monthly deposits, because
    it accounts for *when* each pound went in.
    """
    t0 = cashflows[0][0]
    years = [(d - t0).days / 365.0 for d, _ in cashflows]
    amounts = [a for _, a in cashflows]

    def npv(r: float) -> float:
        return sum(a / (1 + r) ** t for a, t in zip(amounts, years))

    lo, hi = -0.99, 1.0
    if npv(lo) * npv(hi) > 0:
        return float("nan")
    for _ in range(200):  # bisection: slow but very robust
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def summarise(result: Result) -> dict:
    eq = result.equity
    final = float(eq["value"].iloc[-1])
    contributed = float(eq["contributed"].iloc[-1])
    cash_share = (eq["cash"] / eq["value"].where(eq["value"] > 0)).fillna(1.0)
    return {
        "strategy": result.name,
        "contributed": round(contributed, 2),
        "final_value": round(final, 2),
        "profit": round(final - contributed, 2),
        "annual_return": xirr(result.cashflows),
        "avg_in_cash": float(cash_share.mean()),
        "trades": len(result.trades),
    }
