"""Builds and sends the alert email through Gmail.

Credentials come from environment variables, never from the repo:
    GMAIL_ADDRESS       the Gmail account that sends the email
    GMAIL_APP_PASSWORD  a Gmail app password (not your normal password)
    ALERT_TO            where to send alerts (defaults to GMAIL_ADDRESS)
"""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from html import escape

from .monitor import Alert, Status


def money(ticker: str, v: float) -> str:
    return f"£{v:,.2f}" if ticker.endswith(".L") else f"${v:,.2f}"


def _pct(v, signed=False) -> str:
    try:
        if v != v:  # NaN
            return "n/a"
    except TypeError:
        return "n/a"
    return f"{v:+.0%}" if signed else f"{v:.0%}"


def history_line(a: Alert) -> str:
    h = a.history
    n = h["past_episodes"]
    if n < 1:
        return f"This is the first time since {h['since']} it has fallen {a.threshold:.0%} from a high, so there's no history to compare."
    return (f"Since {h['since']}, {a.status.name} has fallen {a.threshold:.0%} from its high {n} other times. "
            f"A year later it was higher {_pct(h['pct_up_12m_after'])} of the time "
            f"(median {_pct(h['median_12m_after'], True)} vs {_pct(h['baseline_median_12m'], True)} from a random day), "
            f"but {_pct(h['pct_fell_10pct_more'])} of the time it fell at least another 10% first.")


def subject(alerts: list[Alert]) -> str:
    if not alerts:
        return "Watchlist status: no new alerts"
    parts = [f"{a.status.ticker} {a.threshold:.0%} below high" for a in alerts]
    return "Dip alert: " + ", ".join(parts)


def build(alerts: list[Alert], statuses: list[Status]) -> tuple[str, str, str]:
    """Returns (subject, plain text, html)."""
    subj = subject(alerts)

    text = []
    for a in alerts:
        s = a.status
        text.append(f"{s.name} ({s.ticker}) is {s.drawdown:.1%} below its all-time high of "
                    f"{money(s.ticker, s.all_time_high)}, now {money(s.ticker, s.price)} "
                    f"({s.day_change:+.1%} today).\n{history_line(a)}\n")
    text.append("Watchlist:")
    for s in statuses:
        text.append(f"  {s.ticker:7s} {money(s.ticker, s.price):>11s}  {s.drawdown:6.1%} below high  "
                    f"{s.day_change:+.1%} today")
    text.append("\nAn alert is a prompt to look into it, not a signal to buy. Not financial advice.")
    plain = "\n".join(text)

    cards = "".join(f"""
      <div style="border:1px solid #e6e5e1;border-left:4px solid #2a78d6;border-radius:6px;padding:14px 16px;margin:0 0 14px">
        <div style="font-size:16px;font-weight:600;color:#0b0b0b">{escape(a.status.name)} ({escape(a.status.ticker)})
          is {a.status.drawdown:.1%} below its high</div>
        <div style="color:#52514e;margin:4px 0 10px">Now {money(a.status.ticker, a.status.price)}
          ({a.status.day_change:+.1%} today) · all-time high {money(a.status.ticker, a.status.all_time_high)}</div>
        <div style="color:#0b0b0b;line-height:1.45">{escape(history_line(a))}</div>
      </div>""" for a in alerts)
    rows = "".join(f"""
        <tr><td style="padding:6px 10px">{escape(s.name)} <span style="color:#8d8c87">{escape(s.ticker)}</span></td>
          <td style="padding:6px 10px;text-align:right">{money(s.ticker, s.price)}</td>
          <td style="padding:6px 10px;text-align:right">{s.drawdown:.1%}</td>
          <td style="padding:6px 10px;text-align:right">{s.day_change:+.1%}</td></tr>""" for s in statuses)
    intro = "" if alerts else '<p style="color:#52514e">No new threshold crossings today.</p>'
    html = f"""<!doctype html><html><body style="margin:0;background:#fcfcfb">
  <div style="max-width:620px;margin:0 auto;padding:20px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;font-size:14px;color:#0b0b0b">
    <h2 style="margin:0 0 14px;font-size:20px">{escape(subj)}</h2>
    {intro}{cards}
    <h3 style="margin:22px 0 6px;font-size:15px">Watchlist</h3>
    <table style="border-collapse:collapse;width:100%;font-size:13px">
      <tr style="color:#52514e;border-bottom:1px solid #e6e5e1">
        <th style="padding:6px 10px;text-align:left;font-weight:500">Holding</th>
        <th style="padding:6px 10px;text-align:right;font-weight:500">Price</th>
        <th style="padding:6px 10px;text-align:right;font-weight:500">Below high</th>
        <th style="padding:6px 10px;text-align:right;font-weight:500">Today</th></tr>{rows}
    </table>
    <p style="color:#8d8c87;font-size:12px;margin-top:22px">An alert is a prompt to look into it, not a signal to buy.
      Prices are daily closes from Yahoo Finance. Not financial advice.</p>
  </div></body></html>"""
    return subj, plain, html


def send(subj: str, plain: str, html: str) -> str:
    sender = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not sender or not password:
        raise RuntimeError("Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD (see README, Stage 3 setup).")
    to = os.environ.get("ALERT_TO") or sender
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subj, sender, to
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)
    return to
