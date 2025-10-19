"""Market regime detection for adaptive trading strategies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

import pandas as pd
import numpy as np

from src.indicators import IndicatorValues
from src.multi_timeframe import TimeframeSummary


class MarketRegime(Enum):
    """Market regime types."""
    BULL_STRONG = "bull_strong"      # Strong uptrend
    BULL_WEAK = "bull_weak"          # Weak uptrend
    BEAR_STRONG = "bear_strong"      # Strong downtrend
    BEAR_WEAK = "bear_weak"          # Weak downtrend
    SIDEWAYS = "sideways"            # Ranging/consolidation
    VOLATILE = "volatile"            # High volatility, unclear direction


@dataclass
class RegimeAnalysis:
    """Result of market regime analysis."""
    regime: MarketRegime
    confidence: float  # 0-1
    trend_strength: float  # -1 (bearish) to +1 (bullish)
    volatility_level: float  # 0 (low) to 1 (high)
    recommendation: str  # "momentum", "mean_reversion", "avoid"


class MarketRegimeDetector:
    """Detect current market regime for adaptive strategy selection."""
    
    def __init__(self):
        self.regime_history = []
    
    def detect_regime(
        self,
        df: pd.DataFrame,
        indicators: IndicatorValues,
        timeframe_summaries: Sequence[TimeframeSummary] | None = None,
    ) -> RegimeAnalysis:
        """
        Detect current market regime using multiple indicators.
        
        Returns RegimeAnalysis with recommended trading approach.
        """
        
        # 1. Trend strength from ADX and multi-timeframe
        trend_strength = self._calculate_trend_strength(indicators, timeframe_summaries)
        
        # 2. Volatility level from ATR and Bollinger Bands
        volatility_level = self._calculate_volatility_level(df, indicators)
        
        # 3. Price momentum from recent price action
        momentum = self._calculate_momentum(df)
        
        # 4. Determine regime
        regime, confidence = self._classify_regime(
            trend_strength, volatility_level, momentum, indicators
        )
        
        # 5. Get trading recommendation
        recommendation = self._get_recommendation(regime, volatility_level)
        
        return RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            trend_strength=trend_strength,
            volatility_level=volatility_level,
            recommendation=recommendation,
        )
    
    def _calculate_trend_strength(
        self,
        indicators: IndicatorValues,
        timeframe_summaries: Sequence[TimeframeSummary] | None,
    ) -> float:
        """
        Calculate trend strength (-1 to +1).
        -1 = strong bear, 0 = sideways, +1 = strong bull
        """
        scores = []
        
        # ADX strength
        if indicators.adx:
            adx_strength = min(indicators.adx / 50.0, 1.0)  # Normalize to 0-1
            
            # Determine direction from MACD
            if indicators.macd and indicators.macd_signal:
                direction = 1.0 if indicators.macd > indicators.macd_signal else -1.0
                scores.append(adx_strength * direction)
        
        # Multi-timeframe trends
        if timeframe_summaries:
            bullish_tfs = sum(1 for tf in timeframe_summaries if tf.trend_pct > 0.5)
            bearish_tfs = sum(1 for tf in timeframe_summaries if tf.trend_pct < -0.5)
            total_tfs = len(timeframe_summaries)
            
            if total_tfs > 0:
                tf_score = (bullish_tfs - bearish_tfs) / total_tfs
                scores.append(tf_score)
        
        # RSI position
        if indicators.rsi:
            if indicators.rsi > 60:
                scores.append(0.5)
            elif indicators.rsi < 40:
                scores.append(-0.5)
        
        return np.mean(scores) if scores else 0.0
    
    def _calculate_volatility_level(self, df: pd.DataFrame, indicators: IndicatorValues) -> float:
        """
        Calculate volatility level (0 to 1).
        0 = very low, 1 = very high
        """
        scores = []
        
        # ATR as percentage of price
        if indicators.atr and len(df) > 0:
            current_price = df["close"].iloc[-1]
            atr_pct = indicators.atr / current_price if current_price > 0 else 0.02
            
            # Normalize: 1% ATR = 0.25, 4% ATR = 1.0
            volatility_score = min(atr_pct / 0.04, 1.0)
            scores.append(volatility_score)
        
        # Bollinger Bands width
        if indicators.bollinger_upper and indicators.bollinger_lower and indicators.bollinger_middle:
            bb_width = (indicators.bollinger_upper - indicators.bollinger_lower) / indicators.bollinger_middle
            
            # Normalize: 2% width = 0.25, 8% width = 1.0
            bb_score = min(bb_width / 0.08, 1.0)
            scores.append(bb_score)
        
        # Recent price swings
        if len(df) >= 20:
            recent_returns = df["close"].pct_change().tail(20)
            swing_volatility = recent_returns.std()
            
            # Normalize: 0.5% std = 0.25, 2% std = 1.0
            swing_score = min(swing_volatility / 0.02, 1.0)
            scores.append(swing_score)
        
        return np.mean(scores) if scores else 0.5
    
    def _calculate_momentum(self, df: pd.DataFrame) -> float:
        """
        Calculate recent momentum (-1 to +1).
        """
        if len(df) < 20:
            return 0.0
        
        # Calculate returns over different periods
        returns_5 = (df["close"].iloc[-1] / df["close"].iloc[-6] - 1) if len(df) >= 6 else 0
        returns_10 = (df["close"].iloc[-1] / df["close"].iloc[-11] - 1) if len(df) >= 11 else 0
        returns_20 = (df["close"].iloc[-1] / df["close"].iloc[-21] - 1) if len(df) >= 21 else 0
        
        # Weighted average (recent more important)
        momentum = (returns_5 * 0.5 + returns_10 * 0.3 + returns_20 * 0.2)
        
        # Normalize to -1 to +1 range
        return max(-1.0, min(1.0, momentum * 20))
    
    def _classify_regime(
        self,
        trend_strength: float,
        volatility_level: float,
        momentum: float,
        indicators: IndicatorValues,
    ) -> tuple[MarketRegime, float]:
        """
        Classify market regime based on calculated metrics.
        Returns (regime, confidence)
        """
        
        # High volatility overrides everything
        if volatility_level > 0.7:
            return MarketRegime.VOLATILE, min(volatility_level, 0.95)
        
        # Sideways market (low ADX, low trend strength)
        if indicators.adx and indicators.adx < 20 and abs(trend_strength) < 0.3:
            confidence = 1.0 - abs(trend_strength)  # More confident if closer to 0
            return MarketRegime.SIDEWAYS, min(confidence, 0.95)
        
        # Bullish regimes
        if trend_strength > 0:
            if indicators.adx and indicators.adx > 30 and momentum > 0.3:
                # Strong bull: high ADX, positive momentum
                confidence = min((indicators.adx / 40.0 + momentum) / 2, 0.95)
                return MarketRegime.BULL_STRONG, confidence
            else:
                # Weak bull: positive trend but not strong
                confidence = min(trend_strength + 0.3, 0.8)
                return MarketRegime.BULL_WEAK, confidence
        
        # Bearish regimes
        elif trend_strength < 0:
            if indicators.adx and indicators.adx > 30 and momentum < -0.3:
                # Strong bear: high ADX, negative momentum
                confidence = min((indicators.adx / 40.0 + abs(momentum)) / 2, 0.95)
                return MarketRegime.BEAR_STRONG, confidence
            else:
                # Weak bear: negative trend but not strong
                confidence = min(abs(trend_strength) + 0.3, 0.8)
                return MarketRegime.BEAR_WEAK, confidence
        
        # Default to sideways if unclear
        return MarketRegime.SIDEWAYS, 0.5
    
    def _get_recommendation(self, regime: MarketRegime, volatility: float) -> str:
        """Get trading strategy recommendation based on regime."""
        
        if volatility > 0.8:
            return "avoid"  # Too volatile, avoid trading
        
        if regime in [MarketRegime.BULL_STRONG, MarketRegime.BEAR_STRONG]:
            return "momentum"  # Strong trends: use momentum strategy
        
        elif regime == MarketRegime.SIDEWAYS:
            return "mean_reversion"  # Ranging: use mean reversion
        
        elif regime in [MarketRegime.BULL_WEAK, MarketRegime.BEAR_WEAK]:
            if volatility < 0.4:
                return "mean_reversion"  # Low volatility weak trend: mean reversion
            else:
                return "momentum"  # Higher volatility: momentum
        
        elif regime == MarketRegime.VOLATILE:
            return "avoid"  # High volatility: avoid
        
        return "momentum"  # Default


__all__ = ["MarketRegime", "RegimeAnalysis", "MarketRegimeDetector"]

