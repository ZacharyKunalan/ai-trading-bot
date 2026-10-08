# AI Trading Bot

An AI-assisted investing agent, built in stages. **Stage 1 is a backtester** that tests one question before any money or automation is involved:

> If I put £150 a month into the S&P 500, does waiting for dips (or selling at all-time highs and buying back lower) beat just investing every month?

![Backtest results](results/backtest.png)

## Findings (SPY, £150/month)

**Last 20 years (Oct 2006 to Oct 2026):**

| Strategy | Put in | Ended with | Annual return | Avg. time in cash |
|:--|--:|--:|--:|--:|
| Monthly investing (baseline) | £36,150 | **£173,684** | 13.9% | 0% |
| Invest 67% monthly, rest on 10% dips | £36,150 | £171,660 | 13.8% | 3% |
| Buy only on 5% dips | £36,150 | £173,062 | 13.8% | 3% |
| Buy only on 10% dips | £36,150 | £167,611 | 13.6% | 10% |
| Sell at highs, rebuy on 5% dips | £36,150 | £109,434 | 10.0% | 47% |
| Sell at highs, rebuy on 10% dips | £36,150 | £75,545 | 6.9% | 57% |

**Across 95 different 10-year periods** (start dates every 3 months from 1993):

| Strategy | Beat baseline | Median vs baseline | Worst | Best |
|:--|--:|--:|--:|--:|
| Invest 67% monthly, rest on 10% dips | 31% | −1.0% | −4.7% | +0.6% |
| Buy only on 5% dips | 45% | −0.2% | −2.8% | +0.5% |
| Buy only on 10% dips | 31% | −3.0% | −14.0% | +1.8% |
| Sell at highs, rebuy on 5% dips | 42% | −9.8% | −28.1% | +12.9% |
| Sell at highs, rebuy on 10% dips | 26% | −23.3% | −38.8% | +5.2% |

**What this says:**

- **Selling at all-time highs is the expensive part.** Highs come in clusters during long bull runs, so the strategy spends roughly half its time in cash while the market keeps climbing. Over 20 years it ended with about £64k less than plain monthly investing.
- It *can* win when a crash follows soon after (the 2000–02 and 2008 periods are where its "best" windows come from), but that is a bet on timing, and it lost more often and by more.
- **Waiting for dips without selling** costs much less, but still doesn't reliably beat investing straight away. The deeper the dip you wait for, the more you lose.
- Idle cash was given the T-bill rate here, which is generous to the dip strategies. With `--no-cash-interest` they do worse.

## How it works

```
src/backtest/
├── data.py        # downloads daily prices (Yahoo Finance) and caches them in data/
├── engine.py      # day-by-day simulation: deposits, buys, sells, cash interest
├── strategies.py  # the strategies compared above
├── metrics.py     # money-weighted return (XIRR) and summary stats
└── charts.py      # the chart above
run_backtest.py    # CLI entry point
tests/             # pytest unit tests for the engine and metrics
```

Each strategy only sees a `Context` for the current day (price, all-time high so far, how far below it the price is, whether today is a deposit day), so there's no look-ahead bias. Returns are compared with **XIRR**, the money-weighted annual return, because with monthly deposits *when* money goes in matters as much as how much.

**Assumptions:** deposits on the first trading day of each month; dividends reinvested (adjusted prices); fractional shares; no fees or tax; trades at the daily close; deposits treated as the same currency as the index (no GBP/USD effects); idle cash earns the 13-week US T-bill yield.

## Run it

```bash
pip install -r requirements.txt
python run_backtest.py                       # SPY, 20 years + rolling 10-year windows
python run_backtest.py --ticker AAPL         # any Yahoo Finance ticker
python run_backtest.py --monthly 200 --years 15 --window 5 --no-cash-interest
pytest
```

Results are written to `results/` (CSV tables and the chart).

## Roadmap

- [x] **Stage 1: Backtester.** Does dip-buying beat monthly investing?
- [ ] **Stage 2: Individual stocks.** Run the same test on S&P 500 constituents, and measure how often a stock that drops past a threshold keeps falling.
- [ ] **Stage 3: Monitor and alert.** A scheduled watcher that checks a watchlist against dip thresholds and sends a notification (no automatic real-money trades).
- [ ] **Stage 4: AI layer.** When a threshold trips, Claude reads recent news and explains *why* the stock dropped, to help separate a temporary dip from a company in trouble.
- [ ] **Stage 5: Paper trading.** Execute the strategy on an Alpaca paper account through the Alpaca MCP server, with hard risk limits in code and every decision logged.

*This project is for learning and research. It is not financial advice.*
