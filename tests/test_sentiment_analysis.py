"""Script de prueba para el sistema de análisis de sentiment."""

from __future__ import annotations

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from data_sources import DataAggregator, SentimentAnalyzer


def test_data_aggregator():
    """Prueba el Data Aggregator con APIs gratuitas."""
    print("=" * 60)
    print("PRUEBA: Data Aggregator (APIs Gratuitas)")
    print("=" * 60)
    
    aggregator = DataAggregator(cache_db_path="data/test_cache.db")
    
    symbol = "BTCUSDT"
    print(f"\n📊 Compilando datos de mercado para {symbol}...")
    
    try:
        compiled_data = aggregator.get_compiled_data(symbol)
        
        print(f"\n✅ Datos compilados exitosamente!\n")
        
        # Coin Metrics
        print("💰 MÉTRICAS DE LA MONEDA:")
        print(f"  - Precio actual: ${compiled_data.coin_metrics.current_price:,.2f}")
        print(f"  - Cambio 24h: {compiled_data.coin_metrics.price_change_24h:+.2f}%")
        if compiled_data.coin_metrics.price_change_7d:
            print(f"  - Cambio 7d: {compiled_data.coin_metrics.price_change_7d:+.2f}%")
        print(f"  - Market Cap: ${compiled_data.coin_metrics.market_cap:,.0f}")
        print(f"  - Volumen 24h: ${compiled_data.coin_metrics.volume_24h:,.0f}")
        print(f"  - Sentiment Score: {compiled_data.coin_metrics.sentiment_score:.2f}")
        
        # Market Sentiment
        print(f"\n😱 SENTIMIENTO DEL MERCADO:")
        print(f"  - Fear & Greed Index: {compiled_data.market_sentiment.fear_greed_index}")
        print(f"  - Clasificación: {compiled_data.market_sentiment.fear_greed_classification}")
        print(f"  - Score normalizado: {compiled_data.market_sentiment.fear_greed_score:.2f}")
        print(f"  - Recomendación: {compiled_data.market_sentiment.recommendation}")
        
        # Global Market
        print(f"\n🌍 MERCADO GLOBAL:")
        print(f"  - Market Cap Total: ${compiled_data.global_market.total_market_cap:,.0f}")
        print(f"  - Cambio 24h: {compiled_data.global_market.market_cap_change_24h:+.2f}%")
        print(f"  - Dominancia BTC: {compiled_data.global_market.btc_dominance:.2f}%")
        print(f"  - Dominancia ETH: {compiled_data.global_market.eth_dominance:.2f}%")
        
        # Trending & News
        print(f"\n📰 NOTICIAS Y TENDENCIAS:")
        print(f"  - Trending coins: {', '.join(compiled_data.trending_coins[:5])}")
        print(f"  - Noticias recientes: {compiled_data.news_summary['count']}")
        print(f"  - Sentiment de noticias: {compiled_data.news_summary['sentiment']}")
        
        # Compiled Score
        print(f"\n📈 SCORE COMPILADO: {compiled_data.compiled_score:.2f}")
        if compiled_data.compiled_score > 0.3:
            print("  ➡️  SEÑAL: BULLISH")
        elif compiled_data.compiled_score < -0.3:
            print("  ➡️  SEÑAL: BEARISH")
        else:
            print("  ➡️  SEÑAL: NEUTRAL")
        
        # Cache stats
        print(f"\n💾 ESTADÍSTICAS DE CACHE:")
        stats = aggregator.get_cache_stats()
        print(f"  - Entradas válidas: {stats['valid_entries']}")
        print(f"  - Entradas expiradas: {stats['expired_entries']}")
        print(f"  - Tamaño: {stats['size_mb']} MB")
        
        return True
        
    except Exception as exc:
        print(f"\n❌ Error al compilar datos: {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_sentiment_analyzer():
    """Prueba el Sentiment Analyzer (sin GPT)."""
    print("\n" + "=" * 60)
    print("PRUEBA: Sentiment Analyzer (Sin GPT)")
    print("=" * 60)
    
    aggregator = DataAggregator(cache_db_path="data/test_cache.db")
    analyzer = SentimentAnalyzer(aggregator, use_gpt=False)
    
    symbol = "BTCUSDT"
    print(f"\n🤖 Analizando mercado para {symbol}...")
    
    try:
        result = analyzer.analyze_market(symbol)
        
        print(f"\n✅ Análisis completado!\n")
        
        # Análisis Local
        local = result["local_analysis"]
        print("🔍 ANÁLISIS LOCAL (Sin GPT):")
        print(f"  - Acción recomendada: {local['action']}")
        print(f"  - Confianza: {local['confidence']}%")
        print(f"  - Nivel de riesgo: {local['risk_level']}")
        print(f"  - Condiciones de mercado: {local['market_conditions']}")
        print(f"  - Score promedio: {local['average_signal_score']:.2f}")
        
        print(f"\n📊 SEÑALES DETECTADAS ({local['signal_count']}):")
        for i, signal in enumerate(local['signals'][:10], 1):
            print(f"  {i}. {signal}")
        
        # Recomendación Final
        final = result["final_recommendation"]
        print(f"\n🎯 RECOMENDACIÓN FINAL:")
        print(f"  - Acción: {final['action']}")
        print(f"  - Confianza: {final['confidence']}%")
        print(f"  - Riesgo: {final['risk_level']}")
        print(f"  - GPT usado: {'Sí' if final['gpt_enhanced'] else 'No'}")
        
        # Decision visual
        print(f"\n{'='*60}")
        if final['action'] == 'BUY' and final['confidence'] >= 70:
            print("✅ SEÑAL DE COMPRA FUERTE")
        elif final['action'] == 'BUY':
            print("⚠️  SEÑAL DE COMPRA DÉBIL")
        elif final['action'] == 'SELL' and final['confidence'] >= 70:
            print("❌ SEÑAL DE VENTA FUERTE")
        elif final['action'] == 'SELL':
            print("⚠️  SEÑAL DE VENTA DÉBIL")
        else:
            print("⏸️  MANTENER - ESPERAR MEJOR OPORTUNIDAD")
        print(f"{'='*60}")
        
        return True
        
    except Exception as exc:
        print(f"\n❌ Error al analizar: {exc}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Ejecuta todas las pruebas."""
    print("\n🚀 INICIANDO PRUEBAS DEL SISTEMA DE SENTIMENT ANALYSIS\n")
    
    results = []
    
    # Test 1: Data Aggregator
    results.append(test_data_aggregator())
    
    # Test 2: Sentiment Analyzer
    results.append(test_sentiment_analyzer())
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE PRUEBAS")
    print("=" * 60)
    print(f"✅ Pruebas exitosas: {sum(results)}/{len(results)}")
    print(f"❌ Pruebas fallidas: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 ¡TODAS LAS PRUEBAS PASARON EXITOSAMENTE!")
        print("\n💡 El sistema está listo para usar. Comandos sugeridos:")
        print("   - Solo técnico: python src/main.py --symbol BTCUSDT --duration 60 --no-sentiment")
        print("   - Con sentiment:  python src/main.py --symbol BTCUSDT --duration 60")
        print("   - Con GPT:       python src/main.py --symbol BTCUSDT --duration 60 --use-gpt")
    else:
        print("\n⚠️  Algunas pruebas fallaron. Revisa los errores arriba.")
    
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()

