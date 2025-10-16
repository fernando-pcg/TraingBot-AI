"""Risk management utilities providing stop-loss and position sizing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class RiskParameters:
    """Risk parameters used throughout the risk manager."""

    capital: float
    risk_percent: float
    stop_loss_pct: float
    take_profit_pct: float


class RiskManager:
    """Risk manager providing core calculations."""

    def __init__(self, max_daily_loss_pct: float, max_exposure_pct: float = 0.3) -> None:
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_exposure_pct = max_exposure_pct

    @staticmethod
    def calculate_position_size(capital: float, risk_percent: float, stop_loss_pct: float) -> float:
        risk_amount = capital * risk_percent
        if stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be greater than 0")
        position_size = risk_amount / stop_loss_pct
        return max(position_size, 0)

    def should_open_position(self, current_exposure: float, capital: float) -> bool:
        exposure_pct = current_exposure / capital if capital else 0
        return exposure_pct < self.max_exposure_pct

    @staticmethod
    def calculate_stop_loss(entry_price: float, volatility: float) -> float:
        return max(entry_price - entry_price * volatility, 0)

    @staticmethod
    def calculate_take_profit(entry_price: float, strategy_type: str, confidence: float) -> float:
        base_multiplier = 1 + confidence * 0.5
        if strategy_type == "scalping":
            base_multiplier = 1 + confidence * 0.2
        elif strategy_type == "swing":
            base_multiplier = 1 + confidence * 0.7
        return entry_price * base_multiplier

    def check_daily_limits(self, trades_today: pd.DataFrame, capital: float) -> bool:
        if trades_today.empty:
            return True
        total_pnl = trades_today["pnl"].sum()
        loss_pct = abs(min(total_pnl, 0)) / capital if capital else 0
        return loss_pct < self.max_daily_loss_pct

    def trailing_stop(self, current_price: float, peak_price: float, trailing_pct: float) -> float:
        if trailing_pct <= 0:
            raise ValueError("trailing_pct must be greater than 0")
        return peak_price * (1 - trailing_pct)


__all__ = ["RiskManager", "RiskParameters"]


