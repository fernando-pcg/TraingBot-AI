# 🛠️ Herramientas Existentes - Guía de Reutilización

## 📋 Propósito de Este Documento

Este documento es una **referencia rápida** de todas las herramientas y componentes ya implementados en el bot. **ANTES de crear código nuevo, consulta aquí para reutilizar lo existente.**

---

## ✅ COMPONENTES IMPLEMENTADOS Y LISTOS PARA USAR

### 1. 📊 Data Sources - Sistema Completo de Análisis de Mercado

**Ubicación:** `data_sources/`

#### 1.1 DataAggregator (`data_aggregator.py`)
**✅ IMPLEMENTADO - USAR EN VEZ DE CREAR NUEVO**

Compila datos de múltiples fuentes en un solo lugar.

```python
from data_sources import DataAggregator

aggregator = DataAggregator(cache_db_path="data/cache.db")
data = aggregator.get_compiled_data("BTCUSDT")

# Retorna CompiledMarketData con:
print(data.coin_metrics.current_price)           # Precio actual
print(data.coin_metrics.price_change_24h)        # Cambio 24h
print(data.coin_metrics.volume_24h)              # Volumen
print(data.market_sentiment.fear_greed_index)    # Fear & Greed
print(data.global_market.btc_dominance)          # Dominancia BTC
print(data.trending_coins)                       # Coins trending
print(data.compiled_score)                       # Score agregado -1 a 1
```

**Fuentes de datos incluidas:**
- ✅ CoinGecko (precios, market cap, trending)
- ✅ CryptoCompare (noticias, datos sociales)
- ✅ Fear & Greed Index
- ✅ Global market data

---

#### 1.2 SentimentAnalyzer (`sentiment_analyzer.py`)
**✅ IMPLEMENTADO - USAR PARA ANÁLISIS DE MERCADO**

Analiza condiciones de mercado y genera recomendaciones.

```python
from data_sources import DataAggregator, SentimentAnalyzer

aggregator = DataAggregator()
analyzer = SentimentAnalyzer(
    data_aggregator=aggregator,
    use_gpt=False  # Opcional: True si tienes OpenAI API key
)

result = analyzer.analyze_market("ETHUSDT")

# Resultado incluye:
print(result["final_recommendation"]["action"])      # BUY/SELL/HOLD
print(result["final_recommendation"]["confidence"])  # 0-100
print(result["final_recommendation"]["risk_level"])  # LOW/MEDIUM/HIGH
print(result["local_analysis"]["signals"])           # Lista de señales detectadas
print(result["compiled_data"])                       # Todos los datos agregados
```

**Capacidades:**
- ✅ Análisis de momentum de precio
- ✅ Evaluación de volumen vs market cap
- ✅ Interpretación de Fear & Greed Index
- ✅ Análisis de mercado global
- ✅ Sentiment de noticias (keyword-based)
- ✅ Detección de trending coins
- ✅ GPT opcional para casos ambiguos
- ✅ Cálculo de nivel de riesgo

---

#### 1.3 CoinGeckoClient (`coingecko_client.py`)
**✅ IMPLEMENTADO - API GRATUITA**

```python
from data_sources.coingecko_client import CoinGeckoClient

client = CoinGeckoClient()

# Precio simple
price = client.get_coin_price("bitcoin")

# Datos completos
data = client.get_coin_market_data("ethereum")

# Datos globales
global_data = client.get_global_market_data()

# Trending
trending = client.get_trending_coins()
```

---

#### 1.4 FearGreedClient (`fear_greed_client.py`)
**✅ IMPLEMENTADO - API GRATUITA**

```python
from data_sources.fear_greed_client import FearGreedClient

client = FearGreedClient()

# Índice actual
current = client.get_current_index()
print(current["value"])  # 0-100

# Score normalizado para trading
score = client.get_sentiment_score()  # -1 a 1

# Interpretación
interpretation = client.interpret_index(45)
print(interpretation["classification"])  # Fear/Greed/etc
print(interpretation["action_bias"])     # bullish/bearish
```

---

#### 1.5 CacheManager (`cache_manager.py`)
**✅ IMPLEMENTADO - REDUCE LLAMADAS A APIs EN ~80%**

Sistema automático de caché con SQLite. Ya integrado en todos los clientes, pero también puede usarse manualmente:

```python
from data_sources.cache_manager import CacheManager

cache = CacheManager("data/cache.db")

# Guardar
cache.set("my_key", {"data": "value"}, ttl=300)

# Obtener
data = cache.get("my_key")

# Estadísticas
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.1f}%")
```

---

### 2. 🎯 Core Trading Components

#### 2.1 TradingEngine (`src/trading_engine.py`)
**✅ IMPLEMENTADO - MOTOR PRINCIPAL DE TRADING**

