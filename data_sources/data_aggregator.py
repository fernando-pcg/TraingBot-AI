"""Data aggregator that compiles information from multiple sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from data_sources.cache_manager import CacheManager
from data_sources.coingecko_client import CoinGeckoClient
from data_sources.cryptocompare_client import CryptoCompareClient
from data_sources.fear_greed_client import FearGreedClient


@dataclass
class MarketSentiment:
    """Compiled market sentiment data."""
    
    fear_greed_index: int
    fear_greed_classification: str
    fear_greed_score: float  # -1 to 1
    action_bias: str
    recommendation: str


@dataclass
class CoinMetrics:
    """Compiled metrics for a specific coin."""
    
    symbol: str
    current_price: float
    market_cap: float
    volume_24h: float
    price_change_24h: float
    price_change_7d: Optional[float]
    market_cap_rank: Optional[int]
    social_score: Optional[float]
    sentiment_score: float  # Combined sentiment


@dataclass
class GlobalMarketData:
    """Global market overview."""
    
    total_market_cap: float
    total_volume_24h: float
    btc_dominance: float
    eth_dominance: float
    active_cryptocurrencies: int
    market_cap_change_24h: float


@dataclass
class CompiledMarketData:
    """All compiled market data for decision making."""
    
    coin_metrics: CoinMetrics
    market_sentiment: MarketSentiment
    global_market: GlobalMarketData
    trending_coins: List[str]
    news_summary: Dict[str, Any]
    compiled_score: float  # Overall market score -1 to 1
    timestamp: float


class DataAggregator:
    """Aggregates data from multiple free APIs."""

    def __init__(
        self,
        cache_db_path: str = "data/cache.db",
        cryptocompare_api_key: Optional[str] = None,
    ) -> None:
        self._cache = CacheManager(cache_db_path)
        self._coingecko = CoinGeckoClient(cache_manager=self._cache)
        self._cryptocompare = CryptoCompareClient(
            api_key=cryptocompare_api_key,
            cache_manager=self._cache,
        )
        self._feargreed = FearGreedClient(cache_manager=self._cache)

    def get_compiled_data(self, symbol: str) -> CompiledMarketData:
        """Compile all available data for a trading symbol.
        
        Parameters
        ----------
        symbol : str
            Trading symbol (e.g., 'BTCUSDT')
            
        Returns
        -------
        CompiledMarketData with all aggregated information
        """
        import time
        
        # Get coin metrics
        coin_metrics = self._get_coin_metrics(symbol)
        
        # Get market sentiment
        market_sentiment = self._get_market_sentiment()
        
        # Get global market data
        global_market = self._get_global_market_data()
        
        # Get trending coins
        trending_coins = self._get_trending_coins()
        
        # Get news summary
        news_summary = self._get_news_summary(symbol)
        
        # Calculate compiled score
        compiled_score = self._calculate_compiled_score(
            coin_metrics=coin_metrics,
            market_sentiment=market_sentiment,
            global_market=global_market,
        )
        
        return CompiledMarketData(
            coin_metrics=coin_metrics,
            market_sentiment=market_sentiment,
            global_market=global_market,
            trending_coins=trending_coins,
            news_summary=news_summary,
            compiled_score=compiled_score,
            timestamp=time.time(),
        )

    def _get_coin_metrics(self, symbol: str) -> CoinMetrics:
        """Gather metrics for specific coin."""
        coin_id = CoinGeckoClient.symbol_to_coin_id(symbol)
        cc_symbol = CryptoCompareClient.normalize_symbol(symbol)
        
        # Get CoinGecko data
        try:
            cg_market = self._coingecko.get_coin_market_data(coin_id)
            market_data = cg_market.get("market_data", {})
            
            current_price = market_data.get("current_price", {}).get("usd", 0)
            market_cap = market_data.get("market_cap", {}).get("usd", 0)
            volume_24h = market_data.get("total_volume", {}).get("usd", 0)
            price_change_24h = market_data.get("price_change_percentage_24h", 0)
            price_change_7d = market_data.get("price_change_percentage_7d", None)
            market_cap_rank = market_data.get("market_cap_rank", None)
        except Exception:
            # Fallback to simple price API
            try:
                cg_price = self._coingecko.get_coin_price(coin_id)
                coin_data = cg_price.get(coin_id, {})
                
                current_price = coin_data.get("usd", 0)
                market_cap = coin_data.get("usd_market_cap", 0)
                volume_24h = coin_data.get("usd_24h_vol", 0)
                price_change_24h = coin_data.get("usd_24h_change", 0)
                price_change_7d = None
                market_cap_rank = None
            except Exception:
                current_price = 0
                market_cap = 0
                volume_24h = 0
                price_change_24h = 0
                price_change_7d = None
                market_cap_rank = None
        
        # Get social score from CryptoCompare (optional)
        social_score = None
        try:
            social = self._cryptocompare.get_latest_social_stats(cc_symbol)
            if social.get("Data"):
                # Calculate simple social score from available metrics
                social_data = social["Data"]
                twitter_followers = social_data.get("Twitter", {}).get("followers", 0)
                reddit_subscribers = social_data.get("Reddit", {}).get("subscribers", 0)
                
                # Normalize to 0-100 scale (very rough approximation)
                social_score = min(100, (twitter_followers / 1000 + reddit_subscribers / 100))
        except Exception:
            pass
        
        # Calculate sentiment score (-1 to 1) based on price changes
        sentiment = self._calculate_coin_sentiment(
            price_change_24h=price_change_24h,
            price_change_7d=price_change_7d,
            social_score=social_score,
        )
        
        return CoinMetrics(
            symbol=symbol,
            current_price=current_price,
            market_cap=market_cap,
            volume_24h=volume_24h,
            price_change_24h=price_change_24h,
            price_change_7d=price_change_7d,
            market_cap_rank=market_cap_rank,
            social_score=social_score,
            sentiment_score=sentiment,
        )

    def _get_market_sentiment(self) -> MarketSentiment:
        """Get overall market sentiment from Fear & Greed Index."""
        try:
            fg_current = self._feargreed.get_current_index()
            fg_value = int(fg_current.get("value", 50))
            fg_score = self._feargreed.get_sentiment_score()
            fg_interpret = self._feargreed.interpret_index(fg_value)
            
            return MarketSentiment(
                fear_greed_index=fg_value,
                fear_greed_classification=fg_interpret["classification"],
                fear_greed_score=fg_score,
                action_bias=fg_interpret["action_bias"],
                recommendation=fg_interpret["recommendation"],
            )
        except Exception:
            # Return neutral sentiment on error
            return MarketSentiment(
                fear_greed_index=50,
                fear_greed_classification="Neutral",
                fear_greed_score=0.0,
                action_bias="neutral",
                recommendation="Wait for clearer signals",
            )

    def _get_global_market_data(self) -> GlobalMarketData:
        """Get global cryptocurrency market data."""
        try:
            global_data = self._coingecko.get_global_market_data()
            data = global_data.get("data", {})
            
            total_market_cap = data.get("total_market_cap", {}).get("usd", 0)
            total_volume_24h = data.get("total_volume", {}).get("usd", 0)
            
            market_cap_pct = data.get("market_cap_percentage", {})
            btc_dominance = market_cap_pct.get("btc", 0)
            eth_dominance = market_cap_pct.get("eth", 0)
            
            active_cryptocurrencies = data.get("active_cryptocurrencies", 0)
            
            market_cap_change_24h = data.get("market_cap_change_percentage_24h_usd", 0)
            
            return GlobalMarketData(
                total_market_cap=total_market_cap,
                total_volume_24h=total_volume_24h,
                btc_dominance=btc_dominance,
                eth_dominance=eth_dominance,
                active_cryptocurrencies=active_cryptocurrencies,
                market_cap_change_24h=market_cap_change_24h,
            )
        except Exception:
            return GlobalMarketData(
                total_market_cap=0,
                total_volume_24h=0,
                btc_dominance=0,
                eth_dominance=0,
                active_cryptocurrencies=0,
                market_cap_change_24h=0,
            )

    def _get_trending_coins(self) -> List[str]:
        """Get list of trending coin symbols."""
        try:
            trending = self._coingecko.get_trending_coins()
            return [coin["item"]["symbol"].upper() for coin in trending[:5]]
        except Exception:
            return []

    def _get_news_summary(self, symbol: str) -> Dict[str, Any]:
        """Get recent news summary."""
        cc_symbol = CryptoCompareClient.normalize_symbol(symbol)
        
        try:
            news = self._cryptocompare.get_news(categories=f"{cc_symbol},trading")
            
            if not news:
                return {"count": 0, "recent_headlines": [], "sentiment": "neutral"}
            
            # Get top 5 most recent
            recent = news[:5]
            headlines = [article.get("title", "") for article in recent]
            
            # Simple sentiment based on title keywords
            sentiment = self._analyze_headlines_sentiment(headlines)
            
            return {
                "count": len(news),
                "recent_headlines": headlines,
                "sentiment": sentiment,
            }
        except Exception:
            return {"count": 0, "recent_headlines": [], "sentiment": "neutral"}

    def _analyze_headlines_sentiment(self, headlines: List[str]) -> str:
        """Simple keyword-based sentiment analysis."""
        if not headlines:
            return "neutral"
        
        positive_keywords = ["bullish", "surge", "rally", "gain", "up", "high", "growth", "profit"]
        negative_keywords = ["bearish", "crash", "drop", "fall", "down", "low", "loss", "risk"]
        
        positive_count = 0
        negative_count = 0
        
        for headline in headlines:
            headline_lower = headline.lower()
            positive_count += sum(1 for kw in positive_keywords if kw in headline_lower)
            negative_count += sum(1 for kw in negative_keywords if kw in headline_lower)
        
        if positive_count > negative_count * 1.5:
            return "positive"
        elif negative_count > positive_count * 1.5:
            return "negative"
        else:
            return "neutral"

    def _calculate_coin_sentiment(
        self,
        price_change_24h: float,
        price_change_7d: Optional[float],
        social_score: Optional[float],
    ) -> float:
        """Calculate coin-specific sentiment score.
        
        Returns
        -------
        float : Score from -1 (very bearish) to 1 (very bullish)
        """
        score = 0.0
        
        # Price change 24h (-1 to 1)
        if price_change_24h != 0:
            score += max(-1, min(1, price_change_24h / 10))  # Normalize around 10% change
        
        # Price change 7d (if available)
        if price_change_7d is not None:
            score += max(-1, min(1, price_change_7d / 20)) * 0.5  # Less weight, normalize around 20%
        
        # Social score (if available)
        if social_score is not None:
            # Normalize 0-100 to -0.2 to 0.2
            score += ((social_score - 50) / 50) * 0.2
        
        # Normalize final score to -1 to 1
        return max(-1, min(1, score))

    def _calculate_compiled_score(
        self,
        coin_metrics: CoinMetrics,
        market_sentiment: MarketSentiment,
        global_market: GlobalMarketData,
    ) -> float:
        """Calculate overall compiled market score.
        
        Returns
        -------
        float : Score from -1 (very bearish) to 1 (very bullish)
        """
        scores = []
        weights = []
        
        # Coin sentiment (40% weight)
        scores.append(coin_metrics.sentiment_score)
        weights.append(0.4)
        
        # Fear & Greed (30% weight)
        scores.append(market_sentiment.fear_greed_score)
        weights.append(0.3)
        
        # Global market momentum (30% weight)
        global_score = max(-1, min(1, global_market.market_cap_change_24h / 5))
        scores.append(global_score)
        weights.append(0.3)
        
        # Weighted average
        weighted_score = sum(s * w for s, w in zip(scores, weights))
        
        return max(-1, min(1, weighted_score))

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self._cache.get_stats()

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear_all()

    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries."""
        return self._cache.clear_expired()


__all__ = ["DataAggregator", "CompiledMarketData", "CoinMetrics", "MarketSentiment", "GlobalMarketData"]

