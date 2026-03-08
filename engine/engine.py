"""
Core backtesting engine.

Responsibilities:
  1. Load JSON configuration
  2. Load cleaned OHLCV data
  3. Detect the market regime for each day
  4. Dynamically discover & instantiate the correct strategy per regime
  5. Generate sgnals and execute trades at next day's open
  6. Export the trade log to outputs/orders.xlsx
"""

import json
import logging
import os
import pkgutil
import importlib
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import numpy as np
import pandas as pd

from engine.regimes.logic import RegimeDetector
from engine.strategies.strategy_base import StrategyBase

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Strategy auto-discovery
# ══════════════════════════════════════════════════════════════════════

def discover_strategy_class(logic_id: str) -> Type[StrategyBase]:
    """Scan the *strategies/* package and return the class whose
    ``logic_id`` matches the requested value.

    This means adding STRAT_5 only requires:
      1. A new .py file under strategies/
      2. A matching JSON block in engine.json
    Zero changes to the engine code.
    """
    pkg_path = str(Path(__file__).resolve().parent / "strategies")

    for _, module_name, _ in pkgutil.iter_modules([pkg_path]):
        if module_name == "strategy_base":
            continue
        full_module = f"engine.strategies.{module_name}"
        module = importlib.import_module(full_module)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, StrategyBase)
                and obj is not StrategyBase
                and getattr(obj, "logic_id", None) == logic_id
            ):
                return obj

    raise ValueError(f"No strategy class found with logic_id={logic_id!r}")


# ══════════════════════════════════════════════════════════════════════
# Backtest Engine
# ══════════════════════════════════════════════════════════════════════

class BacktestEngine:
    """JSON-driven backtesting engine with regime-aware strategy selection."""

    # Fixed mapping: regime label → strategy key in JSON config
    REGIME_TO_STRATEGY: Dict[str, str] = {
        "trend":    "trend_following",
        "range":    "range_play",
        "volatile": "volatility_breakout",
        "low_vol":  "mean_reversion",
    }

    def __init__(self, config_path: str) -> None:
        self.config_path = config_path
        self.config: Dict[str, Any] = self._load_config(config_path)
        self.df: pd.DataFrame = pd.DataFrame()
        self.strategies: Dict[str, StrategyBase] = {}
        self.trades: List[Dict[str, Any]] = []

        logger.info("BacktestEngine created with config: %s", config_path)

    # ------------------------------------------------------------------
    # Config & data loading
    # ------------------------------------------------------------------
    @staticmethod
    def _load_config(path: str) -> Dict[str, Any]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r") as fh:
            config = json.load(fh)
        logger.info("Loaded config from %s", path)
        return config

    def _load_data(self) -> pd.DataFrame:
        data_file: str = self.config["data_file"]
        if not os.path.isfile(data_file):
            raise FileNotFoundError(f"Data file not found: {data_file}")
        df = pd.read_csv(data_file, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index)
        logger.info("Loaded %d rows from %s (%s -> %s)", len(df), data_file,
                     df.index.min().date(), df.index.max().date())
        return df

    # ------------------------------------------------------------------
    # Strategy initialisation (dynamic discovery)
    # ------------------------------------------------------------------
    def _init_strategies(self) -> Dict[str, StrategyBase]:
        strategies: Dict[str, StrategyBase] = {}
        for strat_key, strat_cfg in self.config["strategies"].items():
            if not strat_cfg.get("enabled", False):
                logger.info("Strategy %s is disabled — skipping.", strat_key)
                continue
            logic_id: str = strat_cfg["logic_id"]
            params: Dict[str, Any] = strat_cfg.get("params", {})
            cls = discover_strategy_class(logic_id)
            strategies[strat_key] = cls(params)
        logger.info("Active strategies: %s", list(strategies.keys()))
        return strategies

    # ------------------------------------------------------------------
    # Signal generation (vectorised, per strategy)
    # ------------------------------------------------------------------
    def _generate_all_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=df.index)
        for key, strategy in self.strategies.items():
            sig_df = strategy.generate_signals(df)
            signals[key] = sig_df["signal"]
        return signals

    # ------------------------------------------------------------------
    # Trade execution (no look-ahead: execute at *next* day open)
    # ------------------------------------------------------------------
    def _execute_trades(
        self,
        df: pd.DataFrame,
        signals: pd.DataFrame,
    ) -> List[Dict[str, Any]]:
        trades: List[Dict[str, Any]] = []
        df = df.copy()
        df["next_open"] = df["open"].shift(-1)

        position: int = 0
        entry_price: float = 0.0
        entry_dt: Optional[pd.Timestamp] = None
        current_strategy: Optional[str] = None
        current_regime: Optional[str] = None
        bars_held: int = 0

        for i in range(len(df) - 1):
            regime: str = df["regime"].iloc[i]
            next_open: float = df["next_open"].iloc[i]

            if pd.isna(regime) or pd.isna(next_open):
                continue

            strat_key = self.REGIME_TO_STRATEGY.get(regime)
            if strat_key is None or strat_key not in self.strategies:
                continue

            signal: int = int(signals[strat_key].iloc[i])

            if position == 0:
                if signal in (1, -1):
                    position = signal
                    entry_price = next_open
                    entry_dt = df.index[i + 1]
                    current_strategy = strat_key
                    current_regime = regime
                    bars_held = 0
            else:
                bars_held += 1
                # Exit when signal flips against the current position
                if (position == 1 and signal == -1) or (position == -1 and signal == 1):
                    exit_price = next_open
                    exit_dt = df.index[i + 1]
                    pnl = (exit_price - entry_price) * position

                    trades.append({
                        "entry_dt": entry_dt,
                        "entry_price": round(entry_price, 2),
                        "qty": 1,
                        "side": "BUY" if position == 1 else "SELL",
                        "strategy_used": current_strategy,
                        "regime": current_regime,
                        "exit_dt": exit_dt,
                        "exit_price": round(exit_price, 2),
                        "pnl": round(pnl, 2),
                        "bars_held": bars_held,
                    })
                    position = 0

        logger.info("Executed %d round-trip trades", len(trades))
        return trades

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    @staticmethod
    def _export(trades: List[Dict[str, Any]], out_dir: str = "outputs") -> None:
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, "orders.xlsx")
        if trades:
            df_out = pd.DataFrame(trades).sort_values("entry_dt")
            df_out.to_excel(path, index=False)
            logger.info("Exported %d trades -> %s", len(df_out), path)
        else:
            logger.warning("No trades to export.")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def run(self) -> None:
        """Full pipeline: load -> detect -> signal -> trade -> export."""
        logger.info("=" * 60)
        logger.info("ENGINE RUN START")
        logger.info("=" * 60)

        # Step 1-2: Load data
        self.df = self._load_data()

        # Step 3: Regime detection
        detector = RegimeDetector(self.config)
        self.df["regime"] = detector.detect(self.df)

        # Step 4: Initialise strategies from JSON
        self.strategies = self._init_strategies()

        # Step 5: Generate signals
        signals = self._generate_all_signals(self.df)

        # Step 6-7: Execute trades
        self.trades = self._execute_trades(self.df, signals)

        # Step 8: Export
        self._export(self.trades)

        logger.info("ENGINE RUN COMPLETE -- %d trades", len(self.trades))


# ══════════════════════════════════════════════════════════════════════
# Convenience function (keeps run_engine.py thin)
# ══════════════════════════════════════════════════════════════════════

def run(config_path: str) -> None:
    """Create an engine instance and run the full backtest."""
    engine = BacktestEngine(config_path)
    engine.run()