Ya incluye:
- ✅ Integración con SentimentAnalyzer
- ✅ Análisis multi-timeframe
- ✅ Detección de régimen de mercado
- ✅ Mean reversion y momentum strategies
- ✅ Combinación de señales técnicas + sentiment
- ✅ Position sizing dinámico (Kelly Criterion)
- ✅ Adaptive stop-loss basado en ATR
- ✅ Trailing stops
- ✅ Gestión de posiciones LONG y SHORT
- ✅ Reporting avanzado de performance

**No necesitas crear un nuevo trading engine, úsalo:**

```python
from src.trading_engine import TradingEngine

engine = TradingEngine(
    config=config,
    client=binance_client,
    strategy=strategy,
    risk_manager=risk_manager,
    state_manager=state_manager,
    loggers=loggers,
    use_sentiment_analysis=True,  # ← Activa sentiment
    use_gpt=False,                # ← Opcional
)

engine.run(
    symbol="BTCUSDT",
    duration_minutes=600,
    interval_seconds=45
)
```

---

#### 2.2 Strategy (`src/strategy.py`)
**✅ IMPLEMENTADO - ANÁLISIS TÉCNICO COMPLETO**

Incluye:
- ✅ RSI, MACD, Bollinger Bands, Stochastic, ADX
- ✅ Multi-timeframe analysis
- ✅ Detección de mercado lateral (ranging)
- ✅ Pattern analysis
- ✅ Scoring system con confianza
- ✅ Umbrales configurables (modo agresivo/conservador)

```python
from src.strategy import Strategy

# Modo conservador
strategy = Strategy(
    min_volume=0,
    rsi_bounds=(35, 65),
    adx_trend_threshold=20,
    atr_volatility_ceiling=0.02,
)

# Modo agresivo
aggressive_strategy = Strategy(
    min_volume=0,
    rsi_bounds=(25, 75),
    adx_trend_threshold=12,
    atr_volatility_ceiling=0.04,
)

signal = strategy.generate_signal(df, "BTCUSDT", timeframe_summaries)
```

---

#### 2.3 RiskManager (`src/risk_manager.py`)
**✅ IMPLEMENTADO - GESTIÓN DE RIESGO AVANZADA**

Capacidades:
- ✅ Position sizing básico y dinámico (Kelly)
- ✅ Adaptive stop-loss basado en ATR
- ✅ Trailing stops
- ✅ Control de exposición máxima
- ✅ Daily loss limits con pausa automática
- ✅ Drawdown tracking con circuit breaker

```python
from src.risk_manager import RiskManager

risk_manager = RiskManager(
    max_daily_loss_pct=0.08,
    max_exposure_pct=0.5,
)

# Position sizing básico
size = risk_manager.calculate_position_size(
    capital=1000,
    risk_percent=0.02,
    stop_loss_pct=0.01
)

# Position sizing dinámico (Kelly)
size = risk_manager.calculate_dynamic_position_size(
    capital=1000,
    win_rate=0.65,
    avg_win=15,
    avg_loss=-8,
    stop_loss_pct=0.01,
    volatility=0.02
)

# Stop loss adaptativo
sl = risk_manager.calculate_adaptive_stop_loss(
    entry_price=100,
    atr=2.5,
    base_stop_pct=0.01
)
```

---

#### 2.4 MarketRegimeDetector (`src/market_regime.py`)
**✅ IMPLEMENTADO - DETECTA TIPO DE MERCADO**

Detecta si el mercado está en:
- TRENDING_UP
- TRENDING_DOWN
- RANGING (lateral)
- VOLATILE

```python
from src.market_regime import MarketRegimeDetector

detector = MarketRegimeDetector()
regime_analysis = detector.detect_regime(df, indicators, timeframe_summaries)

print(regime_analysis.regime)           # Tipo de mercado
print(regime_analysis.confidence)       # 0-1
print(regime_analysis.recommendation)   # "momentum", "mean_reversion", "avoid"
```

---

#### 2.5 MeanReversionStrategy (`src/mean_reversion_strategy.py`)
**✅ IMPLEMENTADO - ESTRATEGIA PARA MERCADOS LATERALES**

Automáticamente activada por TradingEngine cuando detecta ranging market.

```python
from src.mean_reversion_strategy import MeanReversionStrategy

mr_strategy = MeanReversionStrategy(
    support_threshold=0.02,
    resistance_threshold=0.02
)

signal = mr_strategy.evaluate(symbol, current_price, indicators, patterns, timeframes)
```

---

#### 2.6 MultiTimeframeAnalyzer (`src/multi_timeframe.py`)
**✅ IMPLEMENTADO - ANÁLISIS EN MÚLTIPLES TIMEFRAMES**

