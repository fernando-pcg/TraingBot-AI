# Plan de Desarrollo: TraingBot-AI - Sistema Completo

## Arquitectura General del Sistema

El sistema se compondrá de:

- **Core Engine:** Gestor principal del bot configurable
- **Risk Manager:** Módulo de gestión de riesgo y capital
- **Strategy Engine:** Motor de estrategias técnicas intercambiables
- **Data Pipeline:** Recolección y procesamiento de múltiples fuentes
- **ML Engine:** Sistema de aprendizaje local para decisiones rápidas
- **Sentiment Analyzer:** Análisis de noticias y sentiment con IA
- **Multi-Bot Orchestrator:** Gestor de múltiples bots concurrentes
- **Web Dashboard:** Interfaz web segura con 2FA para control y monitoreo

---

## FASE 1: MVP - Bot Seguro y Funcional (PRIORIDAD MÁXIMA)

### 1.1 Sistema de Configuración Robusto

**Archivo:** `config.py` (nuevo)

- Sistema de configuración centralizado con validaciones
- Soporte para múltiples perfiles (live, testnet, backtest)
- Parámetros de riesgo configurables por estrategia
- Variables:
  - Capital inicial, capital máximo por trade
  - Stop-loss, take-profit configurables
  - Márgenes de ganancia mínimos/máximos
  - Porcentaje de reinversión de ganancias
  - Límites diarios de pérdidas

### 1.2 Soporte para Binance Testnet

**Archivo:** `binance_client.py` (modificar)

- Agregar modo testnet con URL: `https://testnet.binance.vision`
- Toggle entre live/testnet mediante configuración
- Validación de ambiente antes de cada operación
- Logger específico para identificar modo de operación

### 1.3 Gestor de Riesgo (Risk Manager)

**Archivo:** `risk_manager.py` (nuevo)

- **Stop-loss dinámico:** Ajustable según volatilidad
- **Take-profit inteligente:** Trailing stop para maximizar ganancias
- **Position sizing:** Cálculo de tamaño de posición según capital disponible
- **Máxima exposición:** Límite de capital en riesgo simultáneo
- **Daily loss limit:** Detener trading si se alcanza pérdida diaria máxima
- **Profit locking:** Proteger ganancias acumuladas
- **Métodos clave:**
  - `calculate_position_size(capital, risk_percent, stop_loss_pct)`
  - `should_open_position(current_exposure, capital)`
  - `calculate_stop_loss(entry_price, volatility)`
  - `calculate_take_profit(entry_price, strategy_type, confidence)`
  - `check_daily_limits(trades_today)`

### 1.4 Sistema de Estado Persistente

**Archivo:** `state_manager.py` (nuevo)

- Guardar estado de posiciones en JSON/SQLite
- Recuperación de estado al reiniciar el bot
- Historial de trades con métricas
- Registro de capital histórico para tracking de performance

### 1.5 Logger Avanzado

**Archivo:** `logger.py` (nuevo)

- Sistema de logs estructurado con niveles (INFO, WARNING, ERROR)
- Logs separados por categoría (trades, errors, api_calls)
- Rotación de logs diarios
- Dashboard básico en consola con métricas en tiempo real

### 1.6 Mejoras en `strategy.py`

- Agregar más validaciones de datos
- Manejo de errores más robusto
- Indicadores adicionales básicos: RSI, MACD
- Confirmación de señales con volumen

### 1.7 Actualización de `main.py`

- Integrar Risk Manager
- Cargar configuración desde `config.py`
- Implementar recuperación de estado
- Agregar modo dry-run (simulación sin ejecutar órdenes reales)

**Resultado del MVP:** Bot que puede operar en testnet de forma segura, con gestión de riesgo robusta, stop-loss/take-profit automáticos, y registro completo de operaciones.

---

## FASE 2: Análisis Técnico Avanzado

### 2.1 Expansión de Indicadores Técnicos

**Archivo:** `indicators.py` (nuevo)

- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bandas de Bollinger
- ATR (Average True Range) para volatilidad
- Fibonacci retracements
- Volume Profile
- Stochastic Oscillator
- ADX (Average Directional Index)

### 2.2 Reconocimiento de Patrones

**Archivo:** `patterns.py` (nuevo)

- Patrones de velas japonesas (Doji, Hammer, Engulfing, etc.)
- Patrones de continuación (Flags, Pennants)
- Patrones de reversión (Head & Shoulders, Double Top/Bottom)
- Detección de soportes y resistencias dinámicos

### 2.3 Sistema Multi-Timeframe

**Archivo:** `multi_timeframe.py` (nuevo)

