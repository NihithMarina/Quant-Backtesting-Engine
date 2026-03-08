"""STRAT_1 — Trend Following (MA Crossover).

Buy when fast MA crosses above slow MA.
Sell when fast MA crosses below slow MA.
"""

import logging
import pandas as pd
import numpy as np
from engine.strategies.strategy_base import StrategyBase

logger = logging.getLogger(__name__)


class TrendFollowing(StrategyBase):
    """Moving-average crossover strategy for trending markets."""

    logic_id: str = "STRAT_1"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        fast_ma: int = self.params.get('fast_ma', 20)
        slow_ma: int = self.params.get('slow_ma', 50)

        df['fast_ma'] = df['close'].rolling(window=fast_ma).mean()
        df['slow_ma'] = df['close'].rolling(window=slow_ma).mean()

        df['signal'] = 0

        # Buy: fast MA crosses above slow MA (using previous bar to avoid look-ahead)
        buy_cross = (df['fast_ma'] > df['slow_ma']) & (df['fast_ma'].shift(1) <= df['slow_ma'].shift(1))
        df.loc[buy_cross, 'signal'] = 1

        # Sell: fast MA crosses below slow MA
        sell_cross = (df['fast_ma'] < df['slow_ma']) & (df['fast_ma'].shift(1) >= df['slow_ma'].shift(1))
        df.loc[sell_cross, 'signal'] = -1

        logger.debug("TrendFollowing signals -- buys: %d, sells: %d", buy_cross.sum(), sell_cross.sum())
        return df
