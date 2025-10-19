"""Data pipeline for fetching and processing market data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from src.binance_client import BinanceClientWrapper


class DataPipeline:
    """Pipeline for fetching and transforming market data."""

    def __init__(self, client: BinanceClientWrapper) -> None:
        self._client = client

    def get_recent_candles(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 100,
        include_indicators: bool = False,
    ) -> pd.DataFrame:
        """Fetch recent candlestick data and return as DataFrame."""
        
        klines = self._client.get_klines(symbol=symbol, interval=interval, limit=limit)
        
        df = pd.DataFrame(
            klines,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "number_of_trades",
                "taker_buy_base_asset_volume",
                "taker_buy_quote_asset_volume",
                "ignore",
            ],
        )
        
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        
        df = df[["timestamp", "open", "high", "low", "close", "volume"]]

        if include_indicators:
            df.set_index("timestamp", inplace=True)
            df.sort_index(inplace=True)
        
        return df

    def get_current_price(self, symbol: str) -> float:
        """Get current market price for a symbol."""
        ticker = self._client.get_symbol_ticker(symbol)
        return float(ticker["price"])


__all__ = ["DataPipeline"]


