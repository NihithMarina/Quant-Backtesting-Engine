# Research Notes

These are my notes on the thinking behind the regime detection, strategy choices, and trade-offs in this engine.


## How the regime detector works

The idea is simple: not every strategy works in every market. A trend-following system gets chopped up in a sideways market, and a mean-reversion system gets destroyed during a breakout. So before generating any signals, the engine first asks — what kind of market are we in today?

It uses three indicators to figure that out:

- **50-day moving average** — is price above or below it? Is the MA itself sloping steeply? This tells us if there's a directional trend.
- **14-day ATR (Average True Range)** — how much is the market actually moving day-to-day? This is raw volatility.
- **ATR percentile over a 20-day window** — is today's ATR high or low *compared to the last 20 days*? This normalizes volatility so we're not comparing absolute numbers across different price levels.

The classification goes in this order (first match wins):

1. **Volatile** — ATR percentile is in the top 30% (>= 0.70). The market is swinging hard.
2. **Low vol** — ATR percentile is in the bottom 30% (<= 0.30). Things are quiet.
3. **Trending** — Price is above the 50-day MA, or the MA slope is steeper than 0.1% of price.
4. **Ranging** — None of the above. This is the default.

The order matters. A day can be both trending *and* volatile — and when that happens, I want the volatility breakout strategy handling it, not the MA crossover. Extreme volatility conditions take priority because they change the character of price action more than trend alone does.


## Why each strategy fits its regime

**Trend Following in trending markets** — MA crossovers are lagging by design, which is actually a feature in trending conditions. You're not trying to catch the exact bottom; you're trying to ride the bulk of a sustained move. The lag filters out noise and keeps you in the trade. In a trending market, momentum tends to persist, so the crossover signal has a decent hit rate.

**Mean Reversion in low-vol markets** — When ATR is compressed, price tends to oscillate in a tight band. RSI works well here because it catches the extremes of that oscillation. An RSI below 30 in a quiet market usually means price has stretched too far down and will snap back. You wouldn't want to do this in a volatile market though — an RSI of 30 during a crash just means it's going lower.

**Volatility Breakout in volatile markets** — High ATR days often kick off a new directional move. The strategy uses ATR-scaled bands (previous high + 1.5× ATR) to catch those explosive breaks. The multiplier keeps it from triggering on normal-range days — you only get a signal when the move is genuinely outsized.

**Range Play in ranging markets** — If price is just bouncing between a floor and ceiling with no clear direction, the best thing to do is fade the extremes. Buy near support, sell near resistance. The 10-day lookback adapts the channel to recent price memory rather than using some static level.


## Why dynamic switching helps

The core problem with running one strategy all the time is drawdowns during the wrong regime. A trend follower in a ranging market takes whipsaw after whipsaw. A mean reversion system during a strong trend keeps shorting something that's going up.

Dynamic regime switching addresses this in a few ways:

- **Reduces mismatch losses** — only the strategy designed for the current conditions gets to trade. You're not forcing a square peg into a round hole.
- **Better capital use** — instead of sitting through a bad period or taking low-quality signals, capital goes to whichever strategy actually has edge right now.
- **Natural diversification** — over a few months, the portfolio touches different return streams (momentum, mean reversion, breakout) as markets evolve. That smooths the equity curve.
- **Removes gut feel** — the switching is mechanical. No temptation to hold a trend position through a volatility spike because "it'll come back."


## What can go wrong

**Detection lag.** MA and ATR are lagging indicators. By the time the regime detector says "we're in a trend," you might have already missed the best entry. Shorter lookback windows or leading indicators (like implied volatility from options) could help.

**Whipsaw at boundaries.** If the market is right on the edge between two regimes — trending one day, ranging the next — the engine flip-flops between strategies and generates conflicting signals. A cooldown period (require N days in a regime before switching) would fix this but I haven't implemented it yet.

**Threshold sensitivity.** The 70th/30th percentile cutoffs and the MA slope threshold are judgment calls. They work on this dataset, but a different instrument or timeframe might need different numbers. That's why they're in the JSON config — easy to tune without touching code. Ideally you'd do walk-forward optimization to set these properly.

**Switching costs.** Every time the regime changes and a different strategy takes over, you might close one position and open another. That's two sets of slippage and commissions. The engine doesn't currently model transaction costs, so the real PnL would be somewhat lower.

**Look-ahead risk.** If the regime detector accidentally uses current-bar data to classify the regime, and then a strategy generates a signal on that same bar, you've got look-ahead bias. I've been careful to use shifted data for indicators, but it's something to watch.


## Things I'd improve next

**Walk-forward testing** — Right now the engine does a single pass over the whole dataset. Properly, you'd split into in-sample and out-of-sample windows and validate that the parameters hold up.

**Position sizing** — Fixed quantity of 1 is a placeholder. A real system would size based on risk — something like "risk 1% of equity per trade, position size = risk budget / ATR."

**Transaction costs** — Deducting slippage and brokerage from PnL would give a more honest picture of performance.

**Multi-timeframe regimes** — Detecting regime on a weekly chart for the big picture, then using daily signals for entries. This would cut down on the day-to-day regime flipping.

**Regime confidence** — Instead of a hard binary switch, assign a probability to each regime and blend strategy signals proportionally. If the detector is 60% confident it's trending and 40% ranging, maybe weight signals accordingly.

**Better exits** — Each strategy currently manages its own exits based on indicator reversal. Adding a trailing stop or a time-based exit would protect against adverse moves that the indicator is slow to pick up.

**More instruments** — Running this across NIFTY, BANKNIFTY, gold, crude, etc. and diversifying at the portfolio level. The regime detector should work on anything with OHLCV data.

**Visualization** — An equity curve, a regime timeline chart, and a drawdown plot would make it much easier to analyze results visually instead of staring at a spreadsheet.
