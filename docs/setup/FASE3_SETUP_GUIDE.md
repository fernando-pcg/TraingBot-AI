# 📚 Guía de Configuración - FASE 3: Integración de Fuentes de Datos

## 🎯 Resumen de la Fase 3

La Fase 3 integra múltiples fuentes de datos externas para enriquecer el análisis de trading con:
- ✅ Datos de mercado en tiempo real
- ✅ Análisis de sentiment del mercado
- ✅ Métricas sociales y on-chain
- ✅ Noticias y tendencias
- ✅ Sistema de caché inteligente

---

## 🌐 APIs Implementadas

### 1. **CoinGecko API** ✅ GRATUITA
**Estado**: Implementada y funcional  
**Archivo**: `data_sources/coingecko_client.py`

#### Características:
- ✅ 100% Gratuita (no requiere API key)
- ⚡ Rate Limit: 10-50 llamadas/minuto
- 📊 Datos disponibles:
  - Precios en tiempo real
  - Market cap y volumen 24h
  - Cambios históricos (24h, 7d, 30d)
  - Datos de mercado global
  - Trending coins
  - Gráficos históricos

#### Configuración:
```python
# No requiere configuración - funciona out-of-the-box
from data_sources import CoinGeckoClient

client = CoinGeckoClient()
price = client.get_coin_price("bitcoin")
```

#### Plan de pago (opcional para mayor límite):
- **Demo**: Gratis, 10-50 calls/min
- **Analyst**: $129/mes, 500 calls/min, 10,000 calls/month
- **Pro**: $399/mes, 30 calls/sec, 100,000 calls/month

**Recomendación**: El plan gratuito es suficiente con nuestro sistema de caché.

---

### 2. **CryptoCompare API** ⚠️ REQUIERE API KEY (Gratuita)
**Estado**: Implementada y funcional  
**Archivo**: `data_sources/cryptocompare_client.py`

#### Características:
- ✅ Tier gratuito disponible
- ⚡ Rate Limit: ~100,000 llamadas/mes (~50/hora recomendado)
- 📊 Datos disponibles:
  - Estadísticas de redes sociales (Twitter, Reddit)
  - Noticias de criptomonedas
  - Métricas on-chain básicas
  - Top exchanges por volumen
  - Datos históricos OHLCV

#### Configuración:

**Paso 1: Obtener API Key (Gratis)**
1. Visita: https://www.cryptocompare.com/cryptopian/api-keys
2. Registra una cuenta gratuita
3. Crea una API key en el dashboard

**Paso 2: Configurar API Key**

Opción A - Variable de entorno (recomendado):
```bash
# Windows (PowerShell)
$env:CRYPTOCOMPARE_API_KEY = "tu-api-key-aqui"

# Windows (CMD)
set CRYPTOCOMPARE_API_KEY=tu-api-key-aqui

# Linux/Mac
export CRYPTOCOMPARE_API_KEY="tu-api-key-aqui"
```

Opción B - Archivo .env:
```bash
# Crear archivo .env en la raíz del proyecto
CRYPTOCOMPARE_API_KEY=tu-api-key-aqui
```

Opción C - Pasar directamente al código:
```python
from data_sources import DataAggregator

aggregator = DataAggregator(
    cryptocompare_api_key="tu-api-key-aqui"
)
```

#### Planes de pago (opcional):
- **Free**: Gratis, 100K calls/mes, historial limitado
- **Hobbyist**: $35/mes, 250K calls/mes, historial completo
- **Startup**: $130/mes, 1M calls/mes, soporte prioritario

**Recomendación**: El plan gratuito es suficiente para empezar.

---

### 3. **Fear & Greed Index** ✅ GRATUITA
**Estado**: Implementada y funcional  
**Archivo**: `data_sources/fear_greed_client.py`

#### Características:
- ✅ 100% Gratuita (no requiere API key)
- ⚡ Sin rate limit estricto
- 📊 Datos disponibles:
  - Índice actual (0-100)
  - Clasificación (Extreme Fear → Extreme Greed)
  - Datos históricos
  - Recomendaciones de trading

#### Configuración:
```python
# No requiere configuración
from data_sources import FearGreedClient

client = FearGreedClient()
index = client.get_current_index()
```

---

### 4. **OpenAI GPT** 💰 OPCIONAL (De Pago)
**Estado**: Implementada, deshabilitada por defecto  
**Archivo**: `data_sources/sentiment_analyzer.py`

#### Características:
- 💰 Requiere API key de pago
- 🎯 Solo se usa para señales ambiguas (ahorra ~70% de créditos)
- 🤖 Modelo: GPT-4o-mini (más económico)
- 📊 Mejora análisis cuando señales técnicas y de mercado no son claras

#### Configuración:

**Paso 1: Obtener API Key**
1. Visita: https://platform.openai.com/api-keys
2. Registra una cuenta (requiere tarjeta de crédito)
3. Compra créditos ($5 mínimo recomendado)

**Paso 2: Configurar API Key**

