"""Basic strategy implementation with indicator validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD


@dataclass
class Signal:
    symbol: str
    action: str
    confidence: float
    reason: str


class Strategy:
    """Simple technical strategy using RSI and MACD confirmations."""

    def __init__(self, min_volume: float = 0, rsi_bounds: tuple[int, int] = (30, 70), aggressive: bool = False) -> None:
        self.min_volume = min_volume
        if aggressive:
            self.rsi_lower, self.rsi_upper = (45, 55)
        else:
            self.rsi_lower, self.rsi_upper = rsi_bounds

    def validate_data(self, df: pd.DataFrame) -> None:
        required_cols = {"close", "volume"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Data missing required columns: {missing}")
        if df["close"].isna().any():
            raise ValueError("Close prices contain NaN")

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> Signal | None:
        self.validate_data(df)

        if df["volume"].iloc[-1] < self.min_volume:
            return None

        if len(df) < 26:
            return None

        rsi = RSIIndicator(df["close"], window=14).rsi().iloc[-1]
        macd_indicator = MACD(df["close"])
        macd = macd_indicator.macd_diff().iloc[-1]
        
        price_change = (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100
        
        if rsi < self.rsi_lower and macd > 0:
            return Signal(symbol=symbol, action="buy", confidence=0.7, reason="RSI oversold + MACD bullish")
        if rsi > self.rsi_upper and macd < 0:
            return Signal(symbol=symbol, action="sell", confidence=0.7, reason="RSI overbought + MACD bearish")
        
        if rsi < 40 and price_change > 0.1:
            return Signal(symbol=symbol, action="buy", confidence=0.6, reason="RSI low + positive momentum")
        if rsi > 60 and price_change < -0.1:
            return Signal(symbol=symbol, action="sell", confidence=0.6, reason="RSI high + negative momentum")
        
        return None


__all__ = ["Strategy", "Signal"]


