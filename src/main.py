"""Main entry point for the trading bot MVP."""

from __future__ import annotations

import argparse
from pathlib import Path

from config import ConfigLoader
from src.binance_client import BinanceClientWrapper
from src.logger import set_log_level, setup_category_loggers
from src.risk_manager import RiskManager
from src.state_manager import StateManager
from src.strategy import Strategy
from src.trading_engine import TradingEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trading Bot MVP")
    parser.add_argument("--profile", default="testnet", help="Configuration profile to load")
    parser.add_argument("--dry-run", action="store_true", help="Override config to dry-run")
    parser.add_argument("--no-dry-run", action="store_true", help="Override config to live trading")
    parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair symbol")
    parser.add_argument("--log-level", default=None, help="Override log level")
    parser.add_argument("--duration", type=int, default=10, help="Trading duration in minutes")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    config_loader = ConfigLoader()
    config = config_loader.load(args.profile)
    if args.dry_run:
        config.dry_run = True
    if args.no_dry_run:
        config.dry_run = False
    if args.log_level:
        config.log_level = args.log_level

    set_log_level(config.log_level)
    loggers = setup_category_loggers(Path(config.logs_dir))
    system_logger = loggers["system"]
    
    mode = "DRY-RUN" if config.dry_run else "LIVE"
    system_logger.info("=" * 60)
    system_logger.info("Starting Trading Bot MVP")
    system_logger.info("Environment: %s | Mode: %s", config.environment.value.upper(), mode)
    system_logger.info("Symbol: %s | Duration: %d minutes", args.symbol, args.duration)
    system_logger.info("=" * 60)

    state_manager = StateManager(Path(config.state_file), Path(config.trades_history_file))
    strategy = Strategy(min_volume=0, rsi_bounds=(30, 70), aggressive=True)
    risk_manager = RiskManager(
        max_daily_loss_pct=config.risk.daily_loss_limit_pct,
        max_exposure_pct=config.risk.max_exposure_pct,
    )
    
    binance_client = BinanceClientWrapper(config, loggers["api_calls"])
    
    trading_engine = TradingEngine(
        config=config,
        client=binance_client,
        strategy=strategy,
        risk_manager=risk_manager,
        state_manager=state_manager,
        loggers=loggers,
    )
    
    trading_engine.run(symbol=args.symbol, duration_minutes=args.duration, interval_seconds=args.interval)
    
    system_logger.info("Trading session completed")


if __name__ == "__main__":
    main()