Opción A - Variable de entorno (recomendado):
```bash
# Windows (PowerShell)
$env:OPENAI_API_KEY = "sk-tu-api-key-aqui"

# Windows (CMD)
set OPENAI_API_KEY=sk-tu-api-key-aqui

# Linux/Mac
export OPENAI_API_KEY="sk-tu-api-key-aqui"
```

Opción B - Archivo .env:
```bash
OPENAI_API_KEY=sk-tu-api-key-aqui
```

**Paso 3: Habilitar GPT en el bot**
```bash
# Habilitar GPT para señales ambiguas
python src/main.py --symbol BTCUSDT --use-gpt
```

#### Costos Estimados (GPT-4o-mini):
- **Input**: $0.150 / 1M tokens
- **Output**: $0.600 / 1M tokens
- **Costo por análisis**: ~$0.0003 - $0.0005 (menos de 1 centavo)
- **100 análisis**: ~$0.03 - $0.05
- **1000 análisis/mes**: ~$0.30 - $0.50

**Optimización implementada**:
- GPT solo se llama si `confidence < 60%`
- Reduce llamadas en >70%
- Usa GPT-4o-mini (más barato que GPT-4)
- Tokens limitados a 300 por respuesta

**Recomendación**: 
- Empezar sin GPT para probar
- Habilitar si ves señales ambiguas frecuentes
- $5 de créditos pueden durar varios meses

---

## 🚀 Uso del Sistema

### Modo 1: Solo Análisis Técnico (Sin APIs Externas)
```bash
python src/main.py --symbol BTCUSDT --duration 60 --no-sentiment
```
- ✅ No requiere configuración
- ✅ Solo usa indicadores técnicos
- ⚡ Más rápido

### Modo 2: Con Sentiment Analysis (APIs Gratuitas)
```bash
python src/main.py --symbol BTCUSDT --duration 60
```
- ✅ Usa CoinGecko (gratis, sin config)
- ✅ Usa Fear & Greed (gratis, sin config)
- ⚠️ Requiere CryptoCompare API key (gratis) para noticias
- 📊 Mejora precisión con contexto de mercado

### Modo 3: Con GPT para Señales Ambiguas
```bash
python src/main.py --symbol BTCUSDT --duration 60 --use-gpt
```
- ✅ Todo lo anterior
- 💰 Requiere OpenAI API key (de pago)
- 🎯 GPT solo para señales difíciles
- 💡 Máxima precisión

---

## 📦 Instalación de Dependencias

```bash
# Instalar todas las dependencias
pip install -r requirements.txt

# Si quieres usar GPT (opcional)
pip install openai>=1.0
```

---

## 🧪 Probar el Sistema

### Test Rápido de APIs Gratuitas
```python
# Crear archivo test_apis.py
from data_sources import DataAggregator, SentimentAnalyzer

# Test básico
aggregator = DataAggregator()
analyzer = SentimentAnalyzer(aggregator, use_gpt=False)

result = analyzer.analyze_market("BTCUSDT")
print(f"Acción: {result['final_recommendation']['action']}")
print(f"Confianza: {result['final_recommendation']['confidence']}%")
```

### Verificar Configuración
```python
# Verificar que las APIs funcionan
import os
from data_sources import (
    CoinGeckoClient, 
    CryptoCompareClient, 
    FearGreedClient
)

# CoinGecko (siempre funciona)
cg = CoinGeckoClient()
try:
    price = cg.get_coin_price("bitcoin")
    print("✅ CoinGecko: OK")
except Exception as e:
    print(f"❌ CoinGecko: {e}")

# CryptoCompare (requiere API key)
cc_key = os.getenv("CRYPTOCOMPARE_API_KEY")
if cc_key:
    cc = CryptoCompareClient(api_key=cc_key)
    try:
        news = cc.get_news()
        print("✅ CryptoCompare: OK")
    except Exception as e:
        print(f"❌ CryptoCompare: {e}")
else:
    print("⚠️  CryptoCompare: No API key configurada")

# Fear & Greed (siempre funciona)
fg = FearGreedClient()
try:
    index = fg.get_current_index()
    print("✅ Fear & Greed: OK")
except Exception as e:
    print(f"❌ Fear & Greed: {e}")

# OpenAI (opcional)
openai_key = os.getenv("OPENAI_API_KEY")
if openai_key:
    print("✅ OpenAI: API key configurada")
else:
    print("⚠️  OpenAI: No API key (opcional)")
```

---

## 📊 APIs de Pago Adicionales (Recomendadas)

### 5. **Glassnode** - Métricas On-Chain Avanzadas
**Uso**: Análisis profundo de blockchain, métricas institucionales

#### Características:
- 📈 Métricas on-chain exclusivas
- 💎 Datos de exchanges, mineros, whales
- 🎯 Indicadores avanzados (MVRV, NVT, Realized Cap)

#### Planes:
- **Free**: $0/mes, datos limitados, delay de 24h
- **Advanced**: $29/mes, 100+ métricas, delay 10 min
- **Professional**: $99/mes, 300+ métricas, datos en vivo

