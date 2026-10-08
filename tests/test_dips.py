import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from backtest import dips  # noqa: E402


def series(values):
    return pd.Series(values, index=pd.bdate_range("2020-01-01", periods=len(values)), dtype=float)


def test_one_episode_per_slide_and_rearm_on_new_high():
    # Falls 20% from 120 (to 96), keeps falling (no new episode), recovers to a
    # new high of 130, then falls 23% to 100 and never recovers.
    p = series([100, 120, 96, 90, 85, 130, 100, 101])
    eps = dips.find_episodes(p, 0.20)
    assert [e.entry for e in eps] == [96, 100]
    assert eps[0].prior_high == 120
    assert eps[0].years_to_recover == pytest.approx((p.index[5] - p.index[2]).days / 365.25)
    assert np.isnan(eps[1].years_to_recover)
    assert eps[1].years_waited == pytest.approx((p.index[-1] - p.index[6]).days / 365.25)


def test_no_episode_when_drop_is_too_small():
    assert dips.find_episodes(series([100, 95, 91, 100]), 0.10) == []


def test_forward_returns_and_further_drop():
    # 300 trading days: fall to 80 on day 1, dip to 60, end at 120.
    vals = [100, 80] + [60] * 10 + [120] * 288
    eps = dips.find_episodes(series(vals), 0.20)
    e = eps[0]
    assert e.entry == 80
    assert e.further_drop_12m == pytest.approx(60 / 80 - 1)
    assert e.ret_12m == pytest.approx(120 / 80 - 1)


def test_summary_columns():
    vals = [100, 80] + [60] * 10 + [120] * 288
    s = dips.summarise("TEST", series(vals), thresholds=(0.2,))
    row = s.iloc[0]
    assert row.episodes == 1
    assert row.pct_fell_10pct_more == 1.0
    assert row.never_recovered == 0
