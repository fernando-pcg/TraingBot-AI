# 🏗️ Arquitectura del Proyecto - TraingBot-AI

## 📁 Estructura Recomendada

```
TraingBot-AI/
│
├── 📂 src/                          # Código fuente principal
│   ├── __init__.py
│   ├── main.py                      # Punto de entrada
│   ├── binance_client.py            # Cliente Binance
│   ├── data_pipeline.py             # Pipeline de datos
│   ├── indicators.py                # Indicadores técnicos
│   ├── logger.py                    # Sistema de logging
│   ├── multi_timeframe.py           # Análisis multi-timeframe
│   ├── patterns.py                  # Patrones de velas
│   ├── risk_manager.py              # Gestión de riesgo
│   ├── state_manager.py             # Persistencia de estado
│   ├── strategy.py                  # Estrategia de trading
│   └── trading_engine.py            # Motor principal
│
├── 📂 data_sources/                 # APIs externas (FASE 3)
│   ├── __init__.py
│   ├── cache_manager.py             # Sistema de caché SQLite
│   ├── coingecko_client.py          # API CoinGecko
│   ├── cryptocompare_client.py      # API CryptoCompare
│   ├── fear_greed_client.py         # API Fear & Greed Index
│   ├── data_aggregator.py           # Agregador de datos
│   └── sentiment_analyzer.py        # Análisis de sentiment
│
├── 📂 config/                       # Configuración
│   ├── __init__.py
│   ├── config_loader.py             # Loader de configuración
│   └── testnet.json                 # Config de testnet
│
├── 📂 tests/                        # Scripts de prueba (NUEVO)
│   ├── test_apis_config.py          # Test de APIs
│   └── test_sentiment_analysis.py   # Test de sentiment
│
├── 📂 scripts/                      # Utilidades (NUEVO)
│   ├── ver_resumen.py               # Ver resumen de trades
│   └── run_8hours.bat               # Script de ejecución
│
├── 📂 ml/                           # Machine Learning (FASE 4 - futuro)
│   └── (vacío - reservado)
│
├── 📂 docs/                         # Documentación (NUEVO)
│   ├── QUICK_START.md
│   ├── FASE3_SETUP_GUIDE.md
│   ├── APIS_DE_PAGO_OPCIONALES.md
│   └── ARCHITECTURE.md
│
├── 📂 data/                         # Datos y caché
│   └── test_cache.db
│
├── 📂 state/                        # Estado del bot
│   └── trades.json
│
├── 📂 logs/                         # Logs del sistema
│   ├── api_calls.log
│   ├── errors.log
│   ├── system.log
│   └── trades.log
│
├── .env                             # Variables de entorno
├── .gitignore                       # Archivos ignorados por Git
├── requirements.txt                 # Dependencias Python
├── README.md                        # Documentación principal
└── LICENSE                          # Licencia del proyecto
```

## 📚 Descripción de Carpetas

### `src/` - Código Fuente Principal
Contiene toda la lógica core del bot de trading:
- **Trading Engine**: Motor principal que coordina todo
- **Strategy**: Lógica de estrategias de trading
- **Risk Manager**: Gestión de riesgo y position sizing
- **Indicators & Patterns**: Análisis técnico

### `data_sources/` - Integración con APIs Externas
Módulo separado para todas las fuentes de datos externas:
- Clientes de APIs (CoinGecko, CryptoCompare, Fear&Greed)
- Sistema de caché para optimizar llamadas
- Agregador que compila toda la información
- Sentiment analyzer con GPT opcional

### `config/` - Configuración
Archivos de configuración del bot:
- Perfiles (testnet, mainnet)
- Parámetros de trading
- Configuración de riesgo

### `tests/` - Pruebas
Scripts de testing y verificación:
- Test de APIs
- Test de componentes
- Test de integración

### `scripts/` - Utilidades
Scripts auxiliares:
- Visualización de resultados
- Scripts de ejecución
- Herramientas de mantenimiento

### `ml/` - Machine Learning (Futuro)
Reservado para Fase 4:
- Modelos de ML
- Feature engineering
- Backtesting con ML
- Optimización automática

### `docs/` - Documentación
Toda la documentación del proyecto:
- Guías de setup
- Documentación de APIs
- Arquitectura
- Tutoriales

