"""
Market Regime Detector.

Classifies each trading day into one of four regimes based on
trend, volatility, and ATR percentile analysis.

Regimes:
  - trend    → Price above MA(n) or strong MA slope
  - range    → Price oscillating around MA with moderate ATR
  - volatile → ATR in the top 30th percentile
  - low_vol  → ATR in the bottom 30th percentile
"""

import logging
from typing import Any, Dict

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class RegimeDetector:
    """Configurable market-regime classifier.

    All thresholds are read from the JSON config so the regime
    logic is tuneable without touching code.
    """

    # Supported regime labels
    TREND: str = "trend"
    RANGE: str = "range"
    VOLATILE: str = "volatile"
    LOW_VOL: str = "low_vol"

    def __init__(self, config: Dict[str, Any]) -> None:
        rc = config.get("regime_classifier", {})
        self.lookback_vol: int = rc.get("lookback_vol", 20)
        self.atr_window: int = rc.get("atr_window", 14)
        self.trend_ma: int = rc.get("trend_ma", 50)
        logger.info(
            "RegimeDetector initialised -- trend_ma=%d, atr_window=%d, lookback_vol=%d",
            self.trend_ma, self.atr_window, self.lookback_vol,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, df: pd.DataFrame) -> pd.Series:
        """Return a Series of regime labels aligned to *df.index*."""
        df = df.copy()

        # --- Trend indicator: MA and its slope ---
        df["ma"] = df["close"].rolling(window=self.trend_ma).mean()
        df["ma_slope"] = df["ma"].diff()

        # --- Volatility indicator: ATR ---
        df["tr"] = pd.concat([
            (df["high"] - df["low"]).abs(),
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"]  - df["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        df["atr"] = df["tr"].rolling(window=self.atr_window).mean()

        # Rolling ATR percentile (position within recent lookback window)
        df["atr_pct"] = df["atr"].rolling(window=self.lookback_vol).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1]
            if not pd.isna(x).all() else np.nan,
            raw=False,
        )

        # --- Build masks (order matters: vol > trend > range) ---
        threshold = df["close"] * 0.001  # 0.1 % of price
        trending = (df["close"] > df["ma"]) | (df["ma_slope"].abs() > threshold)
        volatile = df["atr_pct"] >= 0.70
        low_vol  = df["atr_pct"] <= 0.30

        # Default to RANGE, then overwrite with higher-priority regimes
        regime = pd.Series(self.RANGE, index=df.index)
        regime[trending] = self.TREND
        regime[volatile]  = self.VOLATILE
        regime[low_vol]   = self.LOW_VOL

        # Anything that didn't match any mask stays RANGE
        remaining = (~trending) & (~volatile) & (~low_vol)
        regime[remaining] = self.RANGE

        logger.info(
            "Regime distribution -- %s",
            regime.value_counts().to_dict(),
        )
        return regime


# ------------------------------------------------------------------
# Convenience wrapper (backward-compatible with earlier flat API)
# ------------------------------------------------------------------
def detect_regime(df: pd.DataFrame, config: Dict[str, Any]) -> pd.Series:
    """Functional wrapper around RegimeDetector for simple use-cases."""
    return RegimeDetector(config).detect(df)
