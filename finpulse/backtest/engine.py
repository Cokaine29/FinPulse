"""FinPulse Backtesting Simulation Engine Module

Simulates historical trading of a given Strategy on a stock symbol.
Manages cash, positions, transaction commissions, and trade logs.
Calculates daily equity values and returns a comprehensive BacktestResult.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd
import yfinance as yf

from finpulse.backtest.metrics import calculate_metrics
from finpulse.backtest.strategy import Strategy
from finpulse.logger import get_logger

logger = get_logger("backtest.engine")


@dataclass
class BacktestResult:
    """Contains all results and metrics from a completed backtest."""
    symbol: str
    strategy_name: str
    initial_capital: float
    final_value: float
    total_return_pct: float
    cagr: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float
    total_trades: int
    trades: List[Dict]
    equity_curve: pd.Series
    df: pd.DataFrame  # Price history with indicator columns and signal markers


class BacktestEngine:
    """Simulates trading of a strategy on historical stock prices."""

    def __init__(self, strategy: Strategy, initial_capital: float = 100000.0, brokerage_pct: float = 0.001) -> None:
        """Initialize the Backtest Engine.

        Args:
            strategy: The Strategy object to run.
            initial_capital: Starting cash (default: ₹1,00,000).
            brokerage_pct: Transaction charge (default: 0.1% per trade).
        """
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.brokerage_pct = brokerage_pct

    def _fetch_data(self, symbol: str, years: int) -> pd.DataFrame:
        """Synchronous history downloader."""
        ticker = yf.Ticker(symbol)
        return ticker.history(period=f"{years}y")

    async def run(self, symbol: str, years: int = 3) -> Optional[BacktestResult]:
        """Run the backtest simulation for a given stock symbol and number of years.

        Args:
            symbol: Ticker symbol (e.g. RELIANCE or RELIANCE.NS)
            years: Duration of backtest in years (default: 3)

        Returns:
            Optional[BacktestResult]: Completed backtest results, or None if failed.
        """
        ticker_symbol = symbol.upper().strip()
        if not ticker_symbol.endswith(".NS") and not ticker_symbol.endswith(".BO"):
            ticker_symbol += ".NS"
            
        logger.info(f"Running backtest for {ticker_symbol} using {self.strategy.__class__.__name__} over {years} years...")
        
        try:
            # Download data
            df = await asyncio.to_thread(self._fetch_data, ticker_symbol, years)
            if len(df) < 50:
                logger.warning(f"Insufficient historical data for backtesting {ticker_symbol}")
                return None
                
            # Compute technical indicators and signals
            df_with_inds = self.strategy.compute_indicators(df)
            signals = self.strategy.generate_signals(df_with_inds)
            
            # Add signals to dataframe for reporting
            df_with_inds["Signal"] = signals
            
            # Portfolio simulation variables
            cash = self.initial_capital
            position = 0.0  # Quantity of shares held
            trades = []
            open_trade = None
            portfolio_values = []
            
            for idx, row in df_with_inds.iterrows():
                price = float(row["Close"])
                signal = int(signals.loc[idx])
                
                # Check for sell trigger
                if position > 0 and signal == -1:
                    revenue = position * price
                    exit_comm = revenue * self.brokerage_pct
                    cash = cash + revenue - exit_comm
                    
                    entry_price = open_trade["entry_price"]
                    entry_comm = open_trade["commission"]
                    
                    # Net Profit/Loss (revenue - cost - entry/exit fees)
                    pnl = revenue - (position * entry_price) - entry_comm - exit_comm
                    pnl_pct = (pnl / (entry_price * position)) * 100
                    
                    trades.append({
                        "entry_date": open_trade["entry_date"],
                        "exit_date": idx,
                        "entry_price": entry_price,
                        "exit_price": price,
                        "qty": position,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "duration_days": (idx - open_trade["entry_date"]).days,
                    })
                    
                    position = 0.0
                    open_trade = None
                    
                # Check for buy trigger
                elif position == 0 and signal == 1:
                    # Allocate all available cash, accounting for brokerage fee
                    qty = int(cash / (price * (1.0 + self.brokerage_pct)))
                    if qty > 0:
                        cost = qty * price
                        entry_comm = cost * self.brokerage_pct
                        cash = cash - cost - entry_comm
                        position = qty
                        
                        open_trade = {
                            "entry_date": idx,
                            "entry_price": price,
                            "qty": qty,
                            "commission": entry_comm,
                        }
                        
                # Record daily equity value (cash + live value of stock holdings)
                portfolio_values.append(cash + (position * price))
                
            # Force close open positions on the final day to complete the backtest
            if position > 0:
                last_idx = df_with_inds.index[-1]
                price = float(df_with_inds["Close"].iloc[-1])
                revenue = position * price
                exit_comm = revenue * self.brokerage_pct
                cash = cash + revenue - exit_comm
                
                entry_price = open_trade["entry_price"]
                entry_comm = open_trade["commission"]
                pnl = revenue - (position * entry_price) - entry_comm - exit_comm
                pnl_pct = (pnl / (entry_price * position)) * 100
                
                trades.append({
                    "entry_date": open_trade["entry_date"],
                    "exit_date": last_idx,
                    "entry_price": entry_price,
                    "exit_price": price,
                    "qty": position,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "duration_days": (last_idx - open_trade["entry_date"]).days,
                })
                portfolio_values[-1] = cash  # Update final day's portfolio value after close
                position = 0.0
                open_trade = None
                
            equity_curve = pd.Series(portfolio_values, index=df_with_inds.index)
            
            # Calculate performance metrics
            metrics = calculate_metrics(equity_curve, trades, self.initial_capital, risk_free_annual=0.06)
            
            return BacktestResult(
                symbol=ticker_symbol.replace(".NS", ""),
                strategy_name=self.strategy.__class__.__name__,
                initial_capital=self.initial_capital,
                final_value=metrics["final_value"],
                total_return_pct=metrics["total_return_pct"],
                cagr=metrics["cagr"],
                sharpe_ratio=metrics["sharpe_ratio"],
                max_drawdown_pct=metrics["max_drawdown_pct"],
                win_rate=metrics["win_rate"],
                profit_factor=metrics["profit_factor"],
                total_trades=int(metrics["total_trades"]),
                trades=trades,
                equity_curve=equity_curve,
                df=df_with_inds,
            )
            
        except Exception as e:
            logger.exception(f"Backtest failed for {symbol}")
            return None
