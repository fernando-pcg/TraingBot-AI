"""Advanced performance metrics for trading bot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict
import math

import pandas as pd
import numpy as np


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    
    total_pnl: float
    total_pnl_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    recovery_factor: float
    avg_trade_duration_minutes: float
    trades_per_hour: float
    best_trade: float
    worst_trade: float
    consecutive_wins: int
    consecutive_losses: int


class PerformanceAnalyzer:
    """Analyzer for trading performance metrics."""
    
    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """
        Calculate Sharpe Ratio.
        Higher is better. > 1.0 is good, > 2.0 is excellent.
        """
        if not returns or len(returns) < 2:
            return 0.0
        
        returns_array = np.array(returns)
        excess_returns = returns_array - risk_free_rate
        
        if np.std(excess_returns) == 0:
            return 0.0
        
        return np.mean(excess_returns) / np.std(excess_returns)
    
    @staticmethod
    def calculate_max_drawdown(capital_history: List[float]) -> tuple[float, float]:
        """
        Calculate maximum drawdown in absolute value and percentage.
        Returns: (max_drawdown_value, max_drawdown_pct)
        """
        if not capital_history:
            return 0.0, 0.0
        
        peak = capital_history[0]
        max_dd = 0.0
        max_dd_pct = 0.0
        
        for capital in capital_history:
            if capital > peak:
                peak = capital
            
            drawdown = peak - capital
            drawdown_pct = (drawdown / peak) if peak > 0 else 0.0
            
            if drawdown > max_dd:
                max_dd = drawdown
                max_dd_pct = drawdown_pct
        
        return max_dd, max_dd_pct
    
    @staticmethod
    def calculate_profit_factor(wins: List[float], losses: List[float]) -> float:
        """
        Calculate profit factor (total wins / total losses).
        > 1.0 is profitable, > 2.0 is excellent.
        """
        total_wins = sum(wins) if wins else 0.0
        total_losses = abs(sum(losses)) if losses else 0.0
        
        if total_losses == 0:
            return float('inf') if total_wins > 0 else 0.0
        
        return total_wins / total_losses
    
    @staticmethod
    def analyze_trades(trades: pd.DataFrame, start_capital: float, duration_minutes: float) -> PerformanceMetrics:
        """Analyze trades and return comprehensive metrics."""
        
        if trades.empty:
            return PerformanceMetrics(
                total_pnl=0.0,
                total_pnl_pct=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                max_drawdown_pct=0.0,
                recovery_factor=0.0,
                avg_trade_duration_minutes=0.0,
                trades_per_hour=0.0,
                best_trade=0.0,
                worst_trade=0.0,
                consecutive_wins=0,
                consecutive_losses=0,
            )
        
        # Basic metrics
        total_pnl = trades["pnl"].sum()
        total_pnl_pct = (total_pnl / start_capital) * 100 if start_capital > 0 else 0.0
        total_trades = len(trades)
        
        # Win/Loss metrics
        winning_trades = len(trades[trades["pnl"] > 0])
        losing_trades = len(trades[trades["pnl"] <= 0])
        win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0
        
        wins = trades[trades["pnl"] > 0]["pnl"].tolist()
        losses = trades[trades["pnl"] <= 0]["pnl"].tolist()
        
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0
        
        # Advanced metrics
        profit_factor = PerformanceAnalyzer.calculate_profit_factor(wins, losses)
        
        # Calculate capital history for drawdown
        capital_history = [start_capital]
        running_capital = start_capital
        for pnl in trades["pnl"]:
            running_capital += pnl
            capital_history.append(running_capital)
        
        max_dd, max_dd_pct = PerformanceAnalyzer.calculate_max_drawdown(capital_history)
        
        # Recovery factor = net profit / max drawdown
        recovery_factor = (total_pnl / max_dd) if max_dd > 0 else 0.0
        
        # Sharpe ratio
        returns = trades["pnl"].tolist()
        sharpe_ratio = PerformanceAnalyzer.calculate_sharpe_ratio(returns)
        
        # Trade duration
        if "exit_time" in trades.columns and "entry_time" in trades.columns:
            durations = (trades["exit_time"] - trades["entry_time"]) / 60.0  # Convert to minutes
            avg_duration = durations.mean()
        else:
            avg_duration = 0.0
        
        # Trades per hour
        trades_per_hour = (total_trades / duration_minutes) * 60 if duration_minutes > 0 else 0.0
        
        # Best/Worst trades
        best_trade = trades["pnl"].max()
        worst_trade = trades["pnl"].min()
        
        # Consecutive wins/losses
        consecutive_wins = PerformanceAnalyzer._max_consecutive(trades["pnl"] > 0)
        consecutive_losses = PerformanceAnalyzer._max_consecutive(trades["pnl"] <= 0)
        
        return PerformanceMetrics(
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            recovery_factor=recovery_factor,
            avg_trade_duration_minutes=avg_duration,
            trades_per_hour=trades_per_hour,
            best_trade=best_trade,
            worst_trade=worst_trade,
            consecutive_wins=consecutive_wins,
            consecutive_losses=consecutive_losses,
        )
    
    @staticmethod
    def _max_consecutive(series: pd.Series) -> int:
        """Calculate maximum consecutive True values."""
        max_count = 0
        current_count = 0
        
        for val in series:
            if val:
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        
        return max_count
    
    @staticmethod
    def print_performance_report(metrics: PerformanceMetrics, start_capital: float, end_capital: float) -> None:
        """Print a detailed performance report."""
        print("\n" + "=" * 70)
        print("📊 DETAILED PERFORMANCE REPORT")
        print("=" * 70)
        
        print(f"\n💰 P&L SUMMARY:")
        print(f"  Start Capital:     ${start_capital:,.2f}")
        print(f"  End Capital:       ${end_capital:,.2f}")
        print(f"  Total P&L:         ${metrics.total_pnl:,.2f} ({metrics.total_pnl_pct:+.2f}%)")
        print(f"  Best Trade:        ${metrics.best_trade:,.2f}")
        print(f"  Worst Trade:       ${metrics.worst_trade:,.2f}")
        
        print(f"\n📈 WIN/LOSS METRICS:")
        print(f"  Total Trades:      {metrics.total_trades}")
        print(f"  Winning Trades:    {metrics.winning_trades} ({metrics.win_rate:.1f}%)")
        print(f"  Losing Trades:     {metrics.losing_trades}")
        print(f"  Avg Win:           ${metrics.avg_win:,.2f}")
        print(f"  Avg Loss:          ${metrics.avg_loss:,.2f}")
        print(f"  Win/Loss Ratio:    {abs(metrics.avg_win/metrics.avg_loss):.2f}" if metrics.avg_loss != 0 else "  Win/Loss Ratio:    N/A")
        
        print(f"\n🎯 QUALITY METRICS:")
        print(f"  Profit Factor:     {metrics.profit_factor:.2f}", end="")
        if metrics.profit_factor > 2.0:
            print(" ✨ EXCELLENT")
        elif metrics.profit_factor > 1.5:
            print(" ✅ GOOD")
        elif metrics.profit_factor > 1.0:
            print(" ⚠️  ACCEPTABLE")
        else:
            print(" ❌ POOR")
        
        print(f"  Sharpe Ratio:      {metrics.sharpe_ratio:.2f}", end="")
        if metrics.sharpe_ratio > 2.0:
            print(" ✨ EXCELLENT")
        elif metrics.sharpe_ratio > 1.0:
            print(" ✅ GOOD")
        elif metrics.sharpe_ratio > 0.5:
            print(" ⚠️  ACCEPTABLE")
        else:
            print(" ❌ POOR")
        
        print(f"  Max Drawdown:      ${metrics.max_drawdown:,.2f} ({metrics.max_drawdown_pct:.2f}%)", end="")
        if metrics.max_drawdown_pct < 0.05:
            print(" ✅ LOW")
        elif metrics.max_drawdown_pct < 0.10:
            print(" ⚠️  MODERATE")
        else:
            print(" ❌ HIGH")
        
        print(f"  Recovery Factor:   {metrics.recovery_factor:.2f}", end="")
        if metrics.recovery_factor > 3.0:
            print(" ✨ EXCELLENT")
        elif metrics.recovery_factor > 2.0:
            print(" ✅ GOOD")
        else:
            print("")
        
        print(f"\n⏱️  TRADING ACTIVITY:")
        print(f"  Avg Trade Duration: {metrics.avg_trade_duration_minutes:.1f} minutes")
        print(f"  Trades per Hour:    {metrics.trades_per_hour:.2f}")
        print(f"  Max Consecutive Wins:   {metrics.consecutive_wins}")
        print(f"  Max Consecutive Losses: {metrics.consecutive_losses}")
        
        print("\n" + "=" * 70)
        
        # Weekly projection
        if metrics.total_pnl > 0 and metrics.trades_per_hour > 0:
            hourly_pnl = metrics.total_pnl * metrics.trades_per_hour
            weekly_projection = hourly_pnl * 24 * 7
            weekly_pct = (weekly_projection / start_capital) * 100 if start_capital > 0 else 0
            
            print(f"\n📅 PROJECTIONS (if performance continues):")
            print(f"  Weekly P&L:        ${weekly_projection:,.2f} ({weekly_pct:+.2f}%)")
            print(f"  Monthly P&L:       ${weekly_projection * 4.3:,.2f} ({weekly_pct * 4.3:+.2f}%)")
            print(f"  Yearly P&L:        ${weekly_projection * 52:,.2f} ({weekly_pct * 52:+.2f}%)")
            print("=" * 70)


__all__ = ["PerformanceMetrics", "PerformanceAnalyzer"]