### `data/` - Datos Persistentes
Bases de datos y caché:
- SQLite cache
- Datos históricos (futuro)

### `state/` - Estado del Bot
Estado persistente:
- Posiciones abiertas
- Historial de trades
- Configuración de runtime

### `logs/` - Registros
Logs categorizados:
- Sistema
- Trades
- API calls
- Errores

## 🗂️ Carpeta `api/` - ¿Qué hacer?

**Actualmente vacía**. Opciones:

### Opción 1: Eliminar ❌
Si no planeas exponer el bot como API REST.

### Opción 2: Usar para REST API 🌐
Si quieres exponer el bot como servicio:
```python
api/
├── __init__.py
├── app.py                  # FastAPI/Flask app
├── endpoints.py            # Endpoints REST
├── websocket.py            # WebSocket para stream
└── schemas.py              # Modelos Pydantic
```

### Opción 3: Renombrar a `integrations/` 🔄
Para futuras integraciones (Telegram bot, Discord, etc.)

**Recomendación**: Eliminar por ahora, agregar cuando sea necesario.

## 🔮 Próximas Fases

### FASE 4: Machine Learning
```
ml/
├── models/                 # Modelos entrenados
├── features/               # Feature engineering
├── training/               # Scripts de entrenamiento
├── backtesting/            # Sistema de backtesting
└── optimization/           # Optimización de hiperparámetros
```

### FASE 5: Web Dashboard
```
dashboard/
├── frontend/               # React/Vue frontend
├── backend/                # FastAPI backend
└── websockets/             # Real-time updates
```

## 🚀 Flujo de Ejecución

```
main.py
  ↓
TradingEngine
  ├→ DataPipeline (obtiene datos de Binance)
  ├→ MultiTimeframeAnalyzer (analiza múltiples timeframes)
  ├→ DataAggregator (APIs externas)
  │   ├→ CoinGeckoClient
  │   ├→ CryptoCompareClient
  │   └→ FearGreedClient
  ├→ SentimentAnalyzer (compila todo + GPT opcional)
  ├→ Strategy (genera señales)
  ├→ RiskManager (valida riesgo)
  └→ BinanceClient (ejecuta trades)
```

## 📊 Dependencias Entre Módulos

```
main.py
  │
  ├─ config/config_loader.py
  │
  ├─ src/trading_engine.py
  │   ├─ src/binance_client.py
  │   ├─ src/data_pipeline.py
  │   ├─ src/strategy.py
  │   │   ├─ src/indicators.py
  │   │   ├─ src/patterns.py
  │   │   └─ src/multi_timeframe.py
  │   ├─ src/risk_manager.py
  │   ├─ src/state_manager.py
  │   └─ data_sources/sentiment_analyzer.py
  │       └─ data_sources/data_aggregator.py
  │           ├─ data_sources/coingecko_client.py
  │           ├─ data_sources/cryptocompare_client.py
  │           ├─ data_sources/fear_greed_client.py
  │           └─ data_sources/cache_manager.py
  │
  └─ src/logger.py
```

## 🎯 Principios de Diseño Aplicados

1. **Separación de Responsabilidades**: Cada módulo tiene una función clara
2. **Bajo Acoplamiento**: Los módulos son independientes
3. **Alta Cohesión**: Funcionalidad relacionada está junta
4. **Extensibilidad**: Fácil agregar nuevas fuentes de datos o estrategias
5. **Testabilidad**: Cada componente puede probarse independientemente

## 📝 Convenciones de Código

- **Nombres de archivos**: snake_case (ej: `trading_engine.py`)
- **Nombres de clases**: PascalCase (ej: `TradingEngine`)
- **Nombres de funciones**: snake_case (ej: `calculate_position_size`)
- **Constantes**: UPPER_CASE (ej: `MAX_DAILY_LOSS`)
- **Docstrings**: Google style
- **Type hints**: Usar en todo el código

## 🔒 Archivos Sensibles (no subir a Git)

```
.env                        # Variables de entorno
config/mainnet.json         # Configuración de producción
data/                       # Base de datos de caché
state/                      # Estado del bot
logs/                       # Archivos de log
*.pyc                       # Archivos compilados
__pycache__/                # Cache de Python
```

---

**Última actualización**: Fase 3 completada
**Versión**: 1.0.0
**Mantenedor**: Tu equipo

