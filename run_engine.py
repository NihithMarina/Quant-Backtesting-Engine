"""
Entry point for the quant backtesting engine.

Usage:
    python run_engine.py --config configs/engine.json
"""

import argparse
import logging
import sys

from engine.engine import run


def _setup_logging() -> None:
    """Configure root logger: INFO to console, DEBUG to file."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (INFO+)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    root.addHandler(console)

    # File handler (DEBUG+)
    file_h = logging.FileHandler("outputs/engine.log", mode="w")
    file_h.setLevel(logging.DEBUG)
    file_h.setFormatter(fmt)
    root.addHandler(file_h)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the regime-aware quant backtesting engine."
    )
    parser.add_argument(
        "--config", type=str, required=True, help="Path to JSON config file",
    )
    args = parser.parse_args()

    import os
    os.makedirs("outputs", exist_ok=True)

    _setup_logging()
    logger = logging.getLogger(__name__)

    try:
        run(args.config)
    except FileNotFoundError as exc:
        logger.error("File not found: %s", exc)
        sys.exit(1)
    except Exception:
        logger.exception("Unhandled error during engine run")
        sys.exit(1)


if __name__ == "__main__":
    main()
