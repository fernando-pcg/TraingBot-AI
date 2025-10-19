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

## Inventario del Código Existente (Oct 2025)

- Configuración centralizada en `config/config_loader.py` con perfiles `config/testnet.json`, `config/aggressive.json`, `config/ultra_aggressive.json` y validaciones Pydantic.
- Cliente Binance en `src/binance_client.py` con soporte testnet/live, validación de entorno y logging dedicado.
- Motor principal en `src/main.py` y `src/trading_engine.py`, integrando configuración, loggers, estrategias momentum/mean reversion, gestión de riesgo, market regime detector y reportería avanzada.
- Gestión de riesgo y estado en `src/risk_manager.py` (position sizing dinámico, límites diarios, trailing stops) y `src/state_manager.py` (persistencia JSON de posiciones y trades).
- Estrategias y utilidades técnicas: `src/strategy.py`, `src/mean_reversion_strategy.py`, `src/market_regime.py`, `src/multi_timeframe.py`, `src/indicators.py`, `src/patterns.py`, `src/performance_metrics.py`.
- Pipeline de datos local `src/data_pipeline.py`.
- Módulos de datos externos y sentimiento en `data_sources/` (CoinGecko, CryptoCompare, Fear & Greed, caché SQLite, agregador y analizador de sentimiento con uso opcional de GPT).
- Logger estructurado en `src/logger.py` con salida Rich y archivos en `logs/`.
- Scripts operativos en `scripts/` y pruebas iniciales en `tests/test_apis_config.py`, `tests/test_sentiment_analysis.py`.

Este inventario debe actualizarse cuando se añadan módulos nuevos para evitar duplicar o sobrescribir componentes existentes.

---

## FASE 1: MVP - Bot Seguro y Funcional (PRIORIDAD MÁXIMA)

### 1.1 Sistema de Configuración Robusto
**Estado:** COMPLETADO  
**Archivos actuales:** `config/config_loader.py`, perfiles JSON en `config/`.  
**Pendiente:** Documentar soporte explícito para perfil `backtest` y valores por defecto; ajustar defaults para nuevos módulos (ej. drawdown, logging avanzado).

### 1.2 Soporte para Binance Testnet
**Estado:** COMPLETADO  
**Archivo:** `src/binance_client.py`.  
**Pendiente:** Añadir backoff parametrizable, validaciones unitarias y cobertura de tests automatizados.

### 1.3 Gestor de Riesgo (Risk Manager)
**Estado:** COMPLETADO  
**Archivo:** `src/risk_manager.py`.  
**Pendiente:** Parametrizar umbrales (drawdown, Kelly fraction, trailing) vía configuración y ampliar pruebas de estrés.

### 1.4 Sistema de Estado Persistente
**Estado:** COMPLETADO  
**Archivo:** `src/state_manager.py`.  
**Pendiente:** Añadir opción SQLite y políticas de mantenimiento del historial.

### 1.5 Logger Avanzado
**Estado:** COMPLETADO PARCIAL  
**Archivo:** `src/logger.py`.  
**Pendiente:** Implementar rotación automática de archivos, métricas de consola en tiempo real y configuración centralizada de niveles.

### 1.6 Mejoras en `strategy.py`
**Estado:** COMPLETADO (momentum) + módulos de soporte  
**Archivos clave:** `src/strategy.py`, `src/multi_timeframe.py`, `src/patterns.py`, `src/market_regime.py`, `src/mean_reversion_strategy.py`.  
**Pendiente:** Crear `strategy_engine` modular, ampliar catálogo de indicadores/estrategias y preparar hooks para ML.

### 1.7 Actualización de `main.py`
**Estado:** COMPLETADO  
**Archivo:** `src/main.py`.  
**Pendiente:** Extender CLI para seleccionar estrategias, perfiles ML y configuraciones avanzadas.

**Resultado del MVP:** Bot operativo en modo testnet/dry-run con gestión de riesgo, estrategias momentum/mean reversion, registro completo de operaciones y reportería final.

---

## FASE 2: Análisis Técnico Avanzado

### 2.1 Expansión de Indicadores Técnicos
**Estado:** COMPLETADO PARCIAL  
**Archivo:** `src/indicators.py`.  
**Pendiente:** Incorporar indicadores avanzados restantes (Fibonacci, Volume Profile, ATR multi-periodo) y permitir configuración dinámica por estrategia.

### 2.2 Reconocimiento de Patrones
**Estado:** COMPLETADO PARCIAL  
**Archivo:** `src/patterns.py`.  
**Pendiente:** Añadir patrones de continuación/reversión avanzados y refinar cálculo de soportes/resistencias.

