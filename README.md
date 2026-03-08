# Quant Backtesting Engine

This is a backtesting engine I built in Python that picks the right trading strategy based on what the market is doing that day. Instead of running one strategy all the time, it first figures out the market regime — is it trending? ranging? volatile? quiet? — and then hands off to whichever strategy fits that condition best.

The whole thing is config-driven. Strategy parameters, regime thresholds, data paths — everything lives in a single JSON file. And if I want to add a new strategy, I just drop in a Python file and a config block. The engine picks it up automatically at runtime, no wiring needed.

**Built with:** Python 3, pandas, NumPy, openpyxl


## What's in here

```
run_engine.py                     ← entry point, run this
configs/engine.json               ← all the knobs and switches

engine/
  engine.py                       ← BacktestEngine class, runs the pipeline
  regimes/logic.py                ← RegimeDetector, classifies market days
  strategies/
    strategy_base.py              ← abstract base class every strategy extends
    trend_following.py            ← STRAT_1: MA crossover
    mean_reversion.py             ← STRAT_2: RSI-based
    volatility_breakout.py        ← STRAT_3: ATR breakout
    range_play.py                 ← STRAT_4: support/resistance bounce

data/
  ohlc_raw.csv                    ← raw price data
  ohlc_clean.csv                  ← cleaned version the engine reads

outputs/
  orders.xlsx                     ← trade log (generated after a run)
  engine.log                      ← detailed debug log
  validation_report.txt           ← data quality checks
```


## Running it

```bash
pip install pandas numpy openpyxl
python run_engine.py --config configs/engine.json
```

After it runs, check `outputs/orders.xlsx` for the trade log and `outputs/engine.log` if you want the full trace.


## How it works

The pipeline is pretty straightforward:

1. Reads the config from `configs/engine.json`
2. Loads the cleaned OHLCV data
3. Runs the regime detector over every trading day
4. For each day, picks the strategy that matches the detected regime
5. Each strategy generates buy/sell signals using its own indicators
6. Trades get executed at the **next day's open** (so there's no look-ahead cheating)
7. Everything gets dumped into `outputs/orders.xlsx`


## Regime detection

The regime detector looks at three things each day:

- **50-day MA** — is price above or below it? Is the slope steep?
- **14-day ATR** — how much is the market moving in absolute terms?
- **ATR percentile** (rolling 20-day rank) — is today's volatility high or low compared to recent history?

Based on those, each day gets one of these labels:

- **Volatile** (ATR percentile >= 70th) → routes to volatility breakout strategy
- **Low vol** (ATR percentile <= 30th) → routes to mean reversion strategy
- **Trending** (price above MA or strong slope) → routes to trend following strategy
- **Ranging** (everything else) → routes to range play strategy

Volatile gets checked first because a day can be both trending *and* volatile — and in that case, the breakout strategy handles it better than a slow MA crossover would.


## The four strategies

**Trend Following (STRAT_1)** — Classic MA crossover. Uses a 20-day fast MA and 50-day slow MA. Goes long when the fast crosses above the slow, exits when it crosses back down.

**Mean Reversion (STRAT_2)** — RSI-based. Buys when RSI(14) drops below 30 (oversold), sells when it climbs above 70 (overbought). Works well in low-volatility environments where prices tend to snap back to the mean.

**Volatility Breakout (STRAT_3)** — ATR-scaled bands. Buys when the high breaks above the previous day's high plus 1.5× ATR, sells on the downside equivalent. Designed for explosive moves.

**Range Play (STRAT_4)** — Fades the edges of a 10-day price channel. Buys when price touches the floor (support), sells at the ceiling (resistance).

Every strategy extends `StrategyBase` and implements `generate_signals(df)`. All indicators use shifted data so there's no peeking at future bars.


## Results from a test run

Ran it on 123 trading days of Nifty 50 data (Sep 2025 – Mar 2026):

- **4 round-trip trades**
- **Net PnL: +1,317.60**
- **Win rate: 75%** (3 winners, 1 loser)
- Best trade was a mean reversion short during a low-vol period (+656.75)
- The one loss was a range play trade that went against (-108.60)
- Average holding period was about 17 days

The regime breakdown over that period: 43 days ranging, 39 volatile, 34 low-vol, and only 7 trending. Not a lot of trend action in this sample, which is why the trend following strategy barely fired.


## Adding a new strategy

This was a big design goal — zero engine changes to plug in a new strategy.

Say I want to add a momentum strategy. I create `engine/strategies/momentum.py`:

```python
from engine.strategies.strategy_base import StrategyBase

class Momentum(StrategyBase):
    logic_id = "STRAT_5"

    def generate_signals(self, df):
        df = df.copy()
        # indicator logic goes here
        df['signal'] = 0
        return df
```

Then add this to `configs/engine.json`:

```json
"momentum": {
    "enabled": true,
    "logic_id": "STRAT_5",
    "params": { "window": 10 }
}
```

That's it. The engine uses `pkgutil` to scan `engine/strategies/` at startup and finds any class that extends `StrategyBase`. No registry, no factory, no imports to update.


## Trade log format

Each row in `outputs/orders.xlsx` has: entry date, entry price, quantity (always 1), side (BUY/SELL), which strategy triggered it, what regime was active, exit date, exit price, PnL, and how many bars the position was held.


## Logging

Console gets INFO-level messages — just the pipeline progress, how many trades happened, regime counts. The full debug trace (every signal, every indicator value) goes to `outputs/engine.log`.
