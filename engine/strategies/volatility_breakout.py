"""STRAT_3 — Volatility Breakout (ATR-based).

Buy when High > prev_high + ATR × multiplier.
Sell when Low  < prev_low  − ATR × multiplier.
"""

import logging
import pandas as pd
import numpy as np
from engine.strategies.strategy_base import StrategyBase

logger = logging.getLogger(__name__)


class VolatilityBreakout(StrategyBase):
    """ATR breakout strategy for volatile markets."""

    logic_id: str = "STRAT_3"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        atr_window: int = self.params.get('atr_window', 14)
        multiplier: float = self.params.get('multiplier', 1.5)

        # True Range (Wilder)
        df['tr'] = pd.concat([
            (df['high'] - df['low']).abs(),
            (df['high'] - df['close'].shift(1)).abs(),
            (df['low']  - df['close'].shift(1)).abs(),
        ], axis=1).max(axis=1)
        df['atr'] = df['tr'].rolling(window=atr_window).mean()

        # Previous day's high/low (no look-ahead)
        prev_high = df['high'].shift(1)
        prev_low  = df['low'].shift(1)

        df['signal'] = 0

        # Buy breakout above previous high + ATR band
        buy_mask = df['high'] > prev_high + df['atr'] * multiplier
        df.loc[buy_mask, 'signal'] = 1

        # Sell breakdown below previous low − ATR band
        sell_mask = df['low'] < prev_low - df['atr'] * multiplier
        df.loc[sell_mask, 'signal'] = -1

        logger.debug("VolatilityBreakout signals -- buys: %d, sells: %d", buy_mask.sum(), sell_mask.sum())
        return df
