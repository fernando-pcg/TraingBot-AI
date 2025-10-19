"""Data sources package for external market data."""

from data_sources.cache_manager import CacheManager
from data_sources.coingecko_client import CoinGeckoClient
from data_sources.cryptocompare_client import CryptoCompareClient
from data_sources.data_aggregator import (
    CoinMetrics,
    CompiledMarketData,
    DataAggregator,
    GlobalMarketData,
    MarketSentiment,
)
from data_sources.fear_greed_client import FearGreedClient
from data_sources.sentiment_analyzer import SentimentAnalyzer

__all__ = [
    "CacheManager",
    "CoinGeckoClient",
    "CryptoCompareClient",
    "FearGreedClient",
    "DataAggregator",
    "SentimentAnalyzer",
    "CompiledMarketData",
    "CoinMetrics",
    "MarketSentiment",
    "GlobalMarketData",
]

