"""CryptoCompare API client for social and on-chain metrics."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class CryptoCompareClient:
    """Client for CryptoCompare API with rate limiting."""

    BASE_URL = "https://min-api.cryptocompare.com/data"
    
    # CryptoCompare free tier: ~100,000 calls/month, ~50/hour recommended
    RATE_LIMIT_CALLS = 45
    RATE_LIMIT_PERIOD = 3600  # 1 hour in seconds

    def __init__(self, api_key: Optional[str] = None, cache_manager=None) -> None:
        self._api_key = api_key
        self._cache = cache_manager
        self._session = self._create_session()
        self._call_timestamps: List[float] = []

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        if self._api_key:
            session.headers.update({"authorization": f"Apikey {self._api_key}"})
        
        return session

    def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        now = time.time()
        
        self._call_timestamps = [
            ts for ts in self._call_timestamps 
            if now - ts < self.RATE_LIMIT_PERIOD
        ]
        
        if len(self._call_timestamps) >= self.RATE_LIMIT_CALLS:
            sleep_time = self.RATE_LIMIT_PERIOD - (now - self._call_timestamps[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
                self._call_timestamps = []
        
        self._call_timestamps.append(now)

    def _make_request(self, endpoint: str, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Make API request with rate limiting."""
        cache_key = f"cryptocompare:{endpoint}:{str(params)}"
        
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached
        
        self._rate_limit()
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            response = self._session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("Response") == "Error":
                raise RuntimeError(f"CryptoCompare API error: {data.get('Message', 'Unknown error')}")
            
            if self._cache:
                self._cache.set(cache_key, data, ttl=600)  # 10 minutes
            
            return data
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"CryptoCompare API error: {exc}") from exc

    def get_social_stats(self, coin_id: int) -> Dict[str, Any]:
        """Get social media statistics for a coin.
        
        Parameters
        ----------
        coin_id : int
            CryptoCompare coin ID
            
        Returns
        -------
        Dict containing social media stats (Twitter, Reddit, etc.)
        """
        return self._make_request(f"social/coin/latest", {"coinId": coin_id})

    def get_latest_social_stats(self, symbol: str) -> Dict[str, Any]:
        """Get latest social stats by symbol.
        
        Parameters
        ----------
        symbol : str
            Coin symbol (e.g., 'BTC', 'ETH')
            
        Returns
        -------
        Dict containing social stats
        """
        params = {"fsym": symbol}
        return self._make_request("social/coin/latest", params)

    def get_news(self, categories: str = "BTC,ETH,trading", lang: str = "EN") -> List[Dict[str, Any]]:
        """Get latest crypto news.
        
        Parameters
        ----------
        categories : str
            Comma-separated categories
        lang : str
            Language code (EN, ES, etc.)
            
        Returns
        -------
        List of news articles
        """
        params = {
            "categories": categories,
            "lang": lang,
        }
        
        data = self._make_request("v2/news/", params)
        return data.get("Data", [])

    def get_top_exchanges_by_volume(self, symbol: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top exchanges by trading volume for a symbol.
        
        Parameters
        ----------
        symbol : str
            Coin symbol
        limit : int
            Number of exchanges to return
            
        Returns
        -------
        List of exchanges with volume data
        """
        params = {
            "fsym": symbol,
            "tsym": "USD",
            "limit": limit,
        }
        
        data = self._make_request("top/exchanges/full", params)
        return data.get("Data", {}).get("Exchanges", [])

    def get_on_chain_stats(self, symbol: str) -> Dict[str, Any]:
        """Get on-chain blockchain statistics.
        
        Parameters
        ----------
        symbol : str
            Coin symbol
            
        Returns
        -------
        Dict containing on-chain metrics
        """
        params = {"fsym": symbol, "tsym": "USD"}
        return self._make_request("blockchain/latest", params)

    def get_price_multi(self, symbols: List[str], currencies: List[str] = ["USD"]) -> Dict[str, Any]:
        """Get prices for multiple symbols.
        
        Parameters
        ----------
        symbols : List[str]
            List of coin symbols
        currencies : List[str]
            List of target currencies
            
        Returns
        -------
        Dict mapping symbols to prices
        """
        params = {
            "fsyms": ",".join(symbols),
            "tsyms": ",".join(currencies),
        }
        
        return self._make_request("pricemulti", params)

    def get_historical_daily(
        self,
        symbol: str,
        to_symbol: str = "USD",
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """Get historical daily OHLCV data.
        
        Parameters
        ----------
        symbol : str
            Coin symbol
        to_symbol : str
            Target currency
        limit : int
            Number of days
            
        Returns
        -------
        List of daily candles
        """
        params = {
            "fsym": symbol,
            "tsym": to_symbol,
            "limit": limit,
        }
        
        data = self._make_request("v2/histoday", params)
        return data.get("Data", {}).get("Data", [])

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Normalize Binance symbol to CryptoCompare format.
        
        Parameters
        ----------
        symbol : str
            Binance symbol (e.g., 'BTCUSDT')
            
        Returns
        -------
        str : CryptoCompare symbol (e.g., 'BTC')
        """
        return symbol.replace("USDT", "").replace("BUSD", "").replace("USDC", "").upper()


__all__ = ["CryptoCompareClient"]

