import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from alerts import emailer, monitor  # noqa: E402


def series(values):
    return pd.Series(values, index=pd.bdate_range("2024-01-01", periods=len(values)), dtype=float)


def test_alert_fires_on_the_day_of_the_crossing():
    a = monitor.new_alerts("X", "Xco", series([100, 110, 95, 98]), [0.10])
    assert a == []  # crossed 10% two days ago, not today
    a = monitor.new_alerts("X", "Xco", series([100, 110, 105, 98]), [0.10])
    assert len(a) == 1 and a[0].threshold == 0.10
    assert a[0].status.drawdown == pytest.approx(1 - 98 / 110)


def test_multiple_thresholds_can_fire_on_a_crash_day():
    a = monitor.new_alerts("X", "Xco", series([100, 120, 115, 84]), [0.10, 0.20, 0.30])
    assert [x.threshold for x in a] == [0.10, 0.20, 0.30]


def test_does_not_refire_while_still_below_until_new_high():
    # Crossed 10% on day 3; still below on day 4: no new alert.
    assert monitor.new_alerts("X", "Xco", series([100, 89, 88]), [0.10]) == []
    # New high on day 3 re-arms it; crossing again on day 4 alerts.
    assert len(monitor.new_alerts("X", "Xco", series([100, 89, 101, 90]), [0.10])) == 1


def test_lookback_catches_a_missed_day():
    p = series([100, 110, 98, 97])
    assert monitor.new_alerts("X", "Xco", p, [0.10], lookback_bars=1) == []
    assert len(monitor.new_alerts("X", "Xco", p, [0.10], lookback_bars=2)) == 1


def test_email_content():
    a = monitor.new_alerts("VUAG.L", "Vanguard", series([100, 110, 105, 98]), [0.10])
    statuses = [a[0].status]
    subj, plain, html = emailer.build(a, statuses)
    assert subj == "Dip alert: VUAG.L 10% below high"
    assert "£98.00" in plain and "Vanguard" in html
    assert "first time" in plain  # no previous dips in this short series


def test_status_email_when_no_alerts():
    st = monitor.status_of("MSFT", "Microsoft", series([100, 101]))
    subj, plain, _ = emailer.build([], [st])
    assert "no new alerts" in subj
    assert "$101.00" in plain


def test_send_requires_credentials(monkeypatch):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    with pytest.raises(RuntimeError):
        emailer.send("s", "p", "<p>h</p>")
