"""Script para ejecutar sesión optimizada de 10 horas.

Este script:
1. Analiza las mejores monedas disponibles usando los componentes existentes
2. Selecciona la más prometedora según condiciones actuales
3. Ejecuta la estrategia agresiva durante 10 horas
"""

from __future__ import annotations

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import time
from typing import List, Dict, Any
from config import ConfigLoader
from data_sources import DataAggregator, SentimentAnalyzer
from src.binance_client import BinanceClientWrapper
from src.logger import set_log_level, setup_category_loggers
from src.risk_manager import RiskManager
from src.state_manager import StateManager
from src.strategy import Strategy
from src.trading_engine import TradingEngine


# Monedas principales a evaluar
CANDIDATE_SYMBOLS = [
    "BTCUSDT",   # Bitcoin - más estable
    "ETHUSDT",   # Ethereum - buen volumen
    "BNBUSDT",   # Binance Coin - alta liquidez
    "SOLUSDT",   # Solana - alto momentum
    "ADAUSDT",   # Cardano
    "DOGEUSDT",  # Dogecoin - alta volatilidad
    "MATICUSDT", # Polygon
    "AVAXUSDT",  # Avalanche
]


def create_aggressive_strategy():
    """Crea estrategia ULTRA-AGRESIVA optimizada para mantener ganancias."""
    return Strategy(
        min_volume=0,
        rsi_bounds=(25, 75),  # Rango amplio
        adx_trend_threshold=12,
        atr_volatility_ceiling=0.04,
    )


def evaluate_coins(aggregator: DataAggregator, sentiment_analyzer: SentimentAnalyzer) -> List[Dict[str, Any]]:
    """Evalúa las monedas candidatas y las ordena por potencial."""
    
    print("\n" + "="*70)
    print("🔍 EVALUANDO MONEDAS CANDIDATAS")
    print("="*70)
    
    evaluations = []
    
    for symbol in CANDIDATE_SYMBOLS:
        try:
            print(f"\n📊 Analizando {symbol}...")
            
            # Obtener análisis completo usando sentiment_analyzer
            analysis = sentiment_analyzer.analyze_market(symbol)
            
            coin_data = analysis["compiled_data"].coin_metrics
            sentiment_data = analysis["compiled_data"].market_sentiment
            final_rec = analysis["final_recommendation"]
            local_analysis = analysis["local_analysis"]
            
            score = calculate_opportunity_score(
                price_change_24h=coin_data.price_change_24h,
                volume_24h=coin_data.volume_24h,
                market_cap=coin_data.market_cap,
                sentiment_score=coin_data.sentiment_score,
                compiled_score=local_analysis["compiled_score"],
                action=final_rec["action"],
                confidence=final_rec["confidence"],
                risk_level=final_rec["risk_level"],
            )
            
            evaluation = {
                "symbol": symbol,
                "score": score,
                "price": coin_data.current_price,
                "change_24h": coin_data.price_change_24h,
                "volume_24h": coin_data.volume_24h,
                "market_cap": coin_data.market_cap,
                "action": final_rec["action"],
                "confidence": final_rec["confidence"],
                "risk_level": final_rec["risk_level"],
                "compiled_score": local_analysis["compiled_score"],
                "market_conditions": final_rec["market_conditions"],
            }
            
            evaluations.append(evaluation)
            
            print(f"  OK Precio: ${coin_data.current_price:,.2f}")
            print(f"  OK Cambio 24h: {coin_data.price_change_24h:+.2f}%")
            print(f"  OK Volumen: ${coin_data.volume_24h:,.0f}")
            print(f"  OK Accion: {final_rec['action']} (Confianza: {final_rec['confidence']}%)")
            print(f"  OK Riesgo: {final_rec['risk_level']}")
            print(f"  OK Score Final: {score:.2f}")
            
            # Pequeña pausa para no saturar APIs
            time.sleep(1)
            
        except Exception as exc:
            print(f"  ✗ Error analizando {symbol}: {exc}")
            continue
    
    # Ordenar por score (mayor es mejor)
    evaluations.sort(key=lambda x: x["score"], reverse=True)
    
    return evaluations


