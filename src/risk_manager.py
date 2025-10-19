"""Risk management utilities providing stop-loss and position sizing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import math

import pandas as pd


@dataclass
class RiskParameters:
    """Risk parameters used throughout the risk manager."""

    capital: float
    risk_percent: float
    stop_loss_pct: float
    take_profit_pct: float


class RiskManager:
    """Risk manager providing core calculations with advanced features."""

    def __init__(self, max_daily_loss_pct: float, max_exposure_pct: float = 0.3) -> None:
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_exposure_pct = max_exposure_pct
        self.current_drawdown = 0.0
        self.peak_capital = 0.0
        self.trading_paused = False

    @staticmethod
    def calculate_position_size(capital: float, risk_percent: float, stop_loss_pct: float) -> float:
        """Calculate basic position size based on risk percentage."""
        risk_amount = capital * risk_percent
        if stop_loss_pct <= 0:
            raise ValueError("stop_loss_pct must be greater than 0")
        position_size = risk_amount / stop_loss_pct
        return max(position_size, 0)
    
    def calculate_dynamic_position_size(
        self,
        capital: float,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        stop_loss_pct: float,
        volatility: float = 0.02,
    ) -> float:
        """
        Calculate position size using Kelly Criterion with safeguards.
        
        Kelly Criterion: f = (p * b - q) / b
        where:
        - p = win probability
        - q = loss probability (1-p)
        - b = win/loss ratio
        
        We use fractional Kelly (0.25) for safety.
        """
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            # Fallback to basic calculation
            return self.calculate_position_size(capital, 0.02, stop_loss_pct)
        
        win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 1.5
        kelly_fraction = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        # Use fractional Kelly (25%) for safety
        fractional_kelly = max(0.01, min(kelly_fraction * 0.25, 0.05))
        
        # Adjust by volatility - reduce size in high volatility
        volatility_adjustment = 1.0 / (1 + volatility * 10)
        
        # Adjust by current drawdown - reduce size during drawdown
        drawdown_adjustment = 1.0 if self.current_drawdown < 0.05 else 0.5
        
        risk_percent = fractional_kelly * volatility_adjustment * drawdown_adjustment
        
        return self.calculate_position_size(capital, risk_percent, stop_loss_pct)

    def should_open_position(self, current_exposure: float, capital: float) -> bool:
        """Check if we can open a new position based on exposure and drawdown."""
        if self.trading_paused:
            return False
        
        exposure_pct = current_exposure / capital if capital else 0
        return exposure_pct < self.max_exposure_pct
    
    def update_drawdown(self, current_capital: float) -> None:
        """Update current drawdown and pause trading if necessary."""
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital
        
        if self.peak_capital > 0:
            self.current_drawdown = (self.peak_capital - current_capital) / self.peak_capital
            
            # Pause trading if drawdown > 3%
            if self.current_drawdown > 0.03:
                self.trading_paused = True
            # Resume trading if drawdown drops below 2%
            elif self.current_drawdown < 0.02:
                self.trading_paused = False

    @staticmethod
    def calculate_stop_loss(entry_price: float, volatility: float) -> float:
        return max(entry_price - entry_price * volatility, 0)
    
    def calculate_adaptive_stop_loss(self, entry_price: float, atr: float, base_stop_pct: float = 0.012) -> float:
        """
        Calculate adaptive stop loss based on ATR (Average True Range).
        Higher volatility = wider stops to avoid getting stopped out prematurely.
        """
        # ATR as percentage of price
        atr_pct = atr / entry_price if entry_price > 0 else base_stop_pct
        
        # Use max of base stop or 2x ATR
        adaptive_stop = max(base_stop_pct, atr_pct * 2.0)
        
        # Cap at 3% to avoid excessive risk
        adaptive_stop = min(adaptive_stop, 0.03)
        
        return entry_price * (1 - adaptive_stop)

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


