"""
Abstract base class for all trading strategies.

Every strategy must:
  1. Subclass StrategyBase
  2. Set a class-level `logic_id` (e.g. "STRAT_1")
  3. Implement `generate_signals(df)` → DataFrame with a 'signal' column
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import logging
import pandas as pd

logger = logging.getLogger(__name__)


class StrategyBase(ABC):
    """Base class that all strategies inherit from."""

    logic_id: str = ""  # Must be overridden by subclasses

    def __init__(self, params: Dict[str, Any]) -> None:
        self.params = params
        logger.info(
            "Initialized strategy %s (logic_id=%s) with params: %s",
            self.__class__.__name__, self.logic_id, params,
        )

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute trading signals from OHLCV data.

        Args:
            df: DataFrame with columns [open, high, low, close, volume].

        Returns:
            DataFrame with an added 'signal' column:
              1 = buy, -1 = sell, 0 = hold/flat.

        Important:
            Must NOT use any future data (no look-ahead bias).
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(logic_id={self.logic_id!r}, params={self.params})"
