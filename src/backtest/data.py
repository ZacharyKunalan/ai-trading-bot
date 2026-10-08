"""Price and cash-rate data loading, with a local CSV cache."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parents[2] / "data"


def _download(symbol: str, start: str, auto_adjust: bool) -> pd.Series:
    import yfinance as yf

    df = yf.download(symbol, start=start, auto_adjust=auto_adjust, progress=False)
    if df.empty:
        raise RuntimeError(f"No data returned for {symbol}")
    close = df["Close"]
    if isinstance(close, pd.DataFrame):  # yfinance returns a column per ticker
        close = close.iloc[:, 0]
    return close.dropna().rename(symbol)


def load_series(symbol: str, start: str = "1993-01-01", auto_adjust: bool = True,
                refresh: bool = False) -> pd.Series:
    """Daily closes for `symbol`, cached to data/<symbol>.csv.

    auto_adjust=True gives prices adjusted for dividends and splits, so the
    backtest includes reinvested dividends (a total-return series).
    """
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{symbol.replace('^', '_')}.csv"
    if path.exists() and not refresh:
        s = pd.read_csv(path, index_col=0, parse_dates=True).iloc[:, 0]
        return s.rename(symbol)
    s = _download(symbol, start, auto_adjust)
    s.to_csv(path)
    return s


def load_prices(ticker: str = "SPY", refresh: bool = False) -> pd.Series:
    return load_series(ticker, refresh=refresh)


def load_cash_rate(index: pd.DatetimeIndex, refresh: bool = False) -> pd.Series:
    """Annual cash yield (as a fraction) aligned to `index`.

    Uses the 13-week US T-bill yield (^IRX) as a stand-in for what idle cash in
    a savings account or money-market fund could earn.
    """
    irx = load_series("^IRX", auto_adjust=False, refresh=refresh) / 100.0
    return irx.reindex(index).ffill().fillna(0.0)
