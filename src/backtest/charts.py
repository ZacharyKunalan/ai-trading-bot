"""Static chart for the README (matplotlib, light theme)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e6e5e1"
NEUTRAL = "#8d8c87"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # slots 1-3: validated all-pairs
NEG = "#e34948"
POS = "#2a78d6"

# The three lines drawn in the left panel, in slot order.
HEADLINE = ["Monthly investing (baseline)", "Buy only on 10% dips", "Sell at highs, rebuy on 5% dips"]


def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_2, labelsize=9, length=0)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plot_results(results, rolling: pd.DataFrame, ticker: str, window: int, out: Path) -> Path:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.4), gridspec_kw={"width_ratios": [1.35, 1]})
    fig.patch.set_facecolor(SURFACE)

    # Left: portfolio value over the headline period.
    _style(ax1)
    by_name = {r.name: r for r in results}
    base = by_name[HEADLINE[0]].equity
    ax1.plot(base.index, base["contributed"], color=NEUTRAL, lw=1.5, ls="--", label="Money put in")
    for name, color in zip(HEADLINE, SERIES):
        eq = by_name[name].equity
        ax1.plot(eq.index, eq["value"], color=color, lw=2, label=name)
        ax1.annotate(f"£{eq['value'].iloc[-1]:,.0f}", (eq.index[-1], eq["value"].iloc[-1]),
                     xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=TEXT)
    ax1.yaxis.set_major_formatter(lambda v, _: f"£{v / 1000:.0f}k")
    start, end = base.index[0], base.index[-1]
    ax1.set_title(f"£150/month into {ticker}, {start.year}–{end.year}\ndividends reinvested, idle cash earns the T-bill rate", loc="left",
                  fontsize=12, color=TEXT, fontweight="bold")
    ax1.legend(frameon=False, fontsize=9, labelcolor=TEXT_2, loc="upper left")
    ax1.margins(x=0.02)
    ax1.set_xlim(right=end + pd.Timedelta(days=900))

    # Right: how each strategy did vs the baseline across many start dates.
    _style(ax2)
    others = rolling[rolling.strategy != HEADLINE[0]]
    med = others.groupby("strategy", sort=False)["vs_baseline"].median()
    beat = others.groupby("strategy", sort=False)["vs_baseline"].apply(lambda x: (x > 1e-9).mean())
    y = range(len(med))[::-1]
    colors = [POS if v >= 0 else NEG for v in med.values]
    ax2.barh(list(y), med.values * 100, color=colors, height=0.55)
    ax2.axvline(0, color=TEXT_2, lw=1)
    ax2.set_yticks(list(y), med.index, fontsize=9, color=TEXT)
    hi = max(med.max() * 100, 0)
    for yi, v, b in zip(y, med.values, beat.values):
        ax2.annotate(f"{v:+.1%}\nbeat baseline in {b:.0%} of windows", (hi, yi),
                     xytext=(8, 0), textcoords="offset points",
                     ha="left", va="center", fontsize=8.5, color=TEXT_2)
    lo = min(med.min() * 100, 0)
    span = hi - lo
    ax2.set_xlim(lo - 0.08 * span, hi + 0.9 * span)
    ax2.xaxis.set_major_formatter(lambda v, _: f"{v:+.0f}%" if v <= hi + 0.01 else "")
    ax2.grid(axis="y", visible=False)
    n = rolling["start"].nunique()
    ax2.set_title(f"Ending value vs baseline\nmedian across {n} different {window}-year start dates",
                  loc="left", fontsize=12, color=TEXT, fontweight="bold")

    fig.tight_layout()
    fig.savefig(out, dpi=160, facecolor=SURFACE)
    plt.close(fig)
    return out
