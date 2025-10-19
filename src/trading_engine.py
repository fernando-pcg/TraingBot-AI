"""Trading engine managing the main trading loop."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Sequence

import pandas as pd

from config import Config
from data_sources import DataAggregator, SentimentAnalyzer
from src.binance_client import BinanceClientWrapper
from src.data_pipeline import DataPipeline
from src.multi_timeframe import MultiTimeframeAnalyzer
from src.risk_manager import RiskManager
from src.state_manager import PositionState, StateManager, TradeRecord
from src.strategy import Signal, Strategy
from src.mean_reversion_strategy import MeanReversionStrategy, MeanReversionSignal
from src.market_regime import MarketRegimeDetector, MarketRegime
from src.performance_metrics import PerformanceAnalyzer, PerformanceMetrics


@dataclass
class Position:
    """Active trading position."""

    symbol: str
    side: str  # "buy" para LONG, "sell" para SHORT
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_time: float
    peak_price: float = 0.0
    lowest_price: float = 0.0  # Para trailing stop en SHORT


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
        use_sentiment_analysis: bool = True,
        use_gpt: bool = False,
    ) -> None:
        self._config = config
        self._client = client
        self._strategy = strategy
        self._risk_manager = risk_manager
        self._state_manager = state_manager
        self._loggers = loggers
        self._data_pipeline = DataPipeline(client)
        self._mt_analyzer = MultiTimeframeAnalyzer(
            client,
            intervals=("5m", "15m", "1h"),
            candle_limit=200,
        )
        
        # Initialize sentiment analysis (uses free APIs)
        self._use_sentiment_analysis = use_sentiment_analysis
        self._sentiment_analyzer = None
        if use_sentiment_analysis:
            try:
                data_aggregator = DataAggregator(cache_db_path="data/cache.db")
                self._sentiment_analyzer = SentimentAnalyzer(
                    data_aggregator=data_aggregator,
                    use_gpt=use_gpt,
                )
                loggers["system"].info("Sentiment analysis enabled (GPT: %s)", use_gpt)
            except Exception as exc:
                loggers["system"].warning("Failed to initialize sentiment analyzer: %s", exc)
                self._sentiment_analyzer = None
        
        # Initialize mean reversion strategy for ranging markets
        self._mean_reversion_strategy = MeanReversionStrategy(
            support_threshold=0.02,  # 2% cerca del soporte
            resistance_threshold=0.02  # 2% cerca de resistencia
        )
        self._market_mode = "momentum"  # Default mode
        
        # Initialize market regime detector
        self._regime_detector = MarketRegimeDetector()
        
        # Performance tracking
        self._session_start_time = 0.0
        
        self._positions: Dict[str, Position] = {}
        self._capital = config.risk.initial_capital
        self._trades_today: list[TradeRecord] = []
        self._start_capital = config.risk.initial_capital
        
        # Initialize peak capital for drawdown tracking
        self._risk_manager.peak_capital = config.risk.initial_capital

    def run(self, symbol: str, duration_minutes: int = 10, interval_seconds: int = 60) -> None:
        """Run the trading bot for specified duration with advanced optimizations."""
        
        system_logger = self._loggers["system"]
        trades_logger = self._loggers["trades"]
        
        system_logger.info("Starting trading engine for %s (duration: %d min)", symbol, duration_minutes)
        
        # Track session start time
        self._session_start_time = time.time()
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        iteration = 0
        
        while time.time() < end_time:
            iteration += 1
            system_logger.info("=== Iteration %d ===", iteration)
            
            try:
                df = self._data_pipeline.get_recent_candles(symbol, interval="1m", limit=150)
                current_price = self._data_pipeline.get_current_price(symbol)
                timeframe_summaries = self._safe_fetch_timeframes(symbol)
                
                system_logger.info("Current price for %s: %.2f", symbol, current_price)
                
                # Update drawdown tracking
                self._risk_manager.update_drawdown(self._capital)
                
                # Check if trading is paused due to drawdown
                if self._risk_manager.trading_paused:
                    system_logger.warning(
                        "⚠️  TRADING PAUSED - Drawdown %.2f%% exceeds threshold (3%%)",
                        self._risk_manager.current_drawdown * 100
                    )
                    # Still check positions, but don't open new ones
                    self._check_open_positions(symbol, current_price)
                    time.sleep(interval_seconds)
                    continue
                
                self._check_open_positions(symbol, current_price)
                
                if not self._risk_manager.check_daily_limits(pd.DataFrame(self._trades_today), self._capital):
                    system_logger.warning("Daily loss limit reached, stopping trading")
                    break
                
                # Calculate indicators and patterns
                from src.indicators import calculate_indicators
                from src.patterns import analyze_patterns
                
                indicators = calculate_indicators(df)
                patterns = analyze_patterns(df)
                
                # ADVANCED: Detect market regime
                regime_analysis = self._regime_detector.detect_regime(df, indicators, timeframe_summaries)
                
                system_logger.info(
                    "📊 Market Regime: %s (%.0f%% confidence) | Volatility: %.1f%% | Recommendation: %s",
                    regime_analysis.regime.value.upper(),
                    regime_analysis.confidence * 100,
                    regime_analysis.volatility_level * 100,
                    regime_analysis.recommendation.upper()
                )
                
                # Skip trading if regime suggests avoiding
                if regime_analysis.recommendation == "avoid":
                    system_logger.warning("⚠️  Market too volatile or unclear - skipping this iteration")
                    time.sleep(interval_seconds)
                    continue
                
                # Select strategy based on regime recommendation
                technical_signal = None
                
                if regime_analysis.recommendation == "mean_reversion":
                    # Use mean reversion strategy
                    self._market_mode = "mean_reversion"
                    system_logger.info("🔄 Using MEAN REVERSION strategy")
                    
                    mr_signal = self._mean_reversion_strategy.evaluate(
                        symbol, current_price, indicators, patterns, timeframe_summaries
                    )
                    
                    if mr_signal:
                        technical_signal = Signal(
                            symbol=symbol,
                            action=mr_signal.action,
                            confidence=mr_signal.confidence,
                            reason=f"[MEAN REV] {mr_signal.reason}",
                        )
                        system_logger.info("Mean Reversion signal: %s (%.0f%%) - %s", 
                                         mr_signal.action.upper(), 
                                         mr_signal.confidence * 100,
                                         mr_signal.entry_zone)
                else:
                    # Use momentum strategy
                    self._market_mode = "momentum"
                    system_logger.info("📈 Using MOMENTUM strategy")
                    
                    technical_signal = self._strategy.generate_signal(
                        df,
                        symbol,
                        timeframe_summaries=timeframe_summaries,
                    )
                
                # Get market sentiment analysis
                sentiment_data = None
                if self._sentiment_analyzer:
                    try:
                        sentiment_data = self._sentiment_analyzer.analyze_market(symbol)
                        system_logger.info(
                            "Market sentiment: %s (confidence: %d%%, compiled score: %.2f)",
                            sentiment_data["final_recommendation"]["action"],
                            sentiment_data["final_recommendation"]["confidence"],
                            sentiment_data["compiled_data"].compiled_score,
                        )
                    except Exception as exc:
                        system_logger.warning("Sentiment analysis failed: %s", exc)
                
                # Combine technical and sentiment signals
                signal = self._combine_signals(technical_signal, sentiment_data, system_logger)
                
                # QUALITY FILTER: Only trade high-confidence signals
                MIN_CONFIDENCE = 0.45  # Configurable threshold
                if signal and signal.confidence < MIN_CONFIDENCE:
                    system_logger.info(
                        "❌ Signal rejected - confidence %.2f below threshold %.2f",
                        signal.confidence, MIN_CONFIDENCE
                    )
                    signal = None
                
                if signal:
                    system_logger.info(
                        "✅ High-quality signal: %s - %s (confidence: %.2f)", 
                        signal.action, signal.reason, signal.confidence
                    )
                    
                    # Execute signal with advanced position sizing
                    current_position = self._positions.get(symbol)
                    if signal.action.lower() == "buy":
                        if current_position is None:
                            self._execute_buy_signal(signal, current_price, indicators, trades_logger)
                        elif current_position.side == "sell":
                            self._close_position(symbol, current_price, "signal", trades_logger)
                    elif signal.action.lower() == "sell":
                        if current_position is None:
                            self._execute_sell_signal(signal, current_price, indicators, trades_logger)
                        elif current_position.side == "buy":
                            self._close_position(symbol, current_price, "signal", trades_logger)
                
            except Exception as exc:
                self._loggers["errors"].error("Error in trading loop: %s", exc, exc_info=True)
            
            if time.time() < end_time:
                time.sleep(interval_seconds)
        
        self._close_all_positions(trades_logger)
        self._generate_advanced_report(system_logger, duration_minutes)

    def _safe_fetch_timeframes(self, symbol: str) -> Sequence | None:
        try:
            summaries = self._mt_analyzer.fetch(symbol)
            if not summaries:
                self._loggers["system"].debug("No multi-timeframe data available for %s", symbol)
            return summaries
        except Exception as exc:
            self._loggers["errors"].warning("Failed to fetch multi-timeframe data: %s", exc)
            return None

    def _execute_buy_signal(self, signal: Signal, current_price: float, indicators, logger) -> None:
        """Execute a buy signal with advanced position sizing and adaptive stops."""
        
        exposure = sum(pos.entry_price * pos.quantity for pos in self._positions.values())
        
        if not self._risk_manager.should_open_position(exposure, self._capital):
            logger.info("Max exposure reached, skipping signal")
            return
        
        # Calculate performance metrics for dynamic position sizing
        if len(self._trades_today) >= 10:  # Need enough data for Kelly
            trades_df = pd.DataFrame(self._trades_today)
            wins = trades_df[trades_df["pnl"] > 0]
            losses = trades_df[trades_df["pnl"] <= 0]
            
            win_rate = len(wins) / len(trades_df) if len(trades_df) > 0 else 0.5
            avg_win = wins["pnl"].mean() if len(wins) > 0 else 10.0
            avg_loss = losses["pnl"].mean() if len(losses) > 0 else -5.0
            
            # Use dynamic position sizing (Kelly Criterion)
            position_size = self._risk_manager.calculate_dynamic_position_size(
                capital=self._capital,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                stop_loss_pct=self._config.strategy.stop_loss_pct,
                volatility=indicators.atr / current_price if indicators.atr else 0.02,
            )
            logger.info("📊 Using DYNAMIC position sizing (Kelly) - Win rate: %.1f%%", win_rate * 100)
        else:
            # Fallback to basic calculation initially
            position_size = self._risk_manager.calculate_position_size(
                self._capital,
                self._config.strategy.risk_percent,
                self._config.strategy.stop_loss_pct,
            )
            logger.info("Using BASIC position sizing (warming up)")
        
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
            # Use ADAPTIVE stops based on ATR and market mode
            if self._market_mode == "mean_reversion":
                stop_loss_pct = 0.006  # 0.6% for mean reversion
                take_profit_pct = 0.012  # 1.2%
                logger.info("Using MEAN REVERSION stops (tight)")
            else:
                # Adaptive stop loss based on ATR
                if indicators.atr:
                    stop_loss_price = self._risk_manager.calculate_adaptive_stop_loss(
                        current_price, indicators.atr, self._config.strategy.stop_loss_pct
                    )
                    stop_loss_pct = (current_price - stop_loss_price) / current_price
                    logger.info("Using ADAPTIVE stop loss (ATR-based): %.2f%%", stop_loss_pct * 100)
                else:
                    stop_loss_pct = self._config.strategy.stop_loss_pct
                
                take_profit_pct = self._config.risk.take_profit_pct
            
            stop_loss = current_price * (1 - stop_loss_pct)
            take_profit = current_price * (1 + take_profit_pct)
            
            position = Position(
                symbol=signal.symbol,
                side="buy",
                entry_price=current_price,
                quantity=actual_quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_time=time.time(),
                peak_price=current_price,
                lowest_price=0.0,
            )
            
            self._positions[signal.symbol] = position
            logger.info(
                "💰 %s LONG Position opened: %s | Entry: %.2f | SL: %.2f (%.2f%%) | TP: %.2f (%.2f%%)",
                self._market_mode.upper(),
                signal.symbol,
                current_price,
                stop_loss,
                stop_loss_pct * 100,
                take_profit,
                take_profit_pct * 100,
            )
    
    def _execute_sell_signal(self, signal: Signal, current_price: float, indicators, logger) -> None:
        """Execute a SELL signal to open SHORT position with advanced position sizing."""
        
        total_position_value = sum(
            pos.entry_price * pos.quantity for pos in self._positions.values()
        )
        exposure = total_position_value / max(self._capital, 1)
        
        if not self._risk_manager.should_open_position(exposure, self._capital):
            logger.info("Max exposure reached, skipping SHORT signal")
            return
        
        # Calculate performance metrics for dynamic position sizing
        if len(self._trades_today) >= 10:
            trades_df = pd.DataFrame(self._trades_today)
            wins = trades_df[trades_df["pnl"] > 0]
            losses = trades_df[trades_df["pnl"] <= 0]
            
            win_rate = len(wins) / len(trades_df) if len(trades_df) > 0 else 0.5
            avg_win = wins["pnl"].mean() if len(wins) > 0 else 10.0
            avg_loss = losses["pnl"].mean() if len(losses) > 0 else -5.0
            
            position_size = self._risk_manager.calculate_dynamic_position_size(
                capital=self._capital,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                stop_loss_pct=self._config.strategy.stop_loss_pct,
                volatility=indicators.atr / current_price if indicators.atr else 0.02,
            )
            logger.info("📊 Using DYNAMIC position sizing (Kelly) - Win rate: %.1f%%", win_rate * 100)
        else:
            position_size = self._risk_manager.calculate_position_size(
                self._capital,
                self._config.strategy.risk_percent,
                self._config.strategy.stop_loss_pct,
            )
            logger.info("Using BASIC position sizing (warming up)")
        
        quantity = position_size / current_price
        
        if self._config.dry_run:
            logger.info(
                "[DRY RUN] Would SELL %.6f %s at %.2f (position size: %.2f) - OPENING SHORT",
                quantity,
                signal.symbol,
                current_price,
                position_size,
            )
            order_filled = True
            actual_quantity = quantity
        else:
            try:
                order = self._client.place_market_order(signal.symbol, quantity, "sell")
                logger.info("SHORT SELL order executed: %s", order)
                order_filled = order.status == "FILLED"
                actual_quantity = order.executed_qty
            except Exception as exc:
                self._loggers["errors"].error("Failed to execute SHORT SELL: %s", exc)
                return
        
        if order_filled:
            # Use ADAPTIVE stops based on ATR and market mode
            if self._market_mode == "mean_reversion":
                stop_loss_pct = 0.006  # 0.6% for mean reversion
                take_profit_pct = 0.012  # 1.2%
                logger.info("Using MEAN REVERSION stops (tight)")
            else:
                # Adaptive stop loss based on ATR
                if indicators.atr:
                    stop_loss_price = self._risk_manager.calculate_adaptive_stop_loss(
                        current_price, indicators.atr, self._config.strategy.stop_loss_pct
                    )
                    stop_loss_pct = (stop_loss_price - current_price) / current_price  # Inverse for SHORT
                    logger.info("Using ADAPTIVE stop loss (ATR-based): %.2f%%", stop_loss_pct * 100)
                else:
                    stop_loss_pct = self._config.strategy.stop_loss_pct
                
                take_profit_pct = self._config.risk.take_profit_pct
            
            # Para SHORT: stop loss ARRIBA, take profit ABAJO
            stop_loss = current_price * (1 + stop_loss_pct)
            take_profit = current_price * (1 - take_profit_pct)
            
            position = Position(
                symbol=signal.symbol,
                side="sell",
                entry_price=current_price,
                quantity=actual_quantity,
                stop_loss=stop_loss,
                take_profit=take_profit,
                entry_time=time.time(),
                peak_price=0.0,
                lowest_price=current_price,
            )
            
            self._positions[signal.symbol] = position
            logger.info(
                "💰 %s SHORT Position opened: %s | Entry: %.2f | SL: %.2f (%.2f%%) | TP: %.2f (%.2f%%)",
                self._market_mode.upper(),
                signal.symbol,
                current_price,
                stop_loss,
                stop_loss_pct * 100,
                take_profit,
                take_profit_pct * 100,
            )

    def _check_open_positions(self, symbol: str, current_price: float) -> None:
        """Monitor open positions for stop-loss and take-profit."""
        
        if symbol not in self._positions:
            return
        
        position = self._positions[symbol]
        trades_logger = self._loggers["trades"]
        
        if position.side == "buy":  # LONG position
            # Actualizar peak price para trailing stop
            if current_price > position.peak_price:
                position.peak_price = current_price
                trailing_stop = self._risk_manager.trailing_stop(
                    current_price, position.peak_price, self._config.strategy.stop_loss_pct
                )
                if trailing_stop > position.stop_loss:
                    position.stop_loss = trailing_stop
                    trades_logger.info("Trailing stop updated for %s: %.2f", symbol, trailing_stop)
            
            # Check stop loss y take profit para LONG
            if current_price <= position.stop_loss:
                self._close_position(symbol, current_price, "stop_loss", trades_logger)
            elif current_price >= position.take_profit:
                self._close_position(symbol, current_price, "take_profit", trades_logger)
        
        elif position.side == "sell":  # SHORT position
            # Inicializar lowest_price si es la primera vez
            if position.lowest_price == 0.0:
                position.lowest_price = current_price
            
            # Actualizar lowest price para trailing stop en SHORT
            if current_price < position.lowest_price:
                position.lowest_price = current_price
                # Para SHORT, el trailing stop sube cuando el precio baja
                trailing_stop = position.entry_price - (position.entry_price - position.lowest_price) * (1 - self._config.strategy.stop_loss_pct)
                if trailing_stop < position.stop_loss:
                    position.stop_loss = trailing_stop
                    trades_logger.info("SHORT trailing stop updated for %s: %.2f", symbol, trailing_stop)
            
            # Check stop loss y take profit para SHORT (invertido)
            if current_price >= position.stop_loss:
                self._close_position(symbol, current_price, "stop_loss", trades_logger)
            elif current_price <= position.take_profit:
                self._close_position(symbol, current_price, "take_profit", trades_logger)

    def _close_position(self, symbol: str, exit_price: float, reason: str, logger) -> None:
        """Close an open position."""
        
        if symbol not in self._positions:
            return
        
        position = self._positions[symbol]
        
        if self._config.dry_run:
            logger.info(
                "[DRY RUN] Would %s %.6f %s at %.2f (reason: %s)",
                "SELL" if position.side == "buy" else "BUY",  # Operación inversa
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
        
        # Calcular PnL según el tipo de posición
        if position.side == "buy":  # LONG
            pnl = (exit_price - position.entry_price) * position.quantity
            pnl_pct = ((exit_price / position.entry_price) - 1) * 100
        else:  # SHORT
            pnl = (position.entry_price - exit_price) * position.quantity
            pnl_pct = ((position.entry_price / exit_price) - 1) * 100
        
        trade = TradeRecord(
            symbol=symbol,
            side=position.side,
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
            "Position closed: %s %s | Entry: %.2f | Exit: %.2f | PnL: %.2f (%.2f%%) | Reason: %s",
            position.side.upper(),
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

    def _generate_advanced_report(self, logger, duration_minutes: float) -> None:
        """Generate comprehensive performance report using PerformanceAnalyzer."""
        
        if not self._trades_today:
            logger.info("=" * 70)
            logger.info("No trades executed during this session")
            logger.info("=" * 70)
            return
        
        # Convert trades to DataFrame
        trades_df = pd.DataFrame([vars(t) for t in self._trades_today])
        
        # Calculate comprehensive metrics
        metrics = PerformanceAnalyzer.analyze_trades(
            trades=trades_df,
            start_capital=self._start_capital,
            duration_minutes=duration_minutes
        )
        
        # Print detailed performance report
        PerformanceAnalyzer.print_performance_report(
            metrics=metrics,
            start_capital=self._start_capital,
            end_capital=self._capital
        )
        
        # Add risk management status
        logger.info("\n⚠️  RISK MANAGEMENT STATUS:")
        logger.info(f"  Current Drawdown:  {self._risk_manager.current_drawdown * 100:.2f}%")
        logger.info(f"  Peak Capital:      ${self._risk_manager.peak_capital:,.2f}")
        logger.info(f"  Trading Paused:    {'YES ⚠️' if self._risk_manager.trading_paused else 'NO ✅'}")
        logger.info("=" * 70)
    
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

    def _combine_signals(
        self,
        technical_signal: Optional[Signal],
        sentiment_data: Optional[Dict],
        logger,
    ) -> Optional[Signal]:
        """Combine technical analysis signal with market sentiment.
        
        Parameters
        ----------
        technical_signal : Optional[Signal]
            Signal from technical analysis strategy
        sentiment_data : Optional[Dict]
            Market sentiment analysis data
        logger : Logger
            System logger
            
        Returns
        -------
        Optional[Signal] : Combined signal or None
        """
        # If no technical signal and no sentiment analysis, return None
        if not technical_signal and not sentiment_data:
            return None
        
        # If only technical signal available
        if not sentiment_data or not self._sentiment_analyzer:
            return technical_signal
        
        # If only sentiment available (no technical signal)
        if not technical_signal:
            sentiment_rec = sentiment_data["final_recommendation"]
            
            # Only act on high-confidence sentiment signals
            if sentiment_rec["confidence"] >= 70:
                action = sentiment_rec["action"].lower()
                if action in ["buy", "sell"]:
                    logger.info("Using sentiment-based signal (no technical signal)")
                    return Signal(
                        symbol=sentiment_data["symbol"],
                        action=action,
                        confidence=sentiment_rec["confidence"] / 100,
                        reason=f"Sentiment: {', '.join(sentiment_rec['reasoning'][:3])}",
                    )
            
            return None
        
        # Both signals available - combine them
        sentiment_rec = sentiment_data["final_recommendation"]
        technical_action = technical_signal.action.lower()
        sentiment_action = sentiment_rec["action"].lower()
        
        # Check for agreement
        if technical_action == sentiment_action:
            # Signals agree - boost confidence significativamente
            # Base: 70% técnica + 30% sentiment
            base_confidence = (technical_signal.confidence * 0.7) + (sentiment_rec["confidence"] / 100 * 0.3)
            
            # Boost por acuerdo: +20% si ambos están de acuerdo
            agreement_bonus = 1.2
            
            # Boost adicional por bajo riesgo
            if sentiment_rec["risk_level"] == "LOW":
                agreement_bonus *= 1.05
                logger.info("LOW risk + agreement - extra boost")
            
            combined_confidence = min(base_confidence * agreement_bonus, 0.98)
            
            combined_reason = f"{technical_signal.reason} | Sentiment: {sentiment_action} ({sentiment_rec['confidence']}%) - {sentiment_rec['risk_level']} risk | Score: {sentiment_data['compiled_data'].compiled_score:.2f}"
            
            logger.info(
                "Technical and sentiment AGREE - boosting confidence: %.2f -> %.2f (+%.0f%%)",
                base_confidence,
                combined_confidence,
                (agreement_bonus - 1) * 100
            )
            
            return Signal(
                symbol=technical_signal.symbol,
                action=technical_action,
                confidence=combined_confidence,
                reason=combined_reason,
            )
        
        # Signals disagree - SIEMPRE combinar, no ignorar sentiment
        logger.warning(
            "Signal conflict: Technical=%s (%.2f), Sentiment=%s (%d%%)",
            technical_action,
            technical_signal.confidence,
            sentiment_action,
            sentiment_rec["confidence"],
        )
        
        # NUEVO: Calcular factor de ajuste basado en sentiment
        sentiment_factor = sentiment_rec["confidence"] / 100.0
        
        # Si el sentiment muestra riesgo alto, penalizar más
        if sentiment_rec["risk_level"] == "HIGH":
            logger.info("HIGH risk detected - applying strong penalty")
            sentiment_factor *= 0.5  # Penalización del 50%
        elif sentiment_rec["risk_level"] == "MEDIUM":
            logger.info("MEDIUM risk detected - applying moderate penalty")
            sentiment_factor *= 0.75  # Penalización del 25%
        
        # Combinar señales: dar 70% peso a técnica, 30% a sentiment
        # Esto asegura que sentiment SIEMPRE influye, pero técnica domina
        combined_confidence = (technical_signal.confidence * 0.7) + (sentiment_factor * 0.3)
        
        logger.info(
            "Combined confidence: Tech %.2f (70%%) + Sentiment %.2f (30%%) = %.2f",
            technical_signal.confidence,
            sentiment_factor,
            combined_confidence
        )
        
        # Si el conflicto es muy fuerte y el riesgo es alto, cancelar
        if sentiment_rec["risk_level"] == "HIGH" and combined_confidence < 0.45:
            logger.info("Strong conflict with HIGH risk - canceling trade")
            return None
        
        # Si la confianza combinada es muy baja, cancelar
        if combined_confidence < 0.40:
            logger.info("Combined confidence too low (%.2f) - no trade", combined_confidence)
            return None
        
        # Usar la acción técnica pero con confianza ajustada por sentiment
        return Signal(
            symbol=technical_signal.symbol,
            action=technical_action,
            confidence=combined_confidence,
            reason=f"{technical_signal.reason} | Sentiment: {sentiment_action} ({sentiment_rec['confidence']}%) - {sentiment_rec['risk_level']} risk",
        )


__all__ = ["TradingEngine"]

