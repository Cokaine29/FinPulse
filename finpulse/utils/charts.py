"""FinPulse Stock Chart Generation Utility Module

Generates technical analysis charts (Price + EMAs, RSI subplot) using matplotlib.
Returns the chart as in-memory PNG bytes suitable for sending via Telegram bot.
Uses the headless 'Agg' backend to avoid GUI window popups.
"""

import io
import matplotlib
# Use non-interactive backend
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from typing import Optional

from finpulse.analysis.indicators import compute_rsi, compute_ema
from finpulse.logger import get_logger

logger = get_logger("utils.charts")


def generate_stock_chart(symbol: str, df: pd.DataFrame) -> Optional[bytes]:
    """Generate a technical analysis chart (90-day price + EMA, RSI subplot) for a stock.

    Args:
        symbol: Stock symbol (e.g., RELIANCE)
        df: Historical price DataFrame (minimum 90 rows recommended)

    Returns:
        Optional[bytes]: PNG image bytes, or None if generation failed.
    """
    try:
        # Use last 90 trading days for the chart
        chart_df = df.tail(90).copy()
        
        # Calculate technical indicators
        rsi = compute_rsi(chart_df)
        emas = compute_ema(chart_df, [9, 21])
        
        # Enable grid style
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
        
        # Create figure with 2 subplots (top: price + EMAs, bottom: RSI)
        fig, (ax1, ax2) = plt.subplots(
            nrows=2,
            ncols=1,
            sharex=True,
            figsize=(10, 6.5),
            gridspec_kw={"height_ratios": [3, 1]},
        )
        
        # 1. Price Plot (Top Subplot)
        ax1.plot(chart_df.index, chart_df["Close"], label="Close Price", color="#1f77b4", linewidth=2.0)
        ax1.plot(chart_df.index, emas[9], label="9 EMA", color="#ff7f0e", linestyle="--", linewidth=1.2)
        ax1.plot(chart_df.index, emas[21], label="21 EMA", color="#2ca02c", linestyle="--", linewidth=1.2)
        
        ax1.set_title(f"Technical Analysis Chart — {symbol.upper()}", fontsize=14, fontweight="bold", pad=10)
        ax1.set_ylabel("Price (₹)", fontsize=11)
        ax1.legend(loc="upper left", frameon=True)
        ax1.grid(True, alpha=0.3)
        
        # Format price y-axis labels
        ax1.get_yaxis().set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ","))
        )
        
        # 2. RSI Plot (Bottom Subplot)
        ax2.plot(chart_df.index, rsi, label="RSI (14)", color="#9467bd", linewidth=1.5)
        
        # RSI thresholds
        ax2.axhline(70, color="#d62728", linestyle=":", alpha=0.7)  # Overbought line
        ax2.axhline(30, color="#2ca02c", linestyle=":", alpha=0.7)  # Oversold line
        
        # Fill between 30 and 70 area
        ax2.fill_between(chart_df.index, 30, 70, color="#9467bd", alpha=0.05)
        
        ax2.set_ylabel("RSI", fontsize=11)
        ax2.set_ylim(10, 90)
        ax2.grid(True, alpha=0.3)
        
        # Format x-axis dates
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
        fig.autofmt_xdate()
        
        plt.xlabel("Date", fontsize=11)
        plt.tight_layout()
        
        # Save figure to in-memory bytes
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        buf.seek(0)
        
        # Close plot to release memory
        plt.close(fig)
        
        return buf.getvalue()
        
    except Exception as e:
        logger.error(f"Failed to generate stock chart for {symbol}: {e}")
        # Always close figures on exception to avoid memory leak
        try:
            plt.close()
        except Exception:
            pass
        return None
