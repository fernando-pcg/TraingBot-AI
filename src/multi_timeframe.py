"""Helpers for analysing multiple timeframes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

import pandas as pd

from src.data_pipeline import DataPipeline
from src.indicators import (
    IndicatorComputationError,
    IndicatorValues,
    calculate_indicators,
)


@dataclass(frozen=True)
class TimeframeSummary:
    """Summary of indicator readings for a given timeframe."""

    interval: str
    indicators: IndicatorValues
    trend_pct: float
    close: float


class MultiTimeframeAnalyzer:
    """Fetch and evaluate price action across multiple timeframes."""

    def __init__(
        self,
        client,
        intervals: Sequence[str] | None = None,
        candle_limit: int = 200,
        trend_window: int = 5,
    ) -> None:
        self._pipeline = DataPipeline(client)
        self._intervals = tuple(dict.fromkeys(intervals or ("5m", "15m", "1h")))
        self._candle_limit = max(candle_limit, 100)
        self._trend_window = max(trend_window, 3)

    def fetch(self, symbol: str) -> List[TimeframeSummary]:
        summaries: List[TimeframeSummary] = []

        for interval in self._intervals:
            df = self._pipeline.get_recent_candles(symbol, interval=interval, limit=self._candle_limit)
            if df.empty or len(df) < 50:
                continue

            df = df.sort_values("timestamp")

            try:
                indicators = calculate_indicators(df)
            except IndicatorComputationError:
                continue

            trend_pct = self._calculate_trend(df)
            close_price = float(df["close"].iloc[-1])

            summaries.append(
                TimeframeSummary(
                    interval=interval,
                    indicators=indicators,
                    trend_pct=trend_pct,
                    close=close_price,
                )
            )

        return summaries

    def _calculate_trend(self, df: pd.DataFrame) -> float:
        if len(df) < self._trend_window + 1:
            return 0.0

        recent = df["close"].tail(self._trend_window + 1)
        if recent.iloc[0] == 0:
            return 0.0

        return (recent.iloc[-1] / recent.iloc[0] - 1) * 100


__all__ = ["MultiTimeframeAnalyzer", "TimeframeSummary"]


