"""Fear & Greed Index API client."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests


class FearGreedClient:
    """Client for Crypto Fear & Greed Index API."""

    BASE_URL = "https://api.alternative.me"

    def __init__(self, cache_manager=None) -> None:
        self._cache = cache_manager
        self._last_call_time = 0
        self._min_call_interval = 2  # 2 seconds between calls (API doesn't have strict limits)

    def _rate_limit(self) -> None:
        """Simple rate limiting."""
        now = time.time()
        elapsed = now - self._last_call_time
        
        if elapsed < self._min_call_interval:
            time.sleep(self._min_call_interval - elapsed)
        
        self._last_call_time = time.time()

    def _make_request(self, endpoint: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Make API request with caching."""
        cache_key = f"feargreed:{endpoint}:{str(params)}"
        
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached
        
        self._rate_limit()
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if self._cache:
                # Cache for 1 hour (index updates once per day)
                self._cache.set(cache_key, data, ttl=3600)
            
            return data
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Fear & Greed API error: {exc}") from exc

    def get_current_index(self) -> Dict[str, Any]:
        """Get current Fear & Greed Index.
        
        Returns
        -------
        Dict containing:
        - value: Index value (0-100)
        - value_classification: Text classification (Extreme Fear, Fear, Neutral, Greed, Extreme Greed)
        - timestamp: Unix timestamp
        - time_until_update: Seconds until next update
        """
        data = self._make_request("fng/")
        
        if data.get("data") and len(data["data"]) > 0:
            return data["data"][0]
        
        return {}

    def get_historical_index(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get historical Fear & Greed Index values.
        
        Parameters
        ----------
        limit : int
            Number of days to retrieve (max 100+)
            
        Returns
        -------
        List of index values with timestamps
        """
        params = {"limit": limit}
        data = self._make_request("fng/", params)
        
        return data.get("data", [])

    def get_sentiment_score(self) -> float:
        """Get normalized sentiment score (-1 to 1).
        
        Returns
        -------
        float : Normalized score where:
        - -1.0 = Extreme Fear
        - -0.5 = Fear
        -  0.0 = Neutral
        -  0.5 = Greed
        -  1.0 = Extreme Greed
        """
        current = self.get_current_index()
        
        if not current:
            return 0.0
        
        value = int(current.get("value", 50))
        
        # Normalize from 0-100 to -1 to 1
        normalized = (value - 50) / 50
        return max(-1.0, min(1.0, normalized))

    def interpret_index(self, value: int) -> Dict[str, Any]:
        """Interpret the Fear & Greed Index value.
        
        Parameters
        ----------
        value : int
            Index value (0-100)
            
        Returns
        -------
        Dict containing interpretation and trading recommendation
        """
        if value <= 25:
            classification = "Extreme Fear"
            sentiment = "extreme_bearish"
            recommendation = "Potential buying opportunity - market oversold"
            action_bias = "bullish"
        elif value <= 45:
            classification = "Fear"
            sentiment = "bearish"
            recommendation = "Cautious buying - market nervous"
            action_bias = "slight_bullish"
        elif value <= 55:
            classification = "Neutral"
            sentiment = "neutral"
            recommendation = "Wait for clearer signals"
            action_bias = "neutral"
        elif value <= 75:
            classification = "Greed"
            sentiment = "bullish"
            recommendation = "Cautious selling - market euphoric"
            action_bias = "slight_bearish"
        else:
            classification = "Extreme Greed"
            sentiment = "extreme_bullish"
            recommendation = "Consider taking profits - market overbought"
            action_bias = "bearish"
        
        return {
            "value": value,
            "classification": classification,
            "sentiment": sentiment,
            "recommendation": recommendation,
            "action_bias": action_bias,
        }


__all__ = ["FearGreedClient"]

