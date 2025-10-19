"""Script de verificación de configuración de APIs - FASE 3."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

# Cargar variables de entorno desde .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ Archivo .env cargado correctamente\n")
except ImportError:
    print("⚠️  python-dotenv no instalado, usando solo variables de entorno del sistema\n")
except Exception as e:
    print(f"⚠️  Error cargando .env: {e}\n")


def test_coingecko():
    """Test CoinGecko API (100% gratis)."""
    print("\n" + "=" * 60)
    print("🦎 COINGECKO API - Prueba")
    print("=" * 60)
    print("Estado: GRATUITA - No requiere API key")
    
    try:
        from data_sources import CoinGeckoClient
        
        client = CoinGeckoClient()
        
        # Test 1: Get Bitcoin price
        print("\n📊 Obteniendo precio de Bitcoin...")
        btc_data = client.get_coin_price("bitcoin")
        btc_price = btc_data.get("bitcoin", {}).get("usd", 0)
        btc_change = btc_data.get("bitcoin", {}).get("usd_24h_change", 0)
        
        print(f"✅ Precio BTC: ${btc_price:,.2f}")
        print(f"✅ Cambio 24h: {btc_change:+.2f}%")
        
        # Test 2: Global market data
        print("\n🌍 Obteniendo datos globales...")
        global_data = client.get_global_market_data()
        data = global_data.get("data", {})
        total_mcap = data.get("total_market_cap", {}).get("usd", 0)
        btc_dominance = data.get("market_cap_percentage", {}).get("btc", 0)
        
        print(f"✅ Market Cap Total: ${total_mcap:,.0f}")
        print(f"✅ Dominancia BTC: {btc_dominance:.2f}%")
        
        # Test 3: Trending coins
        print("\n🔥 Obteniendo trending coins...")
        trending = client.get_trending_coins()
        if trending:
            print(f"✅ Top 3 trending: {', '.join([c['item']['symbol'] for c in trending[:3]])}")
        
        print("\n✅ COINGECKO: FUNCIONANDO CORRECTAMENTE")
        return True
        
    except Exception as exc:
        print(f"\n❌ COINGECKO: ERROR - {exc}")
        print("   Verifica tu conexión a internet")
        return False


def test_cryptocompare():
    """Test CryptoCompare API (gratuita con registro)."""
    print("\n" + "=" * 60)
    print("🔷 CRYPTOCOMPARE API - Prueba")
    print("=" * 60)
    
    api_key = os.getenv("CRYPTOCOMPARE_API_KEY")
    
    if not api_key:
        print("⚠️  API Key no configurada")
        print("\n📝 Pasos para configurar:")
        print("   1. Registrarse en: https://www.cryptocompare.com/cryptopian/api-keys")
        print("   2. Crear una API key (gratis)")
        print("   3. Configurar variable de entorno:")
        print("      Windows (PowerShell): $env:CRYPTOCOMPARE_API_KEY = 'tu-key'")
        print("      Windows (CMD): set CRYPTOCOMPARE_API_KEY=tu-key")
        print("      Linux/Mac: export CRYPTOCOMPARE_API_KEY='tu-key'")
        print("\n❌ CRYPTOCOMPARE: NO CONFIGURADA (OPCIONAL)")
        return False
    
    try:
        from data_sources import CryptoCompareClient
        
        client = CryptoCompareClient(api_key=api_key)
        
        # Test 1: Get news
        print("\n📰 Obteniendo noticias...")
        news = client.get_news(categories="BTC,ETH", lang="EN")
        if news:
            print(f"✅ Noticias obtenidas: {len(news)} artículos")
            print(f"✅ Última noticia: {news[0].get('title', 'N/A')[:60]}...")
        
        # Test 2: Get prices
        print("\n💰 Obteniendo precios...")
        prices = client.get_price_multi(["BTC", "ETH"], ["USD"])
        if prices:
            print(f"✅ BTC: ${prices.get('BTC', {}).get('USD', 0):,.2f}")
            print(f"✅ ETH: ${prices.get('ETH', {}).get('USD', 0):,.2f}")
        
        print("\n✅ CRYPTOCOMPARE: FUNCIONANDO CORRECTAMENTE")
        return True
        
    except Exception as exc:
        print(f"\n❌ CRYPTOCOMPARE: ERROR - {exc}")
        print("   Verifica que tu API key sea válida")
        return False


def test_fear_greed():
    """Test Fear & Greed Index (100% gratis)."""
    print("\n" + "=" * 60)
    print("😱 FEAR & GREED INDEX - Prueba")
    print("=" * 60)
    print("Estado: GRATUITA - No requiere API key")
    
    try:
        from data_sources import FearGreedClient
        
        client = FearGreedClient()
        
        # Test 1: Current index
        print("\n📊 Obteniendo índice actual...")
        current = client.get_current_index()
        
        value = int(current.get("value", 50))
        classification = current.get("value_classification", "Unknown")
        
        print(f"✅ Índice actual: {value}/100")
        print(f"✅ Clasificación: {classification}")
        
        # Test 2: Sentiment score
        score = client.get_sentiment_score()
        print(f"✅ Score normalizado: {score:.2f} (-1 a 1)")
        
        # Test 3: Interpretation
        interpretation = client.interpret_index(value)
        print(f"✅ Recomendación: {interpretation['recommendation']}")
        
        print("\n✅ FEAR & GREED: FUNCIONANDO CORRECTAMENTE")
        return True
        
    except Exception as exc:
        print(f"\n❌ FEAR & GREED: ERROR - {exc}")
        print("   Verifica tu conexión a internet")
        return False


def test_openai():
    """Test OpenAI GPT (opcional, de pago)."""
    print("\n" + "=" * 60)
    print("🤖 OPENAI GPT - Prueba")
    print("=" * 60)
    
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("⚠️  API Key no configurada (OPCIONAL)")
        print("\n📝 Pasos para configurar (si quieres usar GPT):")
        print("   1. Registrarse en: https://platform.openai.com/api-keys")
        print("   2. Comprar créditos (mínimo $5)")
        print("   3. Crear una API key")
        print("   4. Configurar variable de entorno:")
        print("      Windows (PowerShell): $env:OPENAI_API_KEY = 'sk-tu-key'")
        print("      Windows (CMD): set OPENAI_API_KEY=sk-tu-key")
        print("      Linux/Mac: export OPENAI_API_KEY='sk-tu-key'")
        print("\n💡 GPT es OPCIONAL - El bot funciona sin él")
        print("   Solo mejora análisis de señales ambiguas")
        print("\n⚠️  OPENAI: NO CONFIGURADA (OPCIONAL)")
        return None  # None = no configurada pero no es error
    
    try:
        import openai
        
        client = openai.OpenAI(api_key=api_key)
        
        print("\n🧪 Probando conexión con GPT-5...")
        response = client.chat.completions.create(
            model="gpt-5",
            messages=[
                {"role": "user", "content": "Responde solo 'OK' si funciono correctamente."}
            ],
            max_tokens=10,
        )
        
        result = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        
        print(f"✅ Respuesta: {result}")
        print(f"✅ Tokens usados: {tokens_used}")
        print(f"✅ Costo aproximado: ${tokens_used * 0.00015 / 1000:.6f}")
        
        print("\n✅ OPENAI: FUNCIONANDO CORRECTAMENTE")
        return True
        
    except Exception as exc:
        print(f"\n❌ OPENAI: ERROR - {exc}")
        print("   Verifica:")
        print("   - Tu API key sea válida")
        print("   - Tengas créditos disponibles")
        print("   - openai package instalado: pip install openai")
        return False


def test_cache_system():
    """Test del sistema de caché."""
    print("\n" + "=" * 60)
    print("💾 SISTEMA DE CACHÉ - Prueba")
    print("=" * 60)
    
    try:
        from data_sources import CacheManager
        
        cache = CacheManager(db_path="data/test_cache.db")
        
        # Test 1: Set and get
        print("\n📝 Probando escritura/lectura...")
        cache.set("test_key", {"data": "test_value"}, ttl=60)
        value = cache.get("test_key")
        
        if value and value.get("data") == "test_value":
            print("✅ Escritura/lectura funcional")
        else:
            raise ValueError("Cache no retornó el valor correcto")
        
        # Test 2: Stats
        print("\n📊 Obteniendo estadísticas...")
        stats = cache.get_stats()
        print(f"✅ Entradas totales: {stats['total_entries']}")
        print(f"✅ Entradas válidas: {stats['valid_entries']}")
        print(f"✅ Tamaño: {stats['size_mb']} MB")
        
        # Test 3: Cleanup
        print("\n🧹 Limpiando cache expirado...")
        deleted = cache.clear_expired()
        print(f"✅ Entradas eliminadas: {deleted}")
        
        print("\n✅ CACHÉ: FUNCIONANDO CORRECTAMENTE")
        return True
        
    except Exception as exc:
        print(f"\n❌ CACHÉ: ERROR - {exc}")
        return False


def test_full_integration():
    """Test de integración completa."""
    print("\n" + "=" * 60)
    print("🔗 INTEGRACIÓN COMPLETA - Prueba")
    print("=" * 60)
    
    try:
        from data_sources import DataAggregator, SentimentAnalyzer
        
        print("\n🚀 Inicializando sistema...")
        aggregator = DataAggregator(cache_db_path="data/test_cache.db")
        analyzer = SentimentAnalyzer(aggregator, use_gpt=False)
        
        print("✅ Sistema inicializado")
        
        symbol = "BTCUSDT"
        print(f"\n📊 Analizando {symbol}...")
        
        result = analyzer.analyze_market(symbol)
        
        print(f"\n✅ Análisis completado!")
        print(f"\n🎯 RESULTADO:")
        print(f"   Acción: {result['final_recommendation']['action']}")
        print(f"   Confianza: {result['final_recommendation']['confidence']}%")
        print(f"   Riesgo: {result['final_recommendation']['risk_level']}")
        print(f"   Score compilado: {result['compiled_data'].compiled_score:.2f}")
        
        # Mostrar algunas señales
        signals = result['local_analysis']['signals'][:3]
        print(f"\n📈 Señales principales:")
        for i, signal in enumerate(signals, 1):
            print(f"   {i}. {signal}")
        
        print("\n✅ INTEGRACIÓN COMPLETA: FUNCIONANDO")
        return True
        
    except Exception as exc:
        print(f"\n❌ INTEGRACIÓN: ERROR - {exc}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Ejecuta todos los tests."""
    print("\n" + "🔍" * 30)
    print("VERIFICACIÓN DE CONFIGURACIÓN - FASE 3")
    print("TraingBot-AI - Sistema de Análisis de Mercado")
    print("🔍" * 30)
    
    results = {
        "CoinGecko (Gratis)": None,
        "CryptoCompare (Gratis)": None,
        "Fear & Greed (Gratis)": None,
        "OpenAI GPT (Opcional)": None,
        "Sistema de Caché": None,
        "Integración Completa": None,
    }
    
    # Ejecutar tests
    results["CoinGecko (Gratis)"] = test_coingecko()
    results["CryptoCompare (Gratis)"] = test_cryptocompare()
    results["Fear & Greed (Gratis)"] = test_fear_greed()
    results["OpenAI GPT (Opcional)"] = test_openai()
    results["Sistema de Caché"] = test_cache_system()
    
    # Solo test de integración si las APIs básicas funcionan
    if results["CoinGecko (Gratis)"] and results["Fear & Greed (Gratis)"]:
        results["Integración Completa"] = test_full_integration()
    else:
        print("\n⚠️  Saltando test de integración (APIs básicas no disponibles)")
    
    # Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN FINAL")
    print("=" * 60)
    
    for name, status in results.items():
        if status is True:
            print(f"✅ {name}: FUNCIONANDO")
        elif status is False:
            print(f"❌ {name}: ERROR")
        elif status is None:
            print(f"⚠️  {name}: NO CONFIGURADO")
    
    # Determinar estado general
    critical_apis = [
        results["CoinGecko (Gratis)"],
        results["Fear & Greed (Gratis)"],
        results["Sistema de Caché"],
    ]
    
    print("\n" + "=" * 60)
    
    if all(critical_apis):
        print("🎉 ¡SISTEMA LISTO PARA USAR!")
        print("\n💡 Comandos disponibles:")
        print("   1. Solo técnico:     python src/main.py --symbol BTCUSDT --no-sentiment")
        print("   2. Con sentiment:    python src/main.py --symbol BTCUSDT")
        
        if results["OpenAI GPT (Opcional)"] is True:
            print("   3. Con GPT:          python src/main.py --symbol BTCUSDT --use-gpt")
        else:
            print("   3. Con GPT:          (Configurar OpenAI primero)")
        
        if results["CryptoCompare (Gratis)"] is False:
            print("\n⚠️  RECOMENDACIÓN: Configura CryptoCompare para acceder a noticias")
            print("   Visita: https://www.cryptocompare.com/cryptopian/api-keys")
        
    else:
        print("⚠️  CONFIGURACIÓN INCOMPLETA")
        print("\nAPIs críticas faltantes:")
        if not results["CoinGecko (Gratis)"]:
            print("   ❌ CoinGecko - Verifica tu conexión a internet")
        if not results["Fear & Greed (Gratis)"]:
            print("   ❌ Fear & Greed - Verifica tu conexión a internet")
        if not results["Sistema de Caché"]:
            print("   ❌ Sistema de Caché - Problema con SQLite")
    
    print("=" * 60)
    print("\n📚 Documentación completa: FASE3_SETUP_GUIDE.md\n")


if __name__ == "__main__":
    main()

