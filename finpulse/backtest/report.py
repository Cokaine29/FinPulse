"""FinPulse Backtesting Report Generator Module

Generates text summaries and visual charts for completed backtests.
Visual charts include:
1. Price Chart with Buy (▲ green) and Sell (▼ red) trade markers.
2. Equity Growth Curve (portfolio value over time).
3. Drawdown Chart showing peak-to-trough declines.
"""

import io
from datetime import datetime
from typing import Dict, List, Optional
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from finpulse.backtest.engine import BacktestResult
from finpulse.utils.formatting import format_indian_number
from finpulse.logger import get_logger

logger = get_logger("backtest.report")


def format_backtest_report(result: BacktestResult) -> str:
    """Format the backtest performance metrics into a clean HTML message.

    Args:
        result: The completed BacktestResult object.

    Returns:
        str: Formatted HTML message.
    """
    initial_cap = format_indian_number(result.initial_capital, decimals=0)
    final_val = format_indian_number(result.final_value, decimals=0)
    
    # Calculate average trade metrics
    total_trades = len(result.trades)
    avg_pnl = sum([t["pnl"] for t in result.trades]) / total_trades if total_trades > 0 else 0.0
    avg_pnl_pct = sum([t["pnl_pct"] for t in result.trades]) / total_trades if total_trades > 0 else 0.0
    
    avg_pnl_fmt = format_indian_number(avg_pnl, decimals=2)
    
    # Find strategy duration in years
    days = (result.equity_curve.index[-1] - result.equity_curve.index[0]).days
    years = round(days / 365.25, 1)
    
    lines = [
        f"📊 <b>Backtest Report — {result.symbol}</b>",
        f"⚙️ <b>Strategy:</b> <code>{result.strategy_name}</code>",
        f"⏳ <b>Period:</b> {years} Years ({result.equity_curve.index[0].strftime('%b %Y')} - {result.equity_curve.index[-1].strftime('%b %Y')})",
        "",
        "💰 <b>FINANCIAL PERFORMANCE</b>",
        f"• Starting Capital: ₹{initial_cap}",
        f"• Ending Value: ₹{final_val}",
        f"• Total Return: <b>{result.total_return_pct:+.2f}%</b>",
        f"• CAGR: <b>{result.cagr:+.2f}%</b>",
        "",
        "🛡️ <b>RISK & VOLATILITY</b>",
        f"• Max Drawdown: <b>{result.max_drawdown_pct:.2f}%</b>",
        f"• Sharpe Ratio: <b>{result.sharpe_ratio:.2f}</b>",
        "",
        "📈 <b>TRADE STATISTICS</b>",
        f"• Total Trades: <b>{total_trades}</b>",
        f"• Win Rate: <b>{result.win_rate:.1f}%</b>",
        f"• Profit Factor: <b>{result.profit_factor:.2f}</b>",
        f"• Avg Trade P&L: ₹{avg_pnl_fmt}  ({avg_pnl_pct:+.2f}%)",
        "",
        "📝 <i>Use /backtest for simulating historical performance on NSE stocks.</i>",
    ]
    
    return "\n".join(lines)


def generate_backtest_chart(result: BacktestResult) -> Optional[bytes]:
    """Generate a 3-panel backtest analysis chart (Price + Trades, Equity Curve, Drawdown).

    Args:
        result: The completed BacktestResult object.

    Returns:
        Optional[bytes]: PNG image bytes, or None if failed.
    """
    try:
        df = result.df.copy()
        equity = result.equity_curve
        trades = result.trades
        
        # Calculate drawdown series
        peaks = equity.cummax()
        drawdown = (equity - peaks) / peaks * 100
        
        # Style
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        
        # Create 3-panel figure
        fig, (ax1, ax2, ax3) = plt.subplots(
            nrows=3,
            ncols=1,
            sharex=True,
            figsize=(10, 8),
            gridspec_kw={"height_ratios": [2.2, 1.8, 1.0]},
        )
        
        # --- Panel 1: Price and Trade Markers ---
        ax1.plot(df.index, df["Close"], color="#4A5568", label="Close Price", linewidth=1.5, alpha=0.8)
        
        # Plot trade markers
        buy_dates = [t["entry_date"] for t in trades]
        buy_prices = [t["entry_price"] for t in trades]
        sell_dates = [t["exit_date"] for t in trades]
        sell_prices = [t["exit_price"] for t in trades]
        
        ax1.scatter(buy_dates, buy_prices, color="#38A169", marker="^", s=80, label="Buy", zorder=5)
        ax1.scatter(sell_dates, sell_prices, color="#E53E3E", marker="v", s=80, label="Sell", zorder=5)
        
        ax1.set_title(f"Backtesting Analysis: {result.symbol} ({result.strategy_name})", fontsize=14, fontweight="bold", pad=10)
        ax1.set_ylabel("Stock Price (₹)", fontsize=11)
        ax1.legend(loc="upper left", frameon=True)
        ax1.grid(True, alpha=0.3)
        ax1.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ",")))
        
        # --- Panel 2: Equity Curve ---
        ax2.plot(equity.index, equity, color="#3182CE", label="Portfolio Value", linewidth=2.0)
        ax2.fill_between(equity.index, result.initial_capital, equity, where=(equity >= result.initial_capital), color="#3182CE", alpha=0.08)
        ax2.fill_between(equity.index, result.initial_capital, equity, where=(equity < result.initial_capital), color="#E53E3E", alpha=0.08)
        ax2.axhline(result.initial_capital, color="#718096", linestyle="--", linewidth=1.0, alpha=0.7)
        
        ax2.set_ylabel("Equity (₹)", fontsize=11)
        ax2.legend(loc="upper left", frameon=True)
        ax2.grid(True, alpha=0.3)
        ax2.get_yaxis().set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ",")))
        
        # --- Panel 3: Drawdown Chart ---
        ax3.plot(drawdown.index, drawdown, color="#E53E3E", label="Drawdown %", linewidth=1.2)
        ax3.fill_between(drawdown.index, 0, drawdown, color="#E53E3E", alpha=0.15)
        ax3.set_ylabel("Drawdown %", fontsize=11)
        ax3.set_ylim(min(drawdown.min() * 1.1, -5.0), 1.0)  # Always show down to at least -5%
        ax3.legend(loc="upper left", frameon=True)
        ax3.grid(True, alpha=0.3)
        
        # Format X-axis dates
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        fig.autofmt_xdate()
        
        plt.xlabel("Date", fontsize=11)
        plt.tight_layout()
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        
        plt.close(fig)
        return buf.getvalue()
        
    except Exception as e:
        logger.error(f"Failed to generate backtest report chart: {e}")
        try:
            plt.close()
        except Exception:
            pass
        return None