- Análisis simultáneo en múltiples timeframes (1m, 5m, 15m, 1h, 4h, 1d)
- Confirmación de señales entre timeframes
- Detección de divergencias

### 2.4 Strategy Engine Mejorado

**Archivo:** `strategy_engine.py` (nuevo para reemplazar `strategy.py`)

- Arquitectura de estrategias intercambiables
- Combinación de múltiples indicadores con pesos
- Sistema de scoring para señales
- Backtesting integrado para cada estrategia

---

## FASE 3: Integración de Fuentes de Datos Múltiples

### 3.1 Adaptadores de APIs Gratuitas

**Archivo:** `data_sources/crypto_apis.py` (nuevo)

- **CoinGecko API:** Precios, market cap, volumen 24h, cambios históricos
- **CryptoCompare API:** Datos sociales, métricas on-chain básicas
- **Binance Public API:** Datos de order book, trades recientes
- Sistema de caché inteligente para minimizar llamadas
- Rate limiting y retry logic

### 3.2 Índices de Mercado

**Archivo:** `data_sources/market_indices.py` (nuevo)

- Fear & Greed Index para crypto
- Bitcoin Dominance Index
- Correlación con mercados tradicionales (S&P 500 via Yahoo Finance)
- Detección de eventos macro (noticias económicas importantes)

### 3.3 Data Aggregator

**Archivo:** `data_aggregator.py` (nuevo)

- Recopilar y normalizar datos de todas las fuentes
- Sistema de prioridad para fuentes (fallback si una falla)
- Caché local con SQLite para datos históricos
- Scheduler para actualización periódica de datos estáticos

### 3.4 Mejora del Sentiment Analyzer

**Archivo:** `ai_analyzer.py` (modificar)

- Análisis de sentiment más sofisticado con GPT-4
- Detección de eventos clave (halvings, actualizaciones de protocolo)
- Análisis de correlaciones entre noticias y movimientos de precio
- Reducir llamadas a OpenAI: solo para análisis ambiguos o críticos

---

## FASE 4: Sistema de Machine Learning Local

### 4.1 Recolección y Preparación de Datos

**Archivo:** `ml/data_preparation.py` (nuevo)

- ETL para extraer features de datos históricos
- Features técnicas: indicadores, patrones, volumen
- Features fundamentales: market cap, volumen 24h, dominancia
- Features de sentiment: scores de noticias, social media
- Normalización y scaling de datos
- División en train/validation/test sets

### 4.2 Modelo de Predicción de Precios

**Archivo:** `ml/price_predictor.py` (nuevo)

**Enfoque híbrido:**
- **XGBoost/LightGBM:** Para decisiones rápidas (clasificación: BUY/SELL/HOLD)
- **LSTM opcional:** Para predicción de tendencias a medio plazo
- Training pipeline con validación cruzada
- Optimización de hiperparámetros
- Métricas de evaluación (accuracy, precision, recall, F1)

### 4.3 Sistema de Aprendizaje Continuo

**Archivo:** `ml/continuous_learning.py` (nuevo)

- Reentrenamiento periódico con datos nuevos
- Evaluación de performance del modelo vs realidad
- Sistema de alertas si el modelo degrada
- Versionado de modelos (guardar mejores versiones)

### 4.4 Feature Store

**Archivo:** `ml/feature_store.py` (nuevo)

- Base de datos local (SQLite/PostgreSQL) para features calculadas
- Evitar recalcular features costosas
- Sistema de actualización incremental

### 4.5 Integración con Strategy Engine

**Archivo:** `strategy_engine.py` (modificar)

- Nueva estrategia: `MLPredictorStrategy`
- Combinar predicciones ML con análisis técnico
- Sistema de confianza híbrido: ML + Técnico + Sentiment

---

## FASE 5: Seguimiento de Ballenas y Grandes Traders

### 5.1 Whale Alert Integration

**Archivo:** `data_sources/whale_tracker.py` (nuevo)

- Integración con APIs de blockchain explorers (Etherscan, BscScan)
- Detección de grandes transferencias a exchanges (posible venta)
- Detección de grandes retiros de exchanges (posible acumulación)
- Análisis de wallets de ballenas conocidas

### 5.2 Copy Trading Intelligence

**Archivo:** `social_trading.py` (nuevo)

- Scraping de leaderboards de exchanges (cuando disponible)
- Análisis de patrones de traders exitosos
- Identificación de señales tempranas de movimientos

### 5.3 Pump & Dump Detection

**Archivo:** `anomaly_detector.py` (nuevo)

