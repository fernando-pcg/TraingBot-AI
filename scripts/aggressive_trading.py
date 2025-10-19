"""Sistema de trading agresivo que genera más oportunidades de trade."""

from __future__ import annotations

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import argparse
from config import ConfigLoader
from src.binance_client import BinanceClientWrapper
from src.logger import set_log_level, setup_category_loggers
from src.risk_manager import RiskManager
from src.state_manager import StateManager
from src.strategy import Strategy
from src.trading_engine import TradingEngine


def create_aggressive_strategy():
    """Crea una estrategia ULTRA-AGRESIVA con umbrales muy bajos."""
    return Strategy(
        min_volume=0,  # Sin filtro de volumen
        rsi_bounds=(25, 75),  # Rango MUY amplio (original 30-70)
        adx_trend_threshold=12,  # Threshold muy bajo (original 15)
        atr_volatility_ceiling=0.04,  # Alta tolerancia a volatilidad (original 0.03)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trading Bot - Modo Agresivo")
    parser.add_argument("--profile", default="testnet", help="Configuration profile")
    parser.add_argument("--symbol", default="ETHUSDT", help="Trading pair symbol")
    parser.add_argument("--duration", type=int, default=480, help="Duration in minutes (default: 8 hours)")
    parser.add_argument("--interval", type=int, default=45, help="Check interval in seconds (default: 45)")
    parser.add_argument("--use-gpt", action="store_true", help="Enable GPT for ambiguous signals")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    return parser.parse_args()


def main() -> None:
    print("\n" + "="*70)
    print("🔥 MODO DE TRADING AGRESIVO")
    print("="*70)
    print("\n⚠️  CONFIGURACIÓN AGRESIVA:")
    print("  - Umbrales de señal más bajos")
    print("  - Mayor frecuencia de checks")
    print("  - Rango RSI ampliado (30-70)")
    print("  - Mayor tolerancia a volatilidad")
    print("  - Sentiment analysis habilitado")
    print("\n💡 Objetivo: Generar más oportunidades de trade")
    print("   Win rate esperado: 60-70% (vs 80-90% modo conservador)")
    print("="*70 + "\n")
    
    args = parse_args()
    
    # Cargar configuración
    config_loader = ConfigLoader()
    config = config_loader.load(args.profile)
    config.dry_run = True  # Siempre en dry-run para pruebas
    config.log_level = args.log_level
    
    # Ajustar parámetros de riesgo para modo ULTRA-AGRESIVO (anti-ranging)
    config.risk.max_exposure_pct = 0.6  # Aumentar de 0.5 a 0.6
    config.strategy.risk_percent = 0.02  # Aumentar riesgo por trade de 0.015 a 0.02
    config.risk.stop_loss_pct = 0.015  # Stop loss MÁS amplio (de 0.012 a 0.015) para evitar whipsaws
    config.risk.take_profit_pct = 0.025  # Take profit más grande para compensar
    
    set_log_level(config.log_level)
    loggers = setup_category_loggers(Path(config.logs_dir))
    system_logger = loggers["system"]
    
    system_logger.info("=" * 60)
    system_logger.info("🔥 Starting Trading Bot - AGGRESSIVE MODE")
    system_logger.info("Environment: %s | Mode: DRY-RUN", config.environment.value.upper())
    system_logger.info("Symbol: %s | Duration: %d minutes", args.symbol, args.duration)
    system_logger.info("Check Interval: %d seconds", args.interval)
    system_logger.info("Max Exposure: %.1f%% | Risk per Trade: %.2f%%", 
                      config.risk.max_exposure_pct * 100,
                      config.strategy.risk_percent * 100)
    system_logger.info("=" * 60)
    
    # Componentes
    state_manager = StateManager(Path(config.state_file), Path(config.trades_history_file))
    
    # Estrategia agresiva
    strategy = create_aggressive_strategy()
    system_logger.info("📊 ULTRA-Aggressive Strategy Parameters:")
    system_logger.info("  - RSI Bounds: (25, 75) - VERY wide range")
    system_logger.info("  - ADX Threshold: 12 - VERY low trend requirement")
    system_logger.info("  - ATR Volatility: 0.04 - VERY high tolerance")
    system_logger.info("  - Signal Threshold: 0.7 - VERY easy to trigger")
    system_logger.info("  - Stop Loss: 1.2%% - wider protection")
    
    # Risk manager ajustado
    risk_manager = RiskManager(
        max_daily_loss_pct=config.risk.daily_loss_limit_pct,
        max_exposure_pct=config.risk.max_exposure_pct,
    )
    
    binance_client = BinanceClientWrapper(config, loggers["api_calls"])
    
    # Trading engine con sentiment analysis
    trading_engine = TradingEngine(
        config=config,
        client=binance_client,
        strategy=strategy,
        risk_manager=risk_manager,
        state_manager=state_manager,
        loggers=loggers,
        use_sentiment_analysis=True,  # Siempre habilitado en modo agresivo
        use_gpt=args.use_gpt,
    )
    
    # Ejecutar
    system_logger.info("🚀 Starting aggressive trading session...")
    trading_engine.run(
        symbol=args.symbol,
        duration_minutes=args.duration,
        interval_seconds=args.interval
    )
    
    system_logger.info("✅ Aggressive trading session completed")


if __name__ == "__main__":
    main()

