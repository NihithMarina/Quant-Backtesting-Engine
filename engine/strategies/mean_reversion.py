"""STRAT_2 — Mean Reversion (RSI-based).

Long when RSI drops below the oversold threshold.
Exit when RSI rises above the overbought threshold.
"""

import logging
import pandas as pd
import numpy as np
from engine.strategies.strategy_base import StrategyBase

logger = logging.getLogger(__name__)


class MeanReversion(StrategyBase):
    """RSI mean-reversion strategy for low-volatility markets."""

    logic_id: str = "STRAT_2"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        rsi_window: int = self.params.get('rsi_window', 14)
        rsi_buy: float = self.params.get('rsi_buy', 30)
        rsi_sell: float = self.params.get('rsi_sell', 70)

        # Wilder-style RSI calculation
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0.0).rolling(window=rsi_window).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(window=rsi_window).mean()

        rs = gain / loss.replace(0, np.nan)  # Avoid division by zero
        df['rsi'] = 100.0 - (100.0 / (1.0 + rs))

        df['signal'] = 0

        # Long when RSI < buy threshold (oversold)
        buy_mask = df['rsi'] < rsi_buy
        df.loc[buy_mask, 'signal'] = 1

        # Exit when RSI > sell threshold (overbought)
        sell_mask = df['rsi'] > rsi_sell
        df.loc[sell_mask, 'signal'] = -1

        logger.debug("MeanReversion signals -- buys: %d, sells: %d", buy_mask.sum(), sell_mask.sum())
        return df
