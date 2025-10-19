"""Utilities for detecting classical price patterns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
from ta.momentum import RSIIndicator


@dataclass(frozen=True)
class PatternSignals:
    """Summary of detected bullish/bearish price patterns."""

    bullish: List[str]
    bearish: List[str]
    support: Optional[float]
    resistance: Optional[float]
    bullish_divergence: bool
    bearish_divergence: bool


def _latest_candle(df: pd.DataFrame) -> pd.Series:
    return df.iloc[-1]


def _previous_candle(df: pd.DataFrame) -> pd.Series:
    return df.iloc[-2]


def _body_size(candle: pd.Series) -> float:
    return abs(candle["close"] - candle["open"])


def _upper_shadow(candle: pd.Series) -> float:
    return candle["high"] - max(candle["open"], candle["close"])


def _lower_shadow(candle: pd.Series) -> float:
    return min(candle["open"], candle["close"]) - candle["low"]


def _detect_doji(df: pd.DataFrame) -> Optional[str]:
    candle = _latest_candle(df)
    body = _body_size(candle)
    range_ = candle["high"] - candle["low"]
    if range_ == 0:
        return None
    if body / range_ < 0.1:
        return "Doji"
    return None


def _detect_hammer(df: pd.DataFrame) -> Optional[str]:
    candle = _latest_candle(df)
    body = _body_size(candle)
    lower = _lower_shadow(candle)
    upper = _upper_shadow(candle)
    if body == 0:
        return None
    if lower > body * 2 and upper < body * 0.5:
        if candle["close"] > candle["open"]:
            return "Bullish Hammer"
        return "Bearish Hanging Man"
    return None


def _detect_engulfing(df: pd.DataFrame) -> Optional[str]:
    if len(df) < 2:
        return None
    current = _latest_candle(df)
    previous = _previous_candle(df)

    current_body = current["close"] - current["open"]
    previous_body = previous["close"] - previous["open"]

    if current_body > 0 and previous_body < 0:
        if current["close"] > previous["open"] and current["open"] < previous["close"]:
            return "Bullish Engulfing"
    if current_body < 0 and previous_body > 0:
        if current["close"] < previous["open"] and current["open"] > previous["close"]:
            return "Bearish Engulfing"
    return None


def _calculate_support_resistance(df: pd.DataFrame, lookback: int = 20) -> tuple[Optional[float], Optional[float]]:
    if len(df) < lookback:
        return None, None
    recent = df.tail(lookback)
    support = recent["low"].min()
    resistance = recent["high"].max()
    return support, resistance


def _detect_divergence(df: pd.DataFrame, rsi_series: pd.Series) -> tuple[bool, bool]:
    if len(rsi_series) < 5 or len(df) < 5:
        return False, False

    prices = df["close"].tail(5)
    rsis = rsi_series.tail(5)

    bullish = prices.iloc[-1] < prices.iloc[-2] and rsis.iloc[-1] > rsis.iloc[-2]
    bearish = prices.iloc[-1] > prices.iloc[-2] and rsis.iloc[-1] < rsis.iloc[-2]
    return bullish, bearish


def analyze_patterns(df: pd.DataFrame, lookback: int = 20) -> PatternSignals:
    """Analyze the most recent candles for classical price patterns."""

    if len(df) < 30:
        return PatternSignals([], [], None, None, False, False)

    bullish: List[str] = []
    bearish: List[str] = []

    doji = _detect_doji(df.tail(1))
    if doji:
        bullish.append(doji)
        bearish.append(doji)

    hammer = _detect_hammer(df.tail(1))
    if hammer:
        if "Bullish" in hammer:
            bullish.append(hammer)
        else:
            bearish.append(hammer)

    engulfing = _detect_engulfing(df.tail(2))
    if engulfing:
        if "Bullish" in engulfing:
            bullish.append(engulfing)
        else:
            bearish.append(engulfing)

    support, resistance = _calculate_support_resistance(df, lookback=lookback)

    rsi_series = RSIIndicator(close=df["close"], window=14).rsi()
    bullish_divergence, bearish_divergence = _detect_divergence(df, rsi_series)

    return PatternSignals(
        bullish=bullish,
        bearish=bearish,
        support=support,
        resistance=resistance,
        bullish_divergence=bullish_divergence,
        bearish_divergence=bearish_divergence,
    )


__all__ = ["PatternSignals", "analyze_patterns"]