def calculate_opportunity_score(
    price_change_24h: float,
    volume_24h: float,
    market_cap: float,
    sentiment_score: float,
    compiled_score: float,
    action: str,
    confidence: int,
    risk_level: str,
) -> float:
    """Calcula un score de oportunidad para una moneda.
    
    Factores considerados:
    - Momentum (cambio de precio 24h)
    - Liquidez (volumen vs market cap)
    - Sentiment general
    - Confianza del análisis
    - Nivel de riesgo
    """
    score = 0.0
    
    # 1. Momentum positivo moderado es mejor (no extremo)
    if 1 <= price_change_24h <= 5:
        score += 2.0  # Momentum positivo ideal
    elif 0 <= price_change_24h < 1:
        score += 1.0  # Momentum positivo suave
    elif price_change_24h > 5:
        score += 0.5  # Mucho momentum = posible corrección
    elif -2 <= price_change_24h < 0:
        score += 0.5  # Pequeña caída = oportunidad
    else:
        score -= 1.0  # Caída fuerte = riesgoso
    
    # 2. Volumen alto = buena liquidez
    if market_cap > 0:
        volume_ratio = volume_24h / market_cap
        if volume_ratio > 0.3:
            score += 1.5
        elif volume_ratio > 0.1:
            score += 1.0
        elif volume_ratio < 0.05:
            score -= 0.5
    
    # 3. Sentiment score
    score += sentiment_score * 1.5
    
    # 4. Compiled score del análisis
    score += compiled_score * 2.0
    
    # 5. Confianza del análisis
    if action == "BUY":
        score += (confidence / 100) * 2.0
    elif action == "SELL":
        score -= (confidence / 100) * 1.0  # Penalizar señales de venta
    else:  # HOLD
        score += 0.5
    
    # 6. Nivel de riesgo
    if risk_level == "LOW":
        score += 1.0
    elif risk_level == "MEDIUM":
        score += 0.3
    else:  # HIGH
        score -= 0.5
    
    return score


def print_evaluation_summary(evaluations: List[Dict[str, Any]]) -> None:
    """Imprime un resumen de las evaluaciones."""
    
    print("\n" + "="*70)
    print("RANKING DE OPORTUNIDADES")
    print("="*70)
    
    for i, ev in enumerate(evaluations[:5], 1):  # Top 5
        print(f"\n{i}. {ev['symbol']}")
        print(f"   Score: {ev['score']:.2f} | {ev['action']} ({ev['confidence']}%)")
        print(f"   Precio: ${ev['price']:,.2f} | Cambio: {ev['change_24h']:+.2f}%")
        print(f"   Riesgo: {ev['risk_level']} | {ev['market_conditions']}")
    
    print("\n" + "="*70)