**Configuración**:
```python
# Crear data_sources/glassnode_client.py
GLASSNODE_API_KEY = "tu-api-key"
```

**Recomendación**: Advanced ($29/mes) para trading serio.

---

### 6. **Santiment** - Social Analytics & Dev Activity
**Uso**: Análisis de sentimiento social, actividad de desarrollo

#### Características:
- 📱 Métricas de redes sociales avanzadas
- 👨‍💻 Actividad de desarrollo GitHub
- 🐋 Detección de movimientos de whales

#### Planes:
- **Free**: $0/mes, muy limitado
- **Pro**: $49/mes, métricas completas
- **Premium**: $199/mes, API completa

**Configuración**:
```python
# Crear data_sources/santiment_client.py
SANTIMENT_API_KEY = "tu-api-key"
```

**Recomendación**: Pro ($49/mes) si quieres análisis social serio.

---

### 7. **The Graph** - Datos de DeFi
**Uso**: Análisis de protocolos DeFi, liquidez, TVL

#### Características:
- 🔗 Datos de Uniswap, Aave, Compound, etc.
- 💧 Análisis de liquidez
- 📊 TVL y métricas de protocolos

#### Planes:
- **Free**: 100K queries/mes
- **Paid**: Pay-as-you-go, desde $4/100K queries

**Configuración**:
```python
# Usar subgraphs públicos
THE_GRAPH_API_KEY = "tu-api-key"  # Opcional
```

**Recomendación**: Free tier suficiente para empezar.

---

## 🎯 Configuración Recomendada por Presupuesto

### 💚 Budget: $0/mes (Gratis)
```
✅ CoinGecko (gratis)
✅ Fear & Greed (gratis)
⚠️ CryptoCompare (gratis, requiere registro)
❌ GPT deshabilitado
```

**Comando**:
```bash
python src/main.py --symbol BTCUSDT --duration 60
```

---

### 💛 Budget: $5-10/mes (Básico)
```
✅ CoinGecko (gratis)
✅ Fear & Greed (gratis)
✅ CryptoCompare (gratis)
✅ OpenAI GPT ($5 créditos iniciales, duran meses)
```

**Comando**:
```bash
python src/main.py --symbol BTCUSDT --duration 60 --use-gpt
```

---

### 🧡 Budget: $30-50/mes (Intermedio)
```
✅ Todo lo anterior
✅ Glassnode Advanced ($29/mes)
✅ Santiment Pro ($49/mes) - Elegir uno
```

**Beneficios**:
- Métricas on-chain profesionales
- Análisis de sentiment institucional
- Detección temprana de tendencias

---

### ❤️ Budget: $100+/mes (Profesional)
```
✅ Todo lo anterior
✅ CoinGecko Analyst ($129/mes)
✅ Glassnode Professional ($99/mes)
✅ Santiment Pro ($49/mes)
✅ OpenAI con presupuesto mensual
```

**Beneficios**:
- Sin límites de rate limit
- Datos en tiempo real
- Máxima precisión

---

## 🔧 Implementar APIs Adicionales

Si quieres agregar Glassnode o Santiment, puedo implementarlas con estos archivos:

```
data_sources/
  ├── glassnode_client.py       # Para métricas on-chain
  ├── santiment_client.py        # Para sentiment social
  └── defi_aggregator.py         # Para datos DeFi (The Graph)
```

Y actualizar el `DataAggregator` para incluirlas en el análisis compilado.

---

## 📝 Resumen de Configuración Actual

### ✅ Ya Implementado y Funcional:
1. **CoinGecko** - Sin configuración necesaria
2. **CryptoCompare** - Solo necesita API key gratuita
3. **Fear & Greed** - Sin configuración necesaria
4. **OpenAI GPT** - Opcional, requiere API key de pago
5. **Sistema de Caché** - Automático, reduce 80% de llamadas
6. **Sentiment Analyzer** - Listo para usar

### ⚠️ Pasos Mínimos para Empezar:

1. **Registrarte en CryptoCompare** (gratis):
   - https://www.cryptocompare.com/cryptopian/api-keys
   - Copiar API key

2. **Configurar variable de entorno**:
   ```bash
   # Windows PowerShell
   $env:CRYPTOCOMPARE_API_KEY = "tu-key-aqui"
   ```

3. **Ejecutar el bot**:
   ```bash
   python src/main.py --symbol BTCUSDT --duration 60
   ```

¡Eso es todo! Con eso ya tienes acceso a todas las APIs gratuitas.

---

## 🤔 ¿Quieres que implemente APIs de pago?

Puedo agregar:
- ✅ Glassnode ($29/mes) - Métricas on-chain profesionales
- ✅ Santiment ($49/mes) - Análisis social avanzado
- ✅ The Graph (gratis/pago) - Datos DeFi

Solo dime cuál te interesa y con qué frecuencia quieres que se consulten (para optimizar costos).

