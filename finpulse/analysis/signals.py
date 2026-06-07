"""FinPulse Signal Generation Engine Module

Combines rule-based technical indicator votes (RSI, MACD, Bollinger Bands, EMA crossovers)
with Machine Learning predictions to produce a comprehensive buy/sell/hold SignalReport.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple
import numpy as np
import pandas as pd
import yfinance as yf

from finpulse.analysis.indicators import compute_all
from finpulse.analysis.ml_model import predict_signal
from finpulse.logger import get_logger

logger = get_logger("analysis.signals")


@dataclass
class SignalReport:
    """Consolidated report containing all signal details for a stock."""
    symbol: str
    signal: str                # "BUY" | "SELL" | "HOLD"
    confidence: float          # 0-100%
    rsi_value: float
    rsi_signal: str            # "BUY" | "SELL" | "NEUTRAL"
    macd_signal: str           # "BUY" | "SELL" | "NEUTRAL"
    bollinger_signal: str      # "BUY" | "SELL" | "NEUTRAL"
    ema_signal: str            # "BUY" | "SELL" | "NEUTRAL"
    ml_prediction: str         # "BUY" | "SELL" | "HOLD"
    ml_confidence: float       # 0-100%
    current_price: float
    support_level: float
    resistance_level: float
    timestamp: datetime


def _fetch_history(symbol: str) -> pd.DataFrame:
    """Synchronous yfinance history download runner."""
    ticker = yf.Ticker(symbol)
    # Fetch 1 year of data to calculate indicators (e.g. EMA 200 needs plenty of bars)
    return ticker.history(period="1y")


async def generate_signal(symbol: str) -> Optional[Tuple[SignalReport, pd.DataFrame]]:
    """Generate a combined technical & ML signal report for a given stock.

    Args:
        symbol: The ticker symbol (e.g., RELIANCE or RELIANCE.NS)

    Returns:
        Optional[Tuple[SignalReport, pd.DataFrame]]: The report and history, or None if failed.
    """
    ticker_symbol = symbol.upper().strip()
    if not ticker_symbol.endswith(".NS") and not ticker_symbol.endswith(".BO"):
        ticker_symbol += ".NS"
        
    logger.info(f"Generating signal report for {ticker_symbol}...")
    
    try:
        # Fetch data in threadpool to prevent blocking the event loop
        df = await asyncio.to_thread(_fetch_history, ticker_symbol)
        
        if len(df) < 50:
            logger.warning(f"Insufficient historical data for {ticker_symbol} (need >= 50, got {len(df)})")
            return None
            
        current_price = float(df["Close"].iloc[-1])
        last_idx = df.index[-1]
        
        # Calculate support & resistance (rolling 20-day min/max close)
        support_level = float(df["Close"].tail(20).min())
        resistance_level = float(df["Close"].tail(20).max())
        
        # Compute all indicators
        ti = compute_all(df)
        
        # 1. RSI Rule
        rsi = float(ti["rsi"].loc[last_idx])
        if rsi < 35:
            rsi_sig = "BUY"
        elif rsi > 65:
            rsi_sig = "SELL"
        else:
            rsi_sig = "NEUTRAL"
            
        # 2. MACD Rule
        macd_hist = ti["macd"]["histogram"]
        # Check current vs previous histogram sign to detect crossover
        if len(macd_hist) >= 2:
            curr_hist = float(macd_hist.iloc[-1])
            prev_hist = float(macd_hist.iloc[-2])
            if curr_hist > 0 and prev_hist <= 0:
                macd_sig = "BUY"  # Bullish crossover
            elif curr_hist < 0 and prev_hist >= 0:
                macd_sig = "SELL"  # Bearish crossover
            elif curr_hist > 0:
                macd_sig = "BUY"  # Upward momentum
            else:
                macd_sig = "SELL"
        else:
            macd_sig = "NEUTRAL"
            
        # 3. Bollinger Bands Rule
        bb_upper = float(ti["bollinger"]["upper"].loc[last_idx])
        bb_lower = float(ti["bollinger"]["lower"].loc[last_idx])
        bb_width = bb_upper - bb_lower
        
        if bb_width > 0:
            pct_b = (current_price - bb_lower) / bb_width
            if pct_b < 0.15:
                bb_sig = "BUY"  # Touch or close to lower band
            elif pct_b > 0.85:
                bb_sig = "SELL"  # Touch or close to upper band
            else:
                bb_sig = "NEUTRAL"
        else:
            bb_sig = "NEUTRAL"
            
        # 4. EMA Cross Rule
        emas = ti["ema"]
        ema9_val = float(emas[9].loc[last_idx])
        ema21_val = float(emas[21].loc[last_idx])
        
        if ema9_val > ema21_val:
            ema_sig = "BUY"  # Short-term bullish crossover
        elif ema9_val < ema21_val:
            ema_sig = "SELL"
        else:
            ema_sig = "NEUTRAL"
            
        # 5. ML Model Prediction
        ml_pred, ml_conf = predict_signal(df)
        
        # 6. Combined Signal Decision Logic (Weighted Vote)
        # Weights:
        # - RSI: 1.5
        # - MACD: 1.0
        # - Bollinger: 1.0
        # - EMA: 1.0
        # - ML: 2.0 (if ML model is available and has > 60% confidence)
        
        votes = {"BUY": 0.0, "SELL": 0.0, "NEUTRAL": 0.0}
        
        # Technical Indicator votes
        votes[rsi_sig] += 1.5
        votes[macd_sig] += 1.0
        votes[bb_sig] += 1.0
        votes[ema_sig] += 1.0
        
        # ML vote integration
        ml_weight = 2.0 if ml_conf >= 60.0 else 1.0
        if ml_pred in ["BUY", "SELL"]:
            votes[ml_pred] += ml_weight
        else:
            votes["NEUTRAL"] += ml_weight
            
        # Calculate final combined signal
        total_votes = sum(votes.values())
        buy_pct = (votes["BUY"] / total_votes) * 100
        sell_pct = (votes["SELL"] / total_votes) * 100
        
        if buy_pct >= 55.0:
            final_signal = "BUY"
            final_conf = buy_pct
        elif sell_pct >= 55.0:
            final_signal = "SELL"
            final_conf = sell_pct
        else:
            final_signal = "HOLD"
            final_conf = max(buy_pct, sell_pct, 100.0 - buy_pct - sell_pct)
            
        report = SignalReport(
            symbol=ticker_symbol.replace(".NS", ""),
            signal=final_signal,
            confidence=float(final_conf),
            rsi_value=rsi,
            rsi_signal=rsi_sig,
            macd_signal=macd_sig,
            bollinger_signal=bb_sig,
            ema_signal=ema_sig,
            ml_prediction=ml_pred,
            ml_confidence=ml_conf,
            current_price=current_price,
            support_level=support_level,
            resistance_level=resistance_level,
            timestamp=datetime.now(),
        )
        return report, df
        
    except Exception as e:
        logger.exception(f"Failed to generate signal for symbol {symbol}")
        return None
