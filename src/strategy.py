"""Basic strategy implementation with indicator validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

import pandas as pd

from src.indicators import (
    IndicatorComputationError,
    IndicatorValues,
    calculate_indicators,
)
from src.multi_timeframe import TimeframeSummary
from src.patterns import PatternSignals, analyze_patterns


@dataclass
class Signal:
    symbol: str
    action: str
    confidence: float
    reason: str


class Strategy:
    """Technical analysis driven strategy combining multiple indicators."""

    def __init__(
        self,
        min_volume: float = 0,
        rsi_bounds: tuple[int, int] = (35, 65),
        adx_trend_threshold: float = 20,
        atr_volatility_ceiling: float = 0.02,
    ) -> None:
        self.min_volume = min_volume
        self.rsi_lower, self.rsi_upper = rsi_bounds
        self.adx_trend_threshold = adx_trend_threshold
        self.atr_volatility_ceiling = atr_volatility_ceiling

    def validate_data(self, df: pd.DataFrame) -> None:
        required_cols = {"close", "volume"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Data missing required columns: {missing}")
        if df["close"].isna().any():
            raise ValueError("Close prices contain NaN")

    def generate_signal(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe_summaries: Sequence[TimeframeSummary] | None = None,
    ) -> Signal | None:
        self.validate_data(df)

        if df["volume"].iloc[-1] < self.min_volume:
            return None

        try:
            indicators = calculate_indicators(df)
        except IndicatorComputationError:
            return None

        current_price = df["close"].iloc[-1]
        previous_price = df["close"].iloc[-2]
        price_change_pct = (current_price / previous_price - 1) * 100

        if indicators.atr / max(current_price, 1e-8) > self.atr_volatility_ceiling:
            return None
        
        # FILTRO CRÍTICO: Detectar mercado lateral (range-bound) y NO operar
        if self._is_ranging_market(indicators, timeframe_summaries):
            return None  # Evita pérdidas por whipsaw en mercado lateral

        patterns = analyze_patterns(df)

        indicator_scores, indicator_reasons = self._evaluate_indicators(
            current_price,
            indicators,
            price_change_pct,
        )
        pattern_scores, pattern_reasons = self._evaluate_patterns(current_price, patterns)
        timeframe_scores, timeframe_reasons = self._evaluate_timeframes(timeframe_summaries, indicators)

        scores = indicator_scores + pattern_scores + timeframe_scores
        reasons = indicator_reasons + pattern_reasons + timeframe_reasons

        if not scores:
            return None

        total_score = sum(scores)

        # Umbrales ajustables basados en configuración
        # Para modo más agresivo, usar umbrales más bajos
        buy_threshold = 0.7  # Ultra-agresivo: reducido de 1.0 a 0.7
        sell_threshold = -0.7  # Ultra-agresivo: reducido de -1.0 a -0.7
        
        if total_score >= buy_threshold:
            confidence = min(total_score / 4.0, 0.95)  # Ultra-agresivo: divisor de 4.0
            reason = "; ".join(reasons)
            return Signal(symbol=symbol, action="buy", confidence=confidence, reason=reason)

        if total_score <= sell_threshold:
            confidence = min(abs(total_score) / 4.0, 0.95)
            reason = "; ".join(reasons)
            return Signal(symbol=symbol, action="sell", confidence=confidence, reason=reason)

        return None

    def _is_ranging_market(
        self,
        indicators: IndicatorValues,
        timeframe_summaries: Sequence[TimeframeSummary] | None = None,
    ) -> bool:
        """
        Detecta si el mercado está en rango lateral (no trending).
        MEJORADO: Detecta correctamente mercados laterales con volatilidad.
        """
        # 1. Verificar movimiento de precio real en timeframes
        if timeframe_summaries and len(timeframe_summaries) >= 3:
            # Calcular promedio de movimiento absoluto
            avg_movement = sum(abs(tf.trend_pct) for tf in timeframe_summaries) / len(timeframe_summaries)
            
            # Si el movimiento promedio es < 0.5%, es rango lateral
            if avg_movement < 0.5:
                return True
            
            # Verificar si los timeframes se contradicen (lateral con volatilidad)
            trends = [1 if tf.trend_pct > 0 else -1 for tf in timeframe_summaries if abs(tf.trend_pct) > 0.2]
            if len(trends) >= 3:
                ups = sum(1 for t in trends if t > 0)
                downs = sum(1 for t in trends if t < 0)
                # Si está muy dividido (50/50), es rango lateral con ruido
                if abs(ups - downs) <= 1:
                    return True
        
        # 2. ADX bajo = sin tendencia clara
        if indicators.adx and indicators.adx < 18:
            return True
        
        # 3. RSI neutral + precio sin momentum claro
        if indicators.rsi and 45 <= indicators.rsi <= 55:
            # Verificar que el precio realmente no se está moviendo
            if indicators.macd and indicators.macd_signal:
                macd_diff = abs(indicators.macd - indicators.macd_signal)
                if macd_diff < 3:  # MACD muy plano
                    return True
        
        # 4. Bollinger Bands estrechas = baja volatilidad = lateral
        if indicators.bollinger_upper and indicators.bollinger_lower and indicators.bollinger_middle:
            bb_width = (indicators.bollinger_upper - indicators.bollinger_lower) / indicators.bollinger_middle
            if bb_width < 0.02:  # Bandas muy estrechas (< 2%)
                return True
        
        return False

    def _evaluate_indicators(
        self,
        current_price: float,
        indicators: IndicatorValues,
        price_change_pct: float,
    ) -> tuple[List[float], List[str]]:
        scores: List[float] = []
        reasons: List[str] = []

        # RSI momentum
        if indicators.rsi < self.rsi_lower:
            scores.append(1.0)
            reasons.append("RSI oversold")
        elif indicators.rsi > self.rsi_upper:
            scores.append(-1.0)
            reasons.append("RSI overbought")

        # MACD trend confirmation
        if indicators.macd_histogram > 0:
            scores.append(0.75)
            reasons.append("MACD bullish histogram")
        elif indicators.macd_histogram < 0:
            scores.append(-0.75)
            reasons.append("MACD bearish histogram")

        # Bollinger Bands proximity
        if current_price <= indicators.bollinger_lower:
            scores.append(0.5)
            reasons.append("Price near lower Bollinger band")
        elif current_price >= indicators.bollinger_upper:
            scores.append(-0.5)
            reasons.append("Price near upper Bollinger band")

        # Stochastic oscillator
        if indicators.stochastic_k < 20 and indicators.stochastic_d < 20:
            scores.append(0.5)
            reasons.append("Stochastic oversold")
        elif indicators.stochastic_k > 80 and indicators.stochastic_d > 80:
            scores.append(-0.5)
            reasons.append("Stochastic overbought")

        # Trend strength via ADX
        if indicators.adx < self.adx_trend_threshold:
            scores.append(-0.25 if price_change_pct < 0 else 0.25)
            reasons.append("Weak trend (ADX)")
        else:
            scores.append(0.25 if indicators.macd_histogram > 0 else -0.25)
            reasons.append("Strong trend (ADX)")

        # Short-term price momentum confirmation
        if price_change_pct > 0.1:
            scores.append(0.25)
            reasons.append("Positive momentum")
        elif price_change_pct < -0.1:
            scores.append(-0.25)
            reasons.append("Negative momentum")

        return scores, reasons

    def _evaluate_patterns(
        self,
        current_price: float,
        patterns: PatternSignals,
    ) -> tuple[List[float], List[str]]:
        scores: List[float] = []
        reasons: List[str] = []

        for pattern in patterns.bullish:
            scores.append(0.6)
            reasons.append(f"Bullish pattern: {pattern}")

        for pattern in patterns.bearish:
            scores.append(-0.6)
            reasons.append(f"Bearish pattern: {pattern}")

        if patterns.support:
            distance_to_support = (current_price - patterns.support) / patterns.support * 100
            if distance_to_support <= 1:
                scores.append(0.4)
                reasons.append("Price near support level")

        if patterns.resistance:
            distance_to_resistance = (patterns.resistance - current_price) / patterns.resistance * 100
            if distance_to_resistance <= 1:
                scores.append(-0.4)
                reasons.append("Price near resistance level")

        if patterns.bullish_divergence:
            scores.append(0.7)
            reasons.append("Bullish RSI divergence")

        if patterns.bearish_divergence:
            scores.append(-0.7)
            reasons.append("Bearish RSI divergence")

        return scores, reasons

    def _evaluate_timeframes(
        self,
        summaries: Sequence[TimeframeSummary] | None,
        current_tf_indicators: IndicatorValues,
    ) -> tuple[List[float], List[str]]:
        if not summaries:
            return [], []

        weights = {
            "1m": 0.8,
            "3m": 0.9,
            "5m": 1.0,
            "15m": 1.2,
            "30m": 1.3,
            "1h": 1.5,
            "4h": 1.8,
            "1d": 2.0,
        }

        scores: List[float] = []
        reasons: List[str] = []

        for summary in summaries:
            weight = weights.get(summary.interval, 1.0)

            if summary.trend_pct > 0.15:
                scores.append(0.4 * weight)
                reasons.append(f"{summary.interval} uptrend {summary.trend_pct:.2f}%")
            elif summary.trend_pct < -0.15:
                scores.append(-0.4 * weight)
                reasons.append(f"{summary.interval} downtrend {summary.trend_pct:.2f}%")

            if summary.indicators.adx > self.adx_trend_threshold:
                if summary.indicators.macd_histogram > 0:
                    scores.append(0.3 * weight)
                    reasons.append(f"{summary.interval} strong bullish trend")
                else:
                    scores.append(-0.3 * weight)
                    reasons.append(f"{summary.interval} strong bearish trend")

            rsi = summary.indicators.rsi
            if rsi < self.rsi_lower:
                scores.append(0.25 * weight)
                reasons.append(f"{summary.interval} RSI oversold")
            elif rsi > self.rsi_upper:
                scores.append(-0.25 * weight)
                reasons.append(f"{summary.interval} RSI overbought")

        # Encourage alignment: if higher timeframe conflicts with current, penalize
        if summaries:
            higher_tf = summaries[-1]
            if higher_tf.indicators.macd_histogram > 0 and current_tf_indicators.macd_histogram < 0:
                scores.append(-0.5)
                reasons.append("Current timeframe contradicts higher timeframe bullish trend")
            elif higher_tf.indicators.macd_histogram < 0 and current_tf_indicators.macd_histogram > 0:
                scores.append(-0.5)
                reasons.append("Current timeframe contradicts higher timeframe bearish trend")

        return scores, reasons


__all__ = ["Strategy", "Signal"]