```python
from src.multi_timeframe import MultiTimeframeAnalyzer

analyzer = MultiTimeframeAnalyzer(
    client=binance_client,
    intervals=("5m", "15m", "1h"),
    candle_limit=200
)

summaries = analyzer.fetch("BTCUSDT")
for tf in summaries:
    print(f"{tf.interval}: {tf.trend_pct:+.2f}%")
```

---

### 3. 📈 Indicators & Patterns

#### 3.1 Indicators (`src/indicators.py`)
**✅ IMPLEMENTADO - 10+ INDICADORES TÉCNICOS**

```python
from src.indicators import calculate_indicators

indicators = calculate_indicators(df)

# Acceder a indicadores
print(indicators.rsi)
print(indicators.macd, indicators.macd_signal, indicators.macd_histogram)
print(indicators.bollinger_upper, indicators.bollinger_middle, indicators.bollinger_lower)
print(indicators.atr)
print(indicators.adx)
print(indicators.stochastic_k, indicators.stochastic_d)
```

---

#### 3.2 Patterns (`src/patterns.py`)
**✅ IMPLEMENTADO - DETECCIÓN DE PATRONES**

```python
from src.patterns import analyze_patterns

patterns = analyze_patterns(df)

print(patterns.bullish)             # Lista de patrones alcistas
print(patterns.bearish)             # Lista de patrones bajistas
print(patterns.support)             # Nivel de soporte
print(patterns.resistance)          # Nivel de resistencia
print(patterns.bullish_divergence)  # True/False
print(patterns.bearish_divergence)  # True/False
```

---

### 4. 📊 Performance & Metrics

#### 4.1 PerformanceAnalyzer (`src/performance_metrics.py`)
**✅ IMPLEMENTADO - MÉTRICAS COMPLETAS**

```python
from src.performance_metrics import PerformanceAnalyzer

metrics = PerformanceAnalyzer.analyze_trades(
    trades=trades_df,
    start_capital=1000,
    duration_minutes=600
)

# Métricas incluidas:
# - Total trades, win rate, profit factor
# - Sharpe ratio, max drawdown
# - Average win/loss, best/worst trades
# - Trades per hour, hourly/daily projections
# - Consecutive wins/losses
# - Y muchas más...

PerformanceAnalyzer.print_performance_report(metrics, start_capital, end_capital)
```

---

### 5. 🔧 Utilities

#### 5.1 StateManager (`src/state_manager.py`)
**✅ IMPLEMENTADO - PERSISTENCIA DE ESTADO**

```python
from src.state_manager import StateManager

state_manager = StateManager(
    state_file=Path("state/state.json"),
    trades_history_file=Path("state/trades.json")
)

# Guardar trade
state_manager.append_trade(trade_record)

# Cargar estado previo
state = state_manager.load()
```

---

#### 5.2 Logger System (`src/logger.py`)
**✅ IMPLEMENTADO - LOGS CATEGORIZADOS**

```python
from src.logger import setup_category_loggers

loggers = setup_category_loggers(Path("logs"))

loggers["system"].info("System message")
loggers["trades"].info("Trade executed")
loggers["errors"].error("Error occurred")
loggers["api_calls"].debug("API called")
```

---

## 🚀 SCRIPTS LISTOS PARA USAR

### 1. Script de Modo Agresivo (`scripts/aggressive_trading.py`)
**✅ IMPLEMENTADO**

```bash
# Ejecutar sesión agresiva de 8 horas (default)
python scripts/aggressive_trading.py --symbol ETHUSDT --duration 480

# Con GPT
python scripts/aggressive_trading.py --symbol ETHUSDT --duration 480 --use-gpt

# Cambiar intervalo
python scripts/aggressive_trading.py --symbol ETHUSDT --duration 480 --interval 30
```

---

### 2. Script Optimizado 10h (`scripts/run_optimized_10h.py`)
**✅ RECIÉN IMPLEMENTADO**

**REUTILIZA:**
- DataAggregator para datos de mercado
- SentimentAnalyzer para análisis
- TradingEngine para ejecutar

```bash
python scripts/run_optimized_10h.py
```

**Flujo:**
1. Analiza 8 monedas principales (BTCUSDT, ETHUSDT, etc.)
2. Usa SentimentAnalyzer para evaluar cada una
3. Calcula un "opportunity score" considerando:
   - Momentum de precio
   - Volumen/liquidez
   - Sentiment score
   - Nivel de riesgo
   - Confianza del análisis
4. Selecciona la mejor moneda
5. Ajusta parámetros según nivel de riesgo
6. Ejecuta TradingEngine por 10 horas

---

### 3. Otros Scripts Disponibles

```bash
# Modo conservador (modo estándar)
python src/main.py --symbol BTCUSDT --duration 60

# Ver resumen de performance
python scripts/ver_resumen.py

# Test de APIs
python tests/test_apis_config.py

# Test de sentiment
python tests/test_sentiment_analysis.py
```

