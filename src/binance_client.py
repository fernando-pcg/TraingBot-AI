"""Binance client wrapper with environment awareness."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict

from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL
from binance.exceptions import BinanceAPIException

from config import Config


TESTNET_REST_URL = "https://testnet.binance.vision/api"
TESTNET_WEBSOCKET_URL = "wss://testnet.binance.vision/ws"


@dataclass
class OrderResult:
    """Simple result container for orders."""

    order_id: str
    symbol: str
    status: str
    executed_qty: float
    cummulative_quote_qty: float
    fills: list[dict[str, Any]]


class BinanceClientWrapper:
    """Wrapper around python-binance with support for live/testnet modes."""

    def __init__(self, config: Config, logger) -> None:
        self._config = config
        self._logger = logger

        self._client = Client(
            config.binance.api_key,
            config.binance.api_secret,
            tld="com",
            testnet=config.binance.use_testnet,
            requests_params={"timeout": 10},
        )

        if config.binance.use_testnet or (config.environment and config.environment.value == "testnet"):
            self._logger.info("Configuring Binance client for testnet mode")
            self._client.API_URL = TESTNET_REST_URL
            self._client.WSS_URL = TESTNET_WEBSOCKET_URL

    def validate_environment(self, symbol: str) -> None:
        """Ensure client operates under the correct environment."""

        try:
            self._client.ping()
        except BinanceAPIException as exc:
            self._logger.error("Binance API error during ping: %s", exc)
            raise
        self._logger.debug("Environment validation passed for symbol %s", symbol)

    def get_account_info(self) -> Dict[str, Any]:
        """Retrieve account information."""

        return self._client.get_account()

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list[list]:
        """Fetch historical klines (candlestick) data."""
        try:
            return self._client.get_klines(symbol=symbol, interval=interval, limit=limit)
        except BinanceAPIException as exc:
            self._logger.error("Failed to fetch klines for %s: %s", symbol, exc)
            raise

    def get_symbol_ticker(self, symbol: str) -> Dict[str, Any]:
        """Get current price ticker for a symbol."""
        try:
            return self._client.get_symbol_ticker(symbol=symbol)
        except BinanceAPIException as exc:
            self._logger.error("Failed to fetch ticker for %s: %s", symbol, exc)
            raise

    def get_asset_balance(self, asset: str) -> Dict[str, str]:
        """Get balance for a specific asset."""
        try:
            return self._client.get_asset_balance(asset=asset)
        except BinanceAPIException as exc:
            self._logger.error("Failed to fetch balance for %s: %s", asset, exc)
            raise

    def place_market_order(self, symbol: str, quantity: float, side: str) -> OrderResult:
        """Place a market order with basic retry logic."""

        self.validate_environment(symbol)

        order_side = SIDE_BUY if side.lower() == "buy" else SIDE_SELL
        for attempt in range(3):
            try:
                order = self._client.create_order(
                    symbol=symbol,
                    side=order_side,
                    type="MARKET",
                    quantity=quantity,
                )
                return OrderResult(
                    order_id=str(order["orderId"]),
                    symbol=order["symbol"],
                    status=order["status"],
                    executed_qty=float(order["executedQty"]),
                    cummulative_quote_qty=float(order["cummulativeQuoteQty"]),
                    fills=order.get("fills", []),
                )
            except BinanceAPIException as exc:
                self._logger.error("Binance order attempt %s failed: %s", attempt + 1, exc)
                if attempt == 2:
                    raise
                time.sleep(2)

        raise RuntimeError("Failed to place order after retries")


__all__ = ["BinanceClientWrapper", "OrderResult"]