def main() -> None:
    print("\n" + "="*70)
    print("SESION OPTIMIZADA DE 10 HORAS - ESTRATEGIA AGRESIVA")
    print("="*70)
    print("\nFecha: 19 de Octubre, 2025")
    print("Duracion: 10 horas (600 minutos)")
    print("Objetivo: Maximizar ganancias manteniendo control de riesgo")
    print("\n" + "="*70)
    
    # 1. Inicializar componentes de análisis
    print("\nInicializando sistemas de analisis...")
    
    aggregator = DataAggregator(cache_db_path="data/cache.db")
    sentiment_analyzer = SentimentAnalyzer(
        data_aggregator=aggregator,
        use_gpt=False,  # GPT opcional, deshabilitado por defecto
    )
    
    # 2. Obtener condiciones globales del mercado
    print("\nAnalizando condiciones globales del mercado...")
    try:
        btc_analysis = sentiment_analyzer.analyze_market("BTCUSDT")
        global_data = btc_analysis["compiled_data"].global_market
        sentiment_data = btc_analysis["compiled_data"].market_sentiment
        
        print(f"\nMERCADO GLOBAL:")
        print(f"  - Total Market Cap: ${global_data.total_market_cap:,.0f}")
        print(f"  - Cambio 24h: {global_data.market_cap_change_24h:+.2f}%")
        print(f"  - BTC Dominance: {global_data.btc_dominance:.1f}%")
        print(f"  - Fear & Greed Index: {sentiment_data.fear_greed_index} ({sentiment_data.fear_greed_classification})")
        print(f"  - Recomendacion: {sentiment_data.recommendation}")
    except Exception as exc:
        print(f"  WARNING: No se pudo obtener datos globales: {exc}")
    
    # 3. Evaluar monedas candidatas
    evaluations = evaluate_coins(aggregator, sentiment_analyzer)
    
    if not evaluations:
        print("\nERROR: No se pudo evaluar ninguna moneda. Abortando.")
        return
    
    # 4. Mostrar resumen
    print_evaluation_summary(evaluations)
    
    # 5. Seleccionar la mejor moneda
    best_coin = evaluations[0]
    selected_symbol = best_coin["symbol"]
    
    print("\n" + "="*70)
    print(f"MONEDA SELECCIONADA: {selected_symbol}")
    print("="*70)
    print(f"  Score: {best_coin['score']:.2f}")
    print(f"  Precio: ${best_coin['price']:,.2f}")
    print(f"  Momentum 24h: {best_coin['change_24h']:+.2f}%")
    print(f"  Acción recomendada: {best_coin['action']} (Confianza: {best_coin['confidence']}%)")
    print(f"  Nivel de riesgo: {best_coin['risk_level']}")
    print(f"  Condiciones: {best_coin['market_conditions']}")
    print("="*70)
    
    # 6. Configurar y ejecutar bot agresivo
    print("\nConfigurando bot de trading agresivo...")
    
    # Cargar configuración
    config_loader = ConfigLoader()
    config = config_loader.load("testnet")
    config.dry_run = True
    config.log_level = "INFO"
    
    # Ajustar parámetros para modo AGRESIVO pero CONTROLADO
    config.risk.max_exposure_pct = 0.6
    config.strategy.risk_percent = 0.02
    config.risk.stop_loss_pct = 0.015  # Stop loss más amplio para evitar whipsaws
    config.risk.take_profit_pct = 0.025  # Take profit mayor
    
    # Si el riesgo es alto, ser más conservador
    if best_coin['risk_level'] == "HIGH":
        config.risk.max_exposure_pct = 0.4
        config.strategy.risk_percent = 0.015
        config.risk.stop_loss_pct = 0.012
        print("  WARNING: Riesgo alto detectado - ajustando parametros a modo moderado")
    
    set_log_level(config.log_level)
    loggers = setup_category_loggers(Path(config.logs_dir))
    system_logger = loggers["system"]
    
    system_logger.info("=" * 60)
    system_logger.info("🔥 Starting 10-Hour Optimized Aggressive Session")
    system_logger.info("Selected Symbol: %s | Score: %.2f", selected_symbol, best_coin['score'])
    system_logger.info("Duration: 10 hours (600 minutes)")
    system_logger.info("Check Interval: 45 seconds")
    system_logger.info("Max Exposure: %.1f%% | Risk per Trade: %.2f%%", 
                      config.risk.max_exposure_pct * 100,
                      config.strategy.risk_percent * 100)
    system_logger.info("=" * 60)
    
    # Componentes
    state_manager = StateManager(Path(config.state_file), Path(config.trades_history_file))
    strategy = create_aggressive_strategy()
    
    system_logger.info("📊 Aggressive Strategy Parameters:")
    system_logger.info("  - RSI Bounds: (25, 75) - Wide range")
    system_logger.info("  - ADX Threshold: 12 - Low trend requirement")
    system_logger.info("  - ATR Volatility: 0.04 - High tolerance")
    system_logger.info("  - Stop Loss: %.1f%%", config.risk.stop_loss_pct * 100)
    system_logger.info("  - Take Profit: %.1f%%", config.risk.take_profit_pct * 100)
    
    risk_manager = RiskManager(
        max_daily_loss_pct=config.risk.daily_loss_limit_pct,
        max_exposure_pct=config.risk.max_exposure_pct,
    )
    
    binance_client = BinanceClientWrapper(config, loggers["api_calls"])
    
    # Trading engine con sentiment analysis habilitado
    trading_engine = TradingEngine(
        config=config,
        client=binance_client,
        strategy=strategy,
        risk_manager=risk_manager,
        state_manager=state_manager,
        loggers=loggers,
        use_sentiment_analysis=True,  # Usar sentiment analysis
        use_gpt=False,  # GPT opcional, cambiar a True si se desea
    )
    
    # Ejecutar sesión de 10 horas
    print("\nINICIANDO SESION DE TRADING DE 10 HORAS...")
    print("Intervalo de check: 45 segundos")
    print("Sentiment analysis: HABILITADO")
    print("Modo: DRY-RUN (simulacion)")
    print("\nPresiona Ctrl+C para detener en cualquier momento\n")
    
    try:
        system_logger.info("🚀 Starting trading session...")
        trading_engine.run(
            symbol=selected_symbol,
            duration_minutes=600,  # 10 horas
            interval_seconds=45     # Check cada 45 segundos
        )
        system_logger.info("✅ Trading session completed successfully")
    except KeyboardInterrupt:
        print("\n\nWARNING: Sesion interrumpida por usuario")
        system_logger.warning("Session interrupted by user")
    except Exception as exc:
        print(f"\n\nERROR: Error durante la sesion: {exc}")
        system_logger.error("Session error: %s", exc, exc_info=True)
    
    print("\n" + "="*70)
    print("SESION FINALIZADA")
    print("="*70)
    print("\nRevisa los logs en la carpeta 'logs/' para analisis detallado")
    print("Revisa 'state/trades.json' para historial de operaciones\n")


if __name__ == "__main__":
    main()