### 2.3 Sistema Multi-Timeframe
**Estado:** COMPLETADO  
**Archivo:** `src/multi_timeframe.py`.  
**Pendiente:** Parametrizar intervalos desde configuración y enriquecer métricas por timeframe.

### 2.4 Strategy Engine Mejorado
**Estado:** EN PROGRESO (estructura actual basada en `strategy.py`)  
**Pendiente:** Diseñar `src/strategy_engine.py` con estrategias intercambiables, pesos configurables, scoring compuesto y backtesting integrado.

---

## FASE 3: Integración de Fuentes de Datos Múltiples

### 3.1 Adaptadores de APIs Gratuitas
**Estado:** COMPLETADO PARCIAL  
**Archivos:** `data_sources/coingecko_client.py`, `data_sources/cryptocompare_client.py`, `data_sources/fear_greed_client.py`.  
**Pendiente:** Crear adaptador específico `data_sources/crypto_apis.py` para Binance público/order book, consolidar rate limiting y reintentos.

### 3.2 Índices de Mercado
**Estado:** EN PROGRESO  
**Implementado:** Fear & Greed vía `data_sources/fear_greed_client.py`.  
**Pendiente:** Bitcoin Dominance dedicado, correlación con mercados tradicionales, eventos macro relevantes.

### 3.3 Data Aggregator
**Estado:** COMPLETADO  
**Archivo:** `data_sources/data_aggregator.py`.  
**Pendiente:** Scheduler de actualización, capas de fallback configurables y métricas de cacheo.

### 3.4 Mejora del Sentiment Analyzer
**Estado:** COMPLETADO  
**Archivo:** `data_sources/sentiment_analyzer.py`.  
**Pendiente:** Integrar detección de eventos clave, correlaciones históricas y métricas sociales adicionales.

---

## FASE 4: Sistema de Machine Learning Local

Actualmente la carpeta `ml/` está vacía; la fase no ha iniciado.

### 4.1 Recolección y Preparación de Datos
**Archivo objetivo:** `ml/data_preparation.py`.  
**Pendiente:** Diseñar pipeline ETL, selección de features técnicas/fundamentales/sentiment y split de datasets.

### 4.2 Modelo de Predicción de Precios
**Archivo objetivo:** `ml/price_predictor.py`.  
**Pendiente:** Implementar modelos XGBoost/LightGBM, opcional LSTM, validación cruzada y métricas.

### 4.3 Sistema de Aprendizaje Continuo
**Archivo objetivo:** `ml/continuous_learning.py`.  
**Pendiente:** Reentrenamiento periódico, evaluación vs realidad, alertas y versionado de modelos.

### 4.4 Feature Store
**Archivo objetivo:** `ml/feature_store.py`.  
**Pendiente:** Diseñar base de datos local de features y procesos de actualización incremental.

### 4.5 Integración con Strategy Engine
**Pendiente:** Crear `MLPredictorStrategy` dentro del futuro `strategy_engine`, combinando señales ML + TA + sentimiento.

---

## FASE 5: Seguimiento de Ballenas y Grandes Traders

Fase no iniciada. Se mantienen las metas originales:

- `data_sources/whale_tracker.py`: Integraciones con exploradores blockchain y alertas de transferencias significativas.
- `social_trading.py`: Inteligencia de copy trading y detección temprana de movimientos de traders destacados.
- `anomaly_detector.py`: Identificación de pump & dump con salidas rápidas.

---

## FASE 6: Arquitectura Multi-Bot y Dashboard Web

Fase no iniciada. Objetivos pendientes:

- `orchestrator.py`: Gestión multi-bot con configuraciones independientes y monitoreo centralizado.
- Backend FastAPI (`api/`): Endpoints REST, WebSocket y autenticación con JWT + 2FA.
- Sistema de usuarios y roles (`api/auth/`): VIEWER, TRADER, ADMIN, manejo de tokens y secretos 2FA.
- Frontend React/Vue: Dashboard con métricas en tiempo real, control de bots y logs.

---

## Próximos Pasos Prioritarios

1. Parametrizar drawdown, trailing stops y niveles de logging dentro de la configuración existente.
2. Diseñar e implementar `src/strategy_engine.py` modular con soporte para múltiples estrategias y backtesting.
3. Completar adaptadores de datos pendientes (Binance público, índices macro) y programar scheduler de actualización.
4. Definir roadmap detallado para la fase ML (datasets, feature store, pipelines) aprovechando la estructura actual.
5. Planificar arquitectura del orquestador multi-bot y API segura (roles, JWT, 2FA) antes de iniciar la fase 6.