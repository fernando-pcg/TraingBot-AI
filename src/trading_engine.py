"""Trading engine managing the main trading loop."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional

import pandas as pd

from config import Config
from src.binance_client import BinanceClientWrapper
from src.data_pipeline import DataPipeline
from src.risk_manager import RiskManager
from src.state_manager import PositionState, StateManager, TradeRecord
from src.strategy import Signal, Strategy


@dataclass
class Position:
    """Active trading position."""

    symbol: str
    side: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_time: float
    peak_price: float = 0.0


class TradingEngine:
    """Main trading engine orchestrating the bot."""

    def __init__(
        self,
        config: Config,
        client: BinanceClientWrapper,
        strategy: Strategy,
        risk_manager: RiskManager,
        state_manager: StateManager,
        loggers: Dict[str, any],
    ) -> None:
        self._config = config
        self._client = client
        self._strategy = strategy
        self._risk_manager = risk_manager
        self._state_manager = state_manager
        self._loggers = loggers
        self._data_pipeline = DataPipeline(client)
        
        self._positions: Dict[str, Position] = {}
        self._capital = config.risk.initial_capital
        self._trades_today: list[TradeRecord] = []
        self._start_capital = config.risk.initial_capital

    def run(self, symbol: str, duration_minutes: int = 10, interval_seconds: int = 60) -> None:
        """Run the trading bot for specified duration."""
        
        system_logger = self._loggers["system"]
        trades_logger = self._loggers["trades"]
        
        system_logger.info("Starting trading engine for %s (duration: %d min)", symbol, duration_minutes)
        
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        iteration = 0
        
        while time.time() < end_time:
            iteration += 1
            system_logger.info("=== Iteration %d ===", iteration)
            
            try:
                df = self._data_pipeline.get_recent_candles(symbol, interval="1m", limit=100)
                current_price = self._data_pipeline.get_current_price(symbol)
                
                system_logger.info("Current price for %s: %.2f", symbol, current_price)
                
                self._check_open_positions(symbol, current_price)
                
                if not self._risk_manager.check_daily_limits(pd.DataFrame(self._trades_today), self._capital):
                    system_logger.warning("Daily loss limit reached, stopping trading")
                    break
                
                signal = self._strategy.generate_signal(df, symbol)
                
                if signal:
                    system_logger.info("Signal detected: %s - %s (confidence: %.2f)", signal.action, signal.reason, signal.confidence)
                
                if signal and symbol not in self._positions:
                    if signal.action.lower() == "buy":
                        self._execute_buy_signal(signal, current_price, trades_logger)
                elif signal and symbol in self._positions:
                    if signal.action.lower() == "sell" and self._positions[symbol].side == "buy":
                        self._close_position(symbol, current_price, "signal", trades_logger)
                
            except Exception as exc:
                self._loggers["errors"].error("Error in trading loop: %s", exc, exc_info=True)
            
            if time.time() < end_time:
                time.sleep(interval_seconds)
        
        self._close_all_positions(trades_logger)
        self._generate_report(system_logger)

    def _execute_buy_signal(self, signal: Signal, current_price: float, logger) -> None:
        """Execute a buy signal."""
        
        exposure = sum(pos.entry_price * pos.quantity for pos in self._positions.values())
        
        if not self._risk_manager.should_open_position(exposure, self._capital):
            logger.info("Max exposure reached, skipping signal")
            return
        
        position_size = self._risk_manager.calculate_position_size(
            self._capital,
            self._config.strategy.risk_percent,
            self._config.strategy.stop_loss_pct,
        )
        
        quantity = position_size / current_price
        
        if self._config.dry_run:
            logger.info(
                "[DRY RUN] Would BUY %.6f %s at %.2f (position size: %.2f)",
                quantity,
                signal.symbol,
                current_price,
                position_size,
            )
            order_filled = True
            actual_quantity = quantity
        else:
            try:
                order = self._client.place_market_order(signal.symbol, quantity, "buy")
                logger.info("BUY order executed: %s", order)
                order_filled = order.status == "FILLED"
                actual_quantity = order.executed_qty
            except Exception as exc:
                self._loggers["errors"].error("Failed to execute BUY: %s", exc)
                return
        
        if order_filled:
            stop_loss = self._risk_manager.calculate_stop_loss(current_price, self._config.strategy.stop_loss_pct)
            take_profit = self._risk_manager.calculate_take_profit(
                current_price, self._config.strategy.name, signal.confidence
            )
            
            position = Position(
                symbol=signal.symbol,
                side="buy",
                entry_price=current_price,
                quantity=actual_quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_time=time.time(),
                peak_price=current_price,
            )
            
            self._positions[signal.symbol] = position
            logger.info(
                "Position opened: %s | Entry: %.2f | SL: %.2f | TP: %.2f",
                signal.symbol,
                current_price,
                stop_loss,
                take_profit,
            )

    def _check_open_positions(self, symbol: str, current_price: float) -> None:
        """Monitor open positions for stop-loss and take-profit."""
        
        if symbol not in self._positions:
            return
        
        position = self._positions[symbol]
        trades_logger = self._loggers["trades"]
        
        if current_price > position.peak_price:
            position.peak_price = current_price
            trailing_stop = self._risk_manager.trailing_stop(
                current_price, position.peak_price, self._config.strategy.stop_loss_pct
            )
            if trailing_stop > position.stop_loss:
                position.stop_loss = trailing_stop
                trades_logger.info("Trailing stop updated for %s: %.2f", symbol, trailing_stop)
        
        if current_price <= position.stop_loss:
            self._close_position(symbol, current_price, "stop_loss", trades_logger)
        elif current_price >= position.take_profit:
            self._close_position(symbol, current_price, "take_profit", trades_logger)

    def _close_position(self, symbol: str, exit_price: float, reason: str, logger) -> None:
        """Close an open position."""
        
        if symbol not in self._positions:
            return
        
        position = self._positions[symbol]
        
        if self._config.dry_run:
            logger.info(
                "[DRY RUN] Would SELL %.6f %s at %.2f (reason: %s)",
                position.quantity,
                symbol,
                exit_price,
                reason,
            )
        else:
            try:
                order = self._client.place_market_order(symbol, position.quantity, "sell")
                logger.info("SELL order executed: %s (reason: %s)", order, reason)
            except Exception as exc:
                self._loggers["errors"].error("Failed to execute SELL: %s", exc)
                return
        
        pnl = (exit_price - position.entry_price) * position.quantity
        pnl_pct = (exit_price / position.entry_price - 1) * 100
        
        trade = TradeRecord(
            symbol=symbol,
            side="sell",
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
            pnl=pnl,
            timestamp=time.time(),
        )
        
        self._trades_today.append(trade)
        self._state_manager.append_trade(trade)
        self._capital += pnl
        
        logger.info(
            "Position closed: %s | Entry: %.2f | Exit: %.2f | PnL: %.2f (%.2f%%) | Reason: %s",
            symbol,
            position.entry_price,
            exit_price,
            pnl,
            pnl_pct,
            reason,
        )
        
        del self._positions[symbol]

    def _close_all_positions(self, logger) -> None:
        """Close all remaining positions."""
        
        for symbol in list(self._positions.keys()):
            current_price = self._data_pipeline.get_current_price(symbol)
            self._close_position(symbol, current_price, "end_of_session", logger)

    def _generate_report(self, logger) -> None:
        """Generate performance report."""
        
        logger.info("=" * 60)
        logger.info("TRADING SESSION REPORT")
        logger.info("=" * 60)
        
        if not self._trades_today:
            logger.info("No trades executed during this session")
            return
        
        df = pd.DataFrame([vars(t) for t in self._trades_today])
        
        total_trades = len(df)
        winning_trades = len(df[df["pnl"] > 0])
        losing_trades = len(df[df["pnl"] < 0])
        
        total_pnl = df["pnl"].sum()
        total_pnl_pct = (self._capital / self._start_capital - 1) * 100
        
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        avg_win = df[df["pnl"] > 0]["pnl"].mean() if winning_trades > 0 else 0
        avg_loss = df[df["pnl"] < 0]["pnl"].mean() if losing_trades > 0 else 0
        
        logger.info("Total Trades: %d", total_trades)
        logger.info("Winning Trades: %d | Losing Trades: %d", winning_trades, losing_trades)
        logger.info("Win Rate: %.2f%%", win_rate)
        logger.info("Total P&L: %.2f USDT (%.2f%%)", total_pnl, total_pnl_pct)
        logger.info("Average Win: %.2f USDT | Average Loss: %.2f USDT", avg_win, avg_loss)
        logger.info("Start Capital: %.2f USDT", self._start_capital)
        logger.info("End Capital: %.2f USDT", self._capital)
        
        if total_trades > 0:
            avg_pnl_per_trade = total_pnl / total_trades
            trades_per_hour = total_trades / (10 / 60)
            
            hourly_projection = avg_pnl_per_trade * trades_per_hour
            daily_projection = hourly_projection * 24
            monthly_projection = daily_projection * 30
            
            logger.info("=" * 60)
            logger.info("PROJECTIONS (based on session performance)")
            logger.info("=" * 60)
            logger.info("Avg P&L per trade: %.2f USDT", avg_pnl_per_trade)
            logger.info("Projected hourly: %.2f USDT", hourly_projection)
            logger.info("Projected daily: %.2f USDT", daily_projection)
            logger.info("Projected monthly: %.2f USDT", monthly_projection)
        
        logger.info("=" * 60)


__all__ = ["TradingEngine"]

