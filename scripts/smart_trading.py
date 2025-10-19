"""Script inteligente que analiza el mercado y ejecuta el bot con la mejor configuración."""

from __future__ import annotations

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import argparse
from typing import Tuple

from data_sources import DataAggregator, SentimentAnalyzer


def determine_risk_profile(confidence: int) -> Tuple[float, float]:
    """Map confidence percentage to (risk_percent, max_exposure_pct)."""

    if confidence >= 85:
        return 0.025, 0.55
    if confidence >= 75:
        return 0.02, 0.5
    if confidence >= 65:
        return 0.015, 0.4
    if confidence >= 55:
        return 0.0125, 0.35
    return 0.01, 0.3


def analyze_market_and_choose_symbol():
    """Analiza el mercado y elige el mejor símbolo para tradear."""
    print("\n" + "="*70)
    print("🤖 SISTEMA DE TRADING INTELIGENTE")
    print("="*70)
    
    print("\n📊 Analizando mercado global...")
    
    aggregator = DataAggregator(cache_db_path="data/cache.db")
    analyzer = SentimentAnalyzer(aggregator, use_gpt=False)
    
    # Lista de símbolos populares para analizar
    symbols_to_analyze = [
        "BTCUSDT",   # Bitcoin
        "ETHUSDT",   # Ethereum
        "BNBUSDT",   # Binance Coin
        "SOLUSDT",   # Solana
        "ADAUSDT",   # Cardano
    ]
    
    print(f"\n🔍 Analizando {len(symbols_to_analyze)} monedas principales...\n")
    
    results = []
    
    for symbol in symbols_to_analyze:
        try:
            print(f"  Analizando {symbol}...", end=" ")
            result = analyzer.analyze_market(symbol, use_gpt_override=False)
            
            final_rec = result['final_recommendation']
            compiled_data = result['compiled_data']
            
            # Calcular un score ponderado
            confidence = final_rec['confidence']
            action = final_rec['action']
            risk = final_rec['risk_level']
            compiled_score = compiled_data.compiled_score
            
            # Asignar puntos según acción
            action_score = 0
            if action == "BUY":
                action_score = confidence
            elif action == "SELL":
                action_score = -confidence
            else:  # HOLD
                action_score = 0
            
            # Penalizar por riesgo alto
            risk_multiplier = 1.0
            if risk == "HIGH":
                risk_multiplier = 0.7
            elif risk == "MEDIUM":
                risk_multiplier = 0.85
            
            # Score final
            final_score = (action_score + compiled_score * 50) * risk_multiplier
            
            results.append({
                'symbol': symbol,
                'action': action,
                'confidence': confidence,
                'risk': risk,
                'compiled_score': compiled_score,
                'final_score': final_score,
                'price': compiled_data.coin_metrics.current_price,
                'change_24h': compiled_data.coin_metrics.price_change_24h,
                'result': result
            })
            
            print(f"✅ Score: {final_score:.2f}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            continue
    
    if not results:
        print("\n❌ No se pudo analizar ninguna moneda")
        return None
    
    # Ordenar por score
    results.sort(key=lambda x: x['final_score'], reverse=True)
    
    # Mostrar análisis general del mercado
    print("\n" + "="*70)
    print("📈 ANÁLISIS GENERAL DEL MERCADO")
    print("="*70)
    
    # Obtener datos globales
    best_result = results[0]['result']
    market_sentiment = best_result['compiled_data'].market_sentiment
    global_market = best_result['compiled_data'].global_market
    
    print(f"\n🌍 Mercado Global:")
    print(f"  - Market Cap Total: ${global_market.total_market_cap:,.0f}")
    print(f"  - Cambio 24h: {global_market.market_cap_change_24h:+.2f}%")
    print(f"  - Dominancia BTC: {global_market.btc_dominance:.2f}%")
    print(f"  - Dominancia ETH: {global_market.eth_dominance:.2f}%")
    
    print(f"\n😱 Sentiment del Mercado:")
    print(f"  - Fear & Greed Index: {market_sentiment.fear_greed_index}/100")
    print(f"  - Clasificación: {market_sentiment.fear_greed_classification}")
    print(f"  - Recomendación: {market_sentiment.recommendation}")
    
    print(f"\n🔥 Trending Coins:")
    trending = best_result['compiled_data'].trending_coins
    print(f"  {', '.join(trending[:5])}")
    
    # Mostrar ranking de monedas
    print("\n" + "="*70)
    print("🏆 RANKING DE OPORTUNIDADES")
    print("="*70)
    print(f"\n{'#':<3} {'Símbolo':<10} {'Acción':<8} {'Conf.':<7} {'Riesgo':<8} {'Score':<8} {'Precio':<12} {'24h %':<8}")
    print("-"*70)
    
    for i, r in enumerate(results, 1):
        emoji = "🟢" if r['action'] == "BUY" else "🔴" if r['action'] == "SELL" else "🟡"
        print(f"{i:<3} {emoji} {r['symbol']:<9} {r['action']:<8} {r['confidence']:<7}% {r['risk']:<8} "
              f"{r['final_score']:<8.2f} ${r['price']:<11,.2f} {r['change_24h']:+.2f}%")
    
    # Elegir la mejor opción
    best = results[0]
    
    print("\n" + "="*70)
    print("🎯 MONEDA SELECCIONADA")
    print("="*70)
    
    print(f"\n✅ {best['symbol']}")
    print(f"  - Acción Recomendada: {best['action']}")
    print(f"  - Confianza: {best['confidence']}%")
    print(f"  - Nivel de Riesgo: {best['risk']}")
    print(f"  - Score Final: {best['final_score']:.2f}")
    print(f"  - Precio Actual: ${best['price']:,.2f}")
    print(f"  - Cambio 24h: {best['change_24h']:+.2f}%")
    
    # Mostrar señales principales
    local_analysis = best['result']['local_analysis']
    print(f"\n📊 Señales Detectadas:")
    for i, signal in enumerate(local_analysis['signals'][:5], 1):
        print(f"  {i}. {signal}")
    
    # Recomendación de parámetros
    print("\n" + "="*70)
    print("⚙️  PARÁMETROS RECOMENDADOS")
    print("="*70)
    
    # Determinar duración basada en riesgo y volatilidad
    if best['risk'] == "HIGH":
        duration = 30
        interval = 30
        print(f"  ⚠️  Alto riesgo detectado - trading más conservador")
    elif best['risk'] == "MEDIUM":
        duration = 60
        interval = 45
        print(f"  ⚡ Riesgo medio - balance entre seguridad y oportunidades")
    else:
        duration = 120
        interval = 60
        print(f"  ✅ Bajo riesgo - permitir más tiempo para desarrollar posiciones")
    
    print(f"\n  - Duración: {duration} minutos")
    print(f"  - Intervalo de chequeo: {interval} segundos")
    print(f"  - Sentiment Analysis: Habilitado")
    
    # Determinar si usar GPT basado en confianza
    use_gpt = best['confidence'] < 70
    gpt_status = "Habilitado" if use_gpt else "Deshabilitado"
    print(f"  - GPT: {gpt_status}")
    if use_gpt:
        print(f"    💡 (Confianza <70%, GPT ayudará en señales ambiguas)")

    risk_percent, max_exposure = determine_risk_profile(best['confidence'])

    print("\n" + "="*70)
    print("💰 Gestión de Capital Recomendada")
    print("="*70)
    print(f"  - Riesgo por trade: {risk_percent * 100:.2f}% del capital disponible")
    print(f"  - Exposición máxima simultánea: {max_exposure * 100:.1f}%")

    return {
        'symbol': best['symbol'],
        'duration': duration,
        'interval': interval,
        'use_gpt': use_gpt,
        'action': best['action'],
        'confidence': best['confidence'],
        'risk': best['risk'],
        'market_sentiment': market_sentiment,
        'risk_percent': risk_percent,
        'max_exposure_pct': max_exposure,
    }


def execute_bot(config: dict):
    """Ejecuta el bot con la configuración optimizada."""
    import subprocess
    import os
    
    print("\n" + "="*70)
    print("🚀 EJECUTANDO BOT DE TRADING")
    print("="*70)
    
    # Asegurarse de ejecutar desde la raíz del proyecto
    project_root = Path(__file__).parent.parent
    
    cmd = [
        "python",
        "-m", "src.main",  # Usar módulo para evitar problemas de import
        "--symbol", config['symbol'],
        "--duration", str(config['duration']),
        "--interval", str(config['interval']),
    ]
    
    # Agregar GPT si es necesario
    if config['use_gpt']:
        cmd.append("--use-gpt")

    if config.get('risk_percent') is not None:
        cmd.extend(["--risk-percent", f"{config['risk_percent']}"])

    if config.get('max_exposure_pct') is not None:
        cmd.extend(["--max-exposure", f"{config['max_exposure_pct']}"])
    
    print(f"\n📝 Comando: {' '.join(cmd)}")
    print(f"\n⏰ Duración estimada: {config['duration']} minutos")
    print(f"\n{'='*70}\n")
    
    # Mostrar advertencia según acción recomendada
    if config['action'] == "HOLD":
        print("⚠️  NOTA: El análisis recomienda HOLD (mantener).")
        print("   El bot buscará oportunidades pero puede no generar señales inmediatas.")
    elif config['action'] == "SELL":
        print("⚠️  NOTA: El análisis actual sugiere venta.")
        print("   El bot puede no generar señales de compra a menos que las condiciones cambien.")
    else:
        print("✅ Condiciones favorables detectadas para trading.")
    
    print("\n" + "="*70)
    print("Iniciando en 3 segundos...")
    print("="*70 + "\n")
    
    import time
    time.sleep(3)
    
    # Ejecutar el bot
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode == 0
    except KeyboardInterrupt:
        print("\n\n⏹️  Bot detenido por el usuario")
        return False
    except Exception as e:
        print(f"\n\n❌ Error ejecutando el bot: {e}")
        return False


def _ask_to_continue(auto_continue: bool) -> bool:
    """Return True if trading should continue."""

    if auto_continue:
        print("\n⚙️  Auto-continue activado: procediendo sin solicitar confirmación")
        return True

    # Si la entrada estándar no es interactiva, asumir 'sí'
    if not sys.stdin.isatty():
        print("\n⚙️  Entrada no interactiva detectada: procediendo automáticamente")
        return True

    response = input("¿Continuar con el trading? (S/n): ").strip().lower()
    return response in {"", "s", "si", "y", "yes"}


def main(argv: list[str] | None = None):
    """Función principal."""

    parser = argparse.ArgumentParser(description="Análisis inteligente del mercado y ejecución opcional del bot")
    parser.add_argument("--auto-continue", action="store_true", help="Saltar confirmación interactiva y continuar automáticamente")
    args = parser.parse_args(argv)
    try:
        # Analizar mercado y elegir símbolo
        config = analyze_market_and_choose_symbol()
        
        if not config:
            print("\n❌ No se pudo determinar la mejor moneda para tradear")
            return 1
        
        # Preguntar confirmación (puedes comentar esto para ejecución automática)
        print("\n" + "="*70)
        if not _ask_to_continue(auto_continue=args.auto_continue):
            print("\n⏹️  Operación cancelada por el usuario")
            return 0

        # Ejecutar bot
        success = execute_bot(config)
        
        if success:
            print("\n✅ Trading session completada")
            return 0
        else:
            print("\n⚠️  Trading session terminada con advertencias")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Operación cancelada por el usuario")
        return 0
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

