"""CoinGecko API client for cryptocurrency market data."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class CoinGeckoClient:
    """Client for CoinGecko public API with rate limiting and caching."""

    BASE_URL = "https://api.coingecko.com/api/v3"
    
    # CoinGecko free tier: 10-50 calls/minute
    RATE_LIMIT_CALLS = 45
    RATE_LIMIT_PERIOD = 60  # seconds

    def __init__(self, cache_manager=None) -> None:
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
        
        return session

    def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        now = time.time()
        
        # Remove timestamps older than RATE_LIMIT_PERIOD
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

    def _make_request(self, endpoint: str, params: Dict[str, Any] | None = None) -> Dict[str, Any] | List[Any]:
        """Make API request with rate limiting."""
        cache_key = f"coingecko:{endpoint}:{str(params)}"
        
        # Check cache first
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
            
            # Cache the result
            if self._cache:
                self._cache.set(cache_key, data, ttl=300)  # 5 minutes
            
            return data
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"CoinGecko API error: {exc}") from exc

    def get_coin_price(self, coin_id: str, vs_currency: str = "usd") -> Dict[str, Any]:
        """Get current price for a coin.
        
        Parameters
        ----------
        coin_id : str
            CoinGecko coin ID (e.g., 'bitcoin', 'ethereum')
        vs_currency : str
            Target currency (default: 'usd')
            
        Returns
        -------
        Dict containing price data
        """
        params = {
            "ids": coin_id,
            "vs_currencies": vs_currency,
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_24hr_change": "true",
            "include_last_updated_at": "true",
        }
        
        return self._make_request("simple/price", params)

    def get_coin_market_data(self, coin_id: str, vs_currency: str = "usd") -> Dict[str, Any]:
        """Get comprehensive market data for a coin.
        
        Parameters
        ----------
        coin_id : str
            CoinGecko coin ID
        vs_currency : str
            Target currency
            
        Returns
        -------
        Dict containing comprehensive market data
        """
        params = {
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "true",
            "developer_data": "false",
            "sparkline": "false",
        }
        
        return self._make_request(f"coins/{coin_id}", params)

    def get_global_market_data(self) -> Dict[str, Any]:
        """Get global cryptocurrency market data.
        
        Returns
        -------
        Dict containing:
        - Total market cap
        - Total volume
        - Market cap percentage by coin
        - Active cryptocurrencies count
        """
        return self._make_request("global")

    def get_trending_coins(self) -> List[Dict[str, Any]]:
        """Get trending coins in the last 24 hours.
        
        Returns
        -------
        List of trending coins with search data
        """
        data = self._make_request("search/trending")
        return data.get("coins", [])

    def get_coin_market_chart(
        self,
        coin_id: str,
        vs_currency: str = "usd",
        days: int = 7,
    ) -> Dict[str, List]:
        """Get historical market data for a coin.
        
        Parameters
        ----------
        coin_id : str
            CoinGecko coin ID
        vs_currency : str
            Target currency
        days : int
            Number of days of historical data (1, 7, 14, 30, 90, 180, 365, max)
            
        Returns
        -------
        Dict containing prices, market_caps, total_volumes as time series
        """
        params = {
            "vs_currency": vs_currency,
            "days": days,
            "interval": "daily" if days > 1 else "hourly",
        }
        
        return self._make_request(f"coins/{coin_id}/market_chart", params)

    @staticmethod
    def symbol_to_coin_id(symbol: str) -> str:
        """Convert trading symbol to CoinGecko coin ID.
        
        Parameters
        ----------
        symbol : str
            Trading symbol (e.g., 'BTCUSDT', 'ETHUSDT')
            
        Returns
        -------
        str : CoinGecko coin ID
        """
        # Remove USDT, BUSD, etc.
        base_symbol = symbol.replace("USDT", "").replace("BUSD", "").replace("USDC", "").lower()
        
        # Map common symbols to CoinGecko IDs
        symbol_map = {
            "btc": "bitcoin",
            "eth": "ethereum",
            "bnb": "binancecoin",
            "xrp": "ripple",
            "ada": "cardano",
            "doge": "dogecoin",
            "sol": "solana",
            "dot": "polkadot",
            "matic": "matic-network",
            "avax": "avalanche-2",
            "shib": "shiba-inu",
            "link": "chainlink",
            "uni": "uniswap",
            "atom": "cosmos",
            "ltc": "litecoin",
            "etc": "ethereum-classic",
            "xlm": "stellar",
            "algo": "algorand",
            "trx": "tron",
            "vet": "vechain",
        }
        
        return symbol_map.get(base_symbol, base_symbol)


__all__ = ["CoinGeckoClient"]

