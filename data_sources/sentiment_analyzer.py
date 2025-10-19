"""Efficient sentiment analyzer that uses GPT only for final consolidated analysis."""

from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Dict, Optional

from data_sources.data_aggregator import CompiledMarketData, DataAggregator


class SentimentAnalyzer:
    """Analyzes market sentiment using compiled data and optional GPT review."""

    def __init__(
        self,
        data_aggregator: DataAggregator,
        openai_api_key: Optional[str] = None,
        use_gpt: bool = False,
    ) -> None:
        self._aggregator = data_aggregator
        self._openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self._use_gpt = use_gpt and self._openai_api_key is not None

    def analyze_market(self, symbol: str, use_gpt_override: Optional[bool] = None) -> Dict[str, Any]:
        """Analyze market for a symbol with optional GPT enhancement.
        
        Parameters
        ----------
        symbol : str
            Trading symbol (e.g., 'BTCUSDT')
        use_gpt_override : Optional[bool]
            Override the default use_gpt setting for this call
            
        Returns
        -------
        Dict containing:
        - compiled_data: All aggregated market data
        - local_analysis: Analysis based on compiled data (no GPT)
        - gpt_analysis: Optional GPT-enhanced analysis
        - final_recommendation: Trading recommendation
        - confidence_score: 0-100
        """
        # Get compiled data from all free APIs
        compiled_data = self._aggregator.get_compiled_data(symbol)
        
        # Perform local analysis (no GPT required)
        local_analysis = self._local_analysis(compiled_data)
        
        # Decide whether to use GPT
        should_use_gpt = use_gpt_override if use_gpt_override is not None else self._use_gpt
        
        gpt_analysis = None
        if should_use_gpt:
            # Only call GPT if conditions warrant it (e.g., ambiguous signals)
            if self._should_consult_gpt(local_analysis, compiled_data):
                gpt_analysis = self._gpt_analysis(compiled_data, local_analysis)
        
        # Generate final recommendation
        final_recommendation = self._generate_recommendation(
            local_analysis=local_analysis,
            gpt_analysis=gpt_analysis,
        )
        
        return {
            "symbol": symbol,
            "compiled_data": compiled_data,
            "local_analysis": local_analysis,
            "gpt_analysis": gpt_analysis,
            "final_recommendation": final_recommendation,
            "timestamp": compiled_data.timestamp,
        }

    def _local_analysis(self, data: CompiledMarketData) -> Dict[str, Any]:
        """Perform analysis using only compiled data (no API calls).
        
        This is the primary analysis method that doesn't consume GPT credits.
        """
        coin = data.coin_metrics
        sentiment = data.market_sentiment
        global_market = data.global_market
        
        # Calculate signal strength
        signals = []
        signal_scores = []
        
        # Price momentum signals
        if coin.price_change_24h > 3:
            signals.append("Strong 24h price increase")
            signal_scores.append(1.0)
        elif coin.price_change_24h > 1:
            signals.append("Positive 24h momentum")
            signal_scores.append(0.5)
        elif coin.price_change_24h < -3:
            signals.append("Strong 24h price decrease")
            signal_scores.append(-1.0)
        elif coin.price_change_24h < -1:
            signals.append("Negative 24h momentum")
            signal_scores.append(-0.5)
        
        # Volume analysis
        if coin.volume_24h > 0:
            # High volume relative to market cap indicates strong interest
            volume_to_mcap = coin.volume_24h / max(coin.market_cap, 1)
            if volume_to_mcap > 0.3:
                signals.append("Very high trading volume")
                signal_scores.append(0.5)
            elif volume_to_mcap < 0.05:
                signals.append("Low trading volume")
                signal_scores.append(-0.3)
        
        # Fear & Greed interpretation
        if sentiment.fear_greed_index <= 25:
            signals.append(f"Extreme Fear (FG: {sentiment.fear_greed_index}) - contrarian buy signal")
            signal_scores.append(0.7)
        elif sentiment.fear_greed_index <= 45:
            signals.append(f"Fear in market (FG: {sentiment.fear_greed_index})")
            signal_scores.append(0.3)
        elif sentiment.fear_greed_index >= 75:
            signals.append(f"Extreme Greed (FG: {sentiment.fear_greed_index}) - potential top")
            signal_scores.append(-0.7)
        elif sentiment.fear_greed_index >= 55:
            signals.append(f"Greed in market (FG: {sentiment.fear_greed_index})")
            signal_scores.append(-0.3)
        
        # Global market momentum
        if global_market.market_cap_change_24h > 2:
            signals.append("Strong positive global market momentum")
            signal_scores.append(0.6)
        elif global_market.market_cap_change_24h > 0.5:
            signals.append("Positive global market momentum")
            signal_scores.append(0.3)
        elif global_market.market_cap_change_24h < -2:
            signals.append("Strong negative global market momentum")
            signal_scores.append(-0.6)
        elif global_market.market_cap_change_24h < -0.5:
            signals.append("Negative global market momentum")
            signal_scores.append(-0.3)
        
        # Bitcoin dominance analysis (affects altcoins)
        if "BTC" not in coin.symbol:
            if global_market.btc_dominance > 50:
                signals.append("High BTC dominance - altcoin season unlikely")
                signal_scores.append(-0.2)
            elif global_market.btc_dominance < 40:
                signals.append("Low BTC dominance - altcoin season possible")
                signal_scores.append(0.3)
        
        # News sentiment
        if data.news_summary["sentiment"] == "positive":
            signals.append("Positive news sentiment")
            signal_scores.append(0.4)
        elif data.news_summary["sentiment"] == "negative":
            signals.append("Negative news sentiment")
            signal_scores.append(-0.4)
        
        # Trending status
        if coin.symbol.replace("USDT", "") in data.trending_coins:
            signals.append("Coin is trending on CoinGecko")
            signal_scores.append(0.5)
        
        # Calculate aggregate score
        avg_score = sum(signal_scores) / len(signal_scores) if signal_scores else 0
        
        # Determine action
        if avg_score > 0.3:
            action = "BUY"
            confidence = min(95, int(50 + avg_score * 50))
        elif avg_score < -0.3:
            action = "SELL"
            confidence = min(95, int(50 + abs(avg_score) * 50))
        else:
            action = "HOLD"
            confidence = int(50 + abs(avg_score) * 30)
        
        return {
            "action": action,
            "confidence": confidence,
            "compiled_score": data.compiled_score,
            "average_signal_score": avg_score,
            "signals": signals,
            "signal_count": len(signals),
            "risk_level": self._calculate_risk_level(data),
            "market_conditions": self._describe_market_conditions(data),
        }

    def _should_consult_gpt(self, local_analysis: Dict[str, Any], data: CompiledMarketData) -> bool:
        """Decide if GPT consultation is warranted.
        
        Only use GPT for:
        - Ambiguous signals (confidence < 60)
        - High-risk situations
        - Conflicting indicators
        """
        confidence = local_analysis["confidence"]
        compiled_score = abs(data.compiled_score)
        
        # Don't use GPT for clear signals
        if confidence >= 70:
            return False
        
        # Use GPT for ambiguous situations
        if confidence < 60 and compiled_score < 0.3:
            return True
        
        # Use GPT if there are many conflicting signals
        if local_analysis["signal_count"] > 8:
            return True
        
        return False

    def _gpt_analysis(self, data: CompiledMarketData, local_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Call GPT for final strategic analysis (minimizing API calls).
        
        This should only be called for ambiguous or critical decisions.
        """
        if not self._openai_api_key:
            return {"error": "OpenAI API key not configured"}
        
        try:
            import openai
            
            client = openai.OpenAI(api_key=self._openai_api_key)
            
            # Prepare concise summary for GPT
            prompt = self._prepare_gpt_prompt(data, local_analysis)
            
            response = client.chat.completions.create(
                model="gpt-5",  # Use mini for cost efficiency
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert cryptocurrency trading analyst. Provide concise, actionable insights based on market data. Focus on risk assessment and key decision factors.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                max_tokens=300,
                temperature=0.3,  # Lower temperature for more consistent analysis
            )
            
            gpt_recommendation = response.choices[0].message.content
            
            return {
                "gpt_recommendation": gpt_recommendation,
                "model_used": "gpt-4o-mini",
                "tokens_used": response.usage.total_tokens,
            }
            
        except Exception as exc:
            return {"error": f"GPT analysis failed: {exc}"}

    def _prepare_gpt_prompt(self, data: CompiledMarketData, local_analysis: Dict[str, Any]) -> str:
        """Prepare a concise prompt for GPT with all relevant information."""
        coin = data.coin_metrics
        sentiment = data.market_sentiment
        global_market = data.global_market
        
        prompt = f"""Analyze this trading opportunity for {coin.symbol}:

PRICE DATA:
- Current: ${coin.current_price:,.2f}
- 24h Change: {coin.price_change_24h:+.2f}%
- 7d Change: {coin.price_change_7d:+.2f}% (if available)
- Market Cap: ${coin.market_cap:,.0f}
- 24h Volume: ${coin.volume_24h:,.0f}

MARKET SENTIMENT:
- Fear & Greed Index: {sentiment.fear_greed_index} ({sentiment.fear_greed_classification})
- Action Bias: {sentiment.action_bias}

GLOBAL MARKET:
- Total Market Cap Change 24h: {global_market.market_cap_change_24h:+.2f}%
- BTC Dominance: {global_market.btc_dominance:.1f}%

LOCAL ANALYSIS:
- Recommended Action: {local_analysis['action']}
- Confidence: {local_analysis['confidence']}%
- Compiled Score: {data.compiled_score:.2f}
- Key Signals: {', '.join(local_analysis['signals'][:5])}

NEWS SENTIMENT: {data.news_summary['sentiment']}
Recent Headlines: {', '.join(data.news_summary['recent_headlines'][:3])}

Given this data, provide:
1. Your assessment of the current opportunity
2. Key risks to consider
3. Recommended action (BUY/SELL/HOLD) with confidence %
4. One critical factor to monitor

Keep response under 200 words."""
        
        return prompt

    def _generate_recommendation(
        self,
        local_analysis: Dict[str, Any],
        gpt_analysis: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Generate final trading recommendation."""
        
        # Start with local analysis
        action = local_analysis["action"]
        confidence = local_analysis["confidence"]
        reasoning = local_analysis["signals"]
        
        # Enhance with GPT if available
        if gpt_analysis and "gpt_recommendation" in gpt_analysis:
            # GPT provides additional context but doesn't override strong local signals
            if confidence < 60:
                # For low confidence, give GPT more weight
                reasoning.append(f"GPT Analysis: {gpt_analysis['gpt_recommendation'][:200]}")
        
        return {
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning,
            "risk_level": local_analysis["risk_level"],
            "market_conditions": local_analysis["market_conditions"],
            "gpt_enhanced": gpt_analysis is not None,
        }

    def _calculate_risk_level(self, data: CompiledMarketData) -> str:
        """Calculate overall risk level."""
        risk_score = 0
        
        # High volatility = high risk
        if abs(data.coin_metrics.price_change_24h) > 10:
            risk_score += 2
        elif abs(data.coin_metrics.price_change_24h) > 5:
            risk_score += 1
        
        # Extreme Fear/Greed = high risk
        if data.market_sentiment.fear_greed_index <= 20 or data.market_sentiment.fear_greed_index >= 80:
            risk_score += 2
        
        # Low volume = high risk
        if data.coin_metrics.market_cap > 0:
            volume_ratio = data.coin_metrics.volume_24h / data.coin_metrics.market_cap
            if volume_ratio < 0.05:
                risk_score += 1
        
        if risk_score >= 4:
            return "HIGH"
        elif risk_score >= 2:
            return "MEDIUM"
        else:
            return "LOW"

    def _describe_market_conditions(self, data: CompiledMarketData) -> str:
        """Describe current market conditions in plain language."""
        conditions = []
        
        # Price trend
        if data.coin_metrics.price_change_24h > 3:
            conditions.append("strong uptrend")
        elif data.coin_metrics.price_change_24h > 0:
            conditions.append("uptrend")
        elif data.coin_metrics.price_change_24h < -3:
            conditions.append("strong downtrend")
        elif data.coin_metrics.price_change_24h < 0:
            conditions.append("downtrend")
        else:
            conditions.append("sideways")
        
        # Market sentiment
        if data.market_sentiment.fear_greed_index <= 25:
            conditions.append("extreme fear")
        elif data.market_sentiment.fear_greed_index >= 75:
            conditions.append("extreme greed")
        
        # Volume
        if data.coin_metrics.market_cap > 0:
            volume_ratio = data.coin_metrics.volume_24h / data.coin_metrics.market_cap
            if volume_ratio > 0.3:
                conditions.append("high volume")
            elif volume_ratio < 0.05:
                conditions.append("low volume")
        
        return ", ".join(conditions) if conditions else "neutral"


__all__ = ["SentimentAnalyzer"]

