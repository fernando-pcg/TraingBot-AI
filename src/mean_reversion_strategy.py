"""
Mean Reversion Strategy para mercados laterales.
Compra cerca de soporte, vende cerca de resistencia.
"""

from dataclasses import dataclass
from typing import Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from src.patterns import PatternResult

from src.indicators import IndicatorValues
from src.multi_timeframe import TimeframeSummary


@dataclass
class MeanReversionSignal:
    """Señal de mean reversion."""
    action: str  # "buy", "sell", "hold"
    confidence: float
    reason: str
    entry_zone: str  # "support", "resistance", "middle"


class MeanReversionStrategy:
    """
    Estrategia de Mean Reversion para mercados laterales.
    
    Principios:
    - Comprar cuando precio está cerca del SOPORTE (banda inferior)
    - Vender cuando precio está cerca de la RESISTENCIA (banda superior)
    - Usar stops ajustados (0.5-0.8% vs 1.5%)
    - Take profits pequeños pero frecuentes (0.8-1.5% vs 2.5%)
    """
    
    def __init__(self, support_threshold: float = 0.02, resistance_threshold: float = 0.02):
        """
        Args:
            support_threshold: % de distancia al soporte para comprar (default 2%)
            resistance_threshold: % de distancia a resistencia para vender (default 2%)
        """
        self.support_threshold = support_threshold
        self.resistance_threshold = resistance_threshold
    
    def evaluate(
        self,
        symbol: str,
        current_price: float,
        indicators: IndicatorValues,
        patterns: "PatternResult",
        timeframe_summaries: Sequence[TimeframeSummary] | None = None,
    ) -> MeanReversionSignal | None:
        """Evaluar señal de mean reversion."""
        
        scores = []
        reasons = []
        
        # 1. Bollinger Bands - Principal indicador para mean reversion
        if indicators.bollinger_upper and indicators.bollinger_lower and indicators.bollinger_middle:
            bb_position = (current_price - indicators.bollinger_lower) / (indicators.bollinger_upper - indicators.bollinger_lower)
            
            # Cerca de banda inferior = COMPRAR (oversold)
            if bb_position < 0.2:  # 20% inferior
                scores.append(1.5)
                reasons.append(f"Near lower BB (position: {bb_position:.2f})")
            elif bb_position < 0.3:
                scores.append(1.0)
                reasons.append("Approaching lower BB")
            
            # Cerca de banda superior = VENDER (overbought)
            elif bb_position > 0.8:  # 80% superior
                scores.append(-1.5)
                reasons.append(f"Near upper BB (position: {bb_position:.2f})")
            elif bb_position > 0.7:
                scores.append(-1.0)
                reasons.append("Approaching upper BB")
        
        # 2. RSI para confirmar oversold/overbought
        if indicators.rsi:
            if indicators.rsi < 30:
                scores.append(0.8)
                reasons.append(f"RSI oversold ({indicators.rsi:.0f})")
            elif indicators.rsi < 35:
                scores.append(0.5)
                reasons.append(f"RSI low ({indicators.rsi:.0f})")
            elif indicators.rsi > 70:
                scores.append(-0.8)
                reasons.append(f"RSI overbought ({indicators.rsi:.0f})")
            elif indicators.rsi > 65:
                scores.append(-0.5)
                reasons.append(f"RSI high ({indicators.rsi:.0f})")
        
        # 3. Support/Resistance levels
        if patterns.support and patterns.resistance:
            support_dist = (current_price - patterns.support) / patterns.support
            resistance_dist = (patterns.resistance - current_price) / patterns.resistance
            
            # Cerca de soporte = COMPRAR
            if support_dist < self.support_threshold:
                scores.append(1.0)
                reasons.append(f"Near support (${patterns.support:.2f})")
            
            # Cerca de resistencia = VENDER
            if resistance_dist < self.resistance_threshold:
                scores.append(-1.0)
                reasons.append(f"Near resistance (${patterns.resistance:.2f})")
        
        # 4. Stochastic para timing
        if indicators.stochastic_k and indicators.stochastic_d:
            if indicators.stochastic_k < 20:
                scores.append(0.5)
                reasons.append("Stochastic oversold")
            elif indicators.stochastic_k > 80:
                scores.append(-0.5)
                reasons.append("Stochastic overbought")
        
        # 5. MACD divergencia (confirma reversión)
        if indicators.macd and indicators.macd_signal:
            # Bullish crossover en zona baja = COMPRAR
            if indicators.macd > indicators.macd_signal and indicators.macd < 0:
                scores.append(0.6)
                reasons.append("MACD bullish crossover in negative zone")
            # Bearish crossover en zona alta = VENDER
            elif indicators.macd < indicators.macd_signal and indicators.macd > 0:
                scores.append(-0.6)
                reasons.append("MACD bearish crossover in positive zone")
        
        # Evaluar scores
        if not scores:
            return None
        
        total_score = sum(scores)
        
        # Thresholds más bajos que momentum (más oportunidades)
        if total_score >= 1.5:  # Comprar
            confidence = min(total_score / 4.0, 0.90)
            return MeanReversionSignal(
                action="buy",
                confidence=confidence,
                reason="; ".join(reasons),
                entry_zone="support"
            )
        elif total_score <= -1.5:  # Vender/Short
            confidence = min(abs(total_score) / 4.0, 0.90)
            return MeanReversionSignal(
                action="sell",
                confidence=confidence,
                reason="; ".join(reasons),
                entry_zone="resistance"
            )
        
        return None

