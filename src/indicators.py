"""Utility functions for computing technical indicators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import ADXIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands


@dataclass(frozen=True)
class IndicatorValues:
    """Container for the latest values of technical indicators."""

    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    bollinger_upper: float
    bollinger_middle: float
    bollinger_lower: float
    atr: float
    adx: float
    stochastic_k: float
    stochastic_d: float


class IndicatorComputationError(RuntimeError):
    """Raised when indicators cannot be computed due to data issues."""


def _validate_dataframe(df: pd.DataFrame) -> None:
    required_columns = {"close", "high", "low"}
    missing = required_columns - set(df.columns)
    if missing:
        raise IndicatorComputationError(f"Missing required columns: {missing}")

    if len(df) < 50:
        raise IndicatorComputationError("Not enough historical data to compute indicators")


def _get_latest(series: pd.Series) -> float:
    value = series.iloc[-1]
    if np.isnan(value):
        raise IndicatorComputationError("Indicator returned NaN value")
    return float(value)


def calculate_indicators(df: pd.DataFrame) -> IndicatorValues:
    """Calculate a set of core technical indicators.

    Parameters
    ----------
    df: pd.DataFrame
        DataFrame containing at least ``close``, ``high`` and ``low`` columns.

    Returns
    -------
    IndicatorValues
        Latest values for the configured indicators.

    Raises
    ------
    IndicatorComputationError
        If the indicators cannot be computed.
    """

    _validate_dataframe(df)

    close = df["close"]
    high = df["high"]
    low = df["low"]

    rsi_indicator = RSIIndicator(close=close, window=14)
    macd_indicator = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
    bollinger = BollingerBands(close=close, window=20, window_dev=2)
    atr_indicator = AverageTrueRange(high=high, low=low, close=close, window=14)
    adx_indicator = ADXIndicator(high=high, low=low, close=close, window=14)
    stochastic = StochasticOscillator(high=high, low=low, close=close, window=14, smooth_window=3)

    return IndicatorValues(
        rsi=_get_latest(rsi_indicator.rsi()),
        macd=_get_latest(macd_indicator.macd()),
        macd_signal=_get_latest(macd_indicator.macd_signal()),
        macd_histogram=_get_latest(macd_indicator.macd_diff()),
        bollinger_upper=_get_latest(bollinger.bollinger_hband()),
        bollinger_middle=_get_latest(bollinger.bollinger_mavg()),
        bollinger_lower=_get_latest(bollinger.bollinger_lband()),
        atr=_get_latest(atr_indicator.average_true_range()),
        adx=_get_latest(adx_indicator.adx()),
        stochastic_k=_get_latest(stochastic.stoch()),
        stochastic_d=_get_latest(stochastic.stoch_signal()),
    )


__all__ = ["IndicatorValues", "IndicatorComputationError", "calculate_indicators"]