---

## 📖 CÓMO REUTILIZAR EN NUEVOS SCRIPTS

### Ejemplo: Script para Analizar Múltiples Monedas

```python
"""Ejemplo de cómo reutilizar componentes existentes."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_sources import DataAggregator, SentimentAnalyzer

def main():
    # 1. Inicializar componentes existentes
    aggregator = DataAggregator(cache_db_path="data/cache.db")
    analyzer = SentimentAnalyzer(
        data_aggregator=aggregator,
        use_gpt=False
    )
    
    # 2. Analizar monedas
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]
    
    for symbol in symbols:
        # Usa SentimentAnalyzer (no reinventes la rueda)
        result = analyzer.analyze_market(symbol)
        
        # Accede a datos compilados
        coin = result["compiled_data"].coin_metrics
        rec = result["final_recommendation"]
        
        print(f"{symbol}:")
        print(f"  Precio: ${coin.current_price:,.2f}")
        print(f"  Acción: {rec['action']} ({rec['confidence']}%)")
        print(f"  Riesgo: {rec['risk_level']}")
        print()

if __name__ == "__main__":
    main()
```

---

### Ejemplo: Script para Backtesting (Futuro)

```python
"""Ejemplo de estructura para backtesting usando componentes existentes."""

from src.strategy import Strategy
from src.indicators import calculate_indicators
from src.patterns import analyze_patterns
import pandas as pd

def backtest_strategy(df: pd.DataFrame):
    # Reutiliza Strategy existente
    strategy = Strategy(
        min_volume=0,
        rsi_bounds=(35, 65),
        adx_trend_threshold=20,
        atr_volatility_ceiling=0.02,
    )
    
    trades = []
    
    # Simula trading sobre datos históricos
    for i in range(100, len(df)):
        window = df.iloc[i-100:i]
        signal = strategy.generate_signal(window, "BTCUSDT")
        
        if signal:
            trades.append({
                "timestamp": df.iloc[i]["timestamp"],
                "action": signal.action,
                "price": df.iloc[i]["close"],
                "confidence": signal.confidence
            })
    
    return pd.DataFrame(trades)
```

---

## ⚠️ ANTES DE CREAR CÓDIGO NUEVO

### Checklist:

- [ ] ¿Necesito analizar datos de mercado? → **USA DataAggregator**
- [ ] ¿Necesito análisis de sentiment? → **USA SentimentAnalyzer**
- [ ] ¿Necesito ejecutar trading? → **USA TradingEngine**
- [ ] ¿Necesito análisis técnico? → **USA Strategy**
- [ ] ¿Necesito gestión de riesgo? → **USA RiskManager**
- [ ] ¿Necesito indicadores? → **USA calculate_indicators()**
- [ ] ¿Necesito patrones? → **USA analyze_patterns()**
- [ ] ¿Necesito detectar tipo de mercado? → **USA MarketRegimeDetector**
- [ ] ¿Necesito multi-timeframe? → **USA MultiTimeframeAnalyzer**
- [ ] ¿Necesito métricas de performance? → **USA PerformanceAnalyzer**

---

## 📚 Documentación Adicional

- **FASE3_RESUMEN.md**: Detalles completos de integración de datos
- **QUICK_START.md**: Inicio rápido en 5 minutos
- **FASE3_SETUP_GUIDE.md**: Configuración detallada de APIs
- **INTEGRATION_COMPLETE.md**: Resumen de integración completa
- **trading-bot-evolution.plan.md**: Plan de evolución completo

---

## 🎯 Próximas Implementaciones Sugeridas

### Usando componentes existentes:

1. **Backtesting System**
   - Usa: Strategy, indicators, patterns
   - Nuevo: backtesting_engine.py

2. **Multi-Symbol Trading**
   - Usa: TradingEngine, SentimentAnalyzer
   - Nuevo: multi_symbol_orchestrator.py

3. **Alertas por Telegram**
   - Usa: SentimentAnalyzer para detectar oportunidades
   - Nuevo: telegram_bot.py

4. **Dashboard Web**
   - Backend: FastAPI
   - Consume: logs, state files, usa components para live data
   - Nuevo: api/ folder

5. **Machine Learning Integration**
   - Features: Usa indicators, patterns, sentiment data
   - Nuevo: ml/ folder

---

## 💡 Principio Fundamental

> **"No reinventes la rueda. Reutiliza, compone, extiende."**

Todos los componentes están diseñados para ser:
- ✅ Reutilizables
- ✅ Componibles
- ✅ Extensibles
- ✅ Testeables

**Antes de escribir código nuevo, pregúntate:**
*"¿Ya existe un componente que haga esto o parte de esto?"*

---

Última actualización: 19 de Octubre, 2025

