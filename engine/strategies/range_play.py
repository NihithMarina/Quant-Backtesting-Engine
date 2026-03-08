"""STRAT_4 — Range Play (Support / Resistance).

Buy at the bottom of the lookback-day range.
Sell at the top of the lookback-day range.
"""

import logging
import pandas as pd
import numpy as np
from engine.strategies.strategy_base import StrategyBase

logger = logging.getLogger(__name__)


class RangePlay(StrategyBase):
    """Range-bound strategy that fades extremes of a recent channel."""

    logic_id: str = "STRAT_4"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        lookback: int = self.params.get('lookback', 10)

        # Use shift(1) so the range is computed from *previous* bars only (no look-ahead)
        df['range_high'] = df['high'].rolling(window=lookback).max().shift(1)
        df['range_low']  = df['low'].rolling(window=lookback).min().shift(1)

        df['signal'] = 0

        # Buy when price touches / breaks below the range floor (support)
        buy_mask = df['low'] <= df['range_low']
        df.loc[buy_mask, 'signal'] = 1

        # Sell when price touches / breaks above the range ceiling (resistance)
        sell_mask = df['high'] >= df['range_high']
        df.loc[sell_mask, 'signal'] = -1

        logger.debug("RangePlay signals -- buys: %d, sells: %d", buy_mask.sum(), sell_mask.sum())
        return df