- Detección de aumentos anormales de volumen
- Análisis de patrones de pump & dump
- Alertas para aprovechar momentum (con precaución)
- Sistema de exit rápido antes de dumps

---

## FASE 6: Arquitectura Multi-Bot y Dashboard Web

### 6.1 Bot Orchestrator

**Archivo:** `orchestrator.py` (nuevo)

- Gestor de múltiples instancias de bots
- Cada bot con configuración independiente:
  - Tipo de trading (spot, futures)
  - Estrategia específica
  - Par de criptomonedas
  - Capital asignado
- Monitoreo centralizado de todos los bots
- API REST completa para comunicación con frontend

### 6.2 Dashboard Web Completo

**Arquitectura:** Backend FastAPI + Frontend React/Vue

#### 6.2.1 Backend API

**Carpeta:** `api/`

**Archivo principal:** `api/main.py`
- API REST con FastAPI
- WebSocket para datos en tiempo real
- Autenticación con JWT
- Endpoints principales:
  - `/auth/login` - Autenticación
  - `/auth/2fa/setup` - Configurar 2FA
  - `/auth/2fa/verify` - Verificar 2FA
  - `/bots/` - CRUD de bots
  - `/bots/{id}/start` - Iniciar bot
  - `/bots/{id}/stop` - Detener bot
  - `/bots/{id}/status` - Estado del bot
  - `/trades/` - Historial de trades
  - `/trades/live` - WebSocket para trades en vivo
  - `/performance/` - Métricas de performance
  - `/config/` - Configuración de estrategias
  - `/positions/` - Posiciones abiertas
  - `/logs/` - Logs del sistema
  - `/users/` - Gestión de usuarios (ADMIN)

**Archivo:** `api/models.py`
- Modelos de datos con Pydantic
- Validaciones de entrada
- Esquemas de respuesta

**Archivo:** `api/websocket.py`
- WebSocket manager para streaming de datos
- Broadcast de trades en tiempo real
- Actualizaciones de precios
- Estado de bots

#### 6.2.2 Sistema de Seguridad (CRÍTICO)

**Sistema de Usuarios y Roles**

**Archivo:** `api/auth/users.py`

**Roles definidos:**

1. **VIEWER** (Solo lectura)
   - Ver dashboard y métricas
   - Ver historial de trades
   - Ver posiciones abiertas
   - Ver logs
   - NO puede: iniciar/detener bots, cambiar configuraciones, cerrar posiciones

2. **TRADER** (Operaciones básicas)
   - Todo lo de VIEWER
   - Iniciar/detener bots existentes
   - Cerrar posiciones manualmente (con confirmación)
   - NO puede: crear/editar bots, cambiar configuraciones críticas, gestionar API keys

3. **ADMIN** (Control completo)
   - Todo lo de TRADER
   - Crear/editar/eliminar bots
   - Modificar configuraciones de riesgo
   - Gestionar API keys (Binance, OpenAI, etc.)
   - Gestionar usuarios
   - Acceso a todas las funcionalidades

**Modelo de datos de Usuario:**
- id: UUID
- username: string (único)
- email: string (único)
- password_hash: string (bcrypt con salt)
- role: enum (VIEWER, TRADER, ADMIN)
- two_factor_enabled: boolean
- two_factor_secret: string (encriptado)
- is_active: boolean
- last_login: datetime
- created_at: datetime
- updated_at: datetime

**Autenticación con JWT**

**Archivo:** `api/auth/jwt_handler.py`

- **Access Token:** JWT de corta duración (15 minutos)
  - Contiene: user_id, role, permissions
  - Firmado con RS256 (clave privada)
  - Validado en cada request protegido

- **Refresh Token:** Token de larga duración (7 días)
  - Almacenado en httpOnly cookie
  - Permite renovar access token sin re-login
  - Rotación automática al usarse
  - Revocable desde base de datos

- **Tokens almacenados en DB:**
  - Tabla `refresh_tokens` para tracking y revocación
  - Cleanup automático de tokens expirados
  - Máximo 3 sesiones activas por usuario

**Autenticación de Doble Factor (2FA)**

**Archivo:** `api/auth/two_factor.py`

**Implementación con TOTP (Time-based One-Time Password):**

1. **Setup de 2FA:**
   - Generar secret único por usuario
   - Mostrar QR code para escanear con app autenticadora (Google Authenticator, Authy, etc.)
   - Solicitar código de verificación antes de activar
   - Generar códigos de backup (10 códigos de un solo uso)
   - Almacenar secret encriptado en DB

2. **Login con 2FA:**
   - Primera fase: usuario + contraseña → token temporal (5 min)
   - Segunda fase: código