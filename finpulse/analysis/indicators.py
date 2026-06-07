"""FinPulse Technical Indicators Module

Provides helper functions for computing technical indicators (RSI, MACD, Bollinger Bands, EMA)
using pandas-ta. Designed to be robust against pandas-ta version column naming changes.
"""

import pandas as pd
import pandas_ta as ta
from typing import Dict, List, Optional, Union

from finpulse.logger import get_logger

logger = get_logger("analysis.indicators")


def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute Relative Strength Index (RSI)."""
    try:
        rsi = df.ta.rsi(length=period)
        if rsi is None or rsi.empty:
            # Fallback if pandas-ta fails
            return pd.Series(index=df.index, dtype=float)
        return rsi
    except Exception as e:
        logger.error(f"Error computing RSI: {e}")
        return pd.Series(index=df.index, dtype=float)


def compute_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
    """Compute MACD, Signal line, and Histogram."""
    empty_series = pd.Series(index=df.index, dtype=float)
    default_result = {"macd": empty_series, "signal": empty_series, "histogram": empty_series}
    
    try:
        macd_df = df.ta.macd(fast=fast, slow=slow, signal=signal)
        if macd_df is None or macd_df.empty:
            return default_result
            
        # Find columns dynamically by prefix to avoid version mismatch errors
        macd_col = [c for c in macd_df.columns if c.startswith("MACD_")]
        signal_col = [c for c in macd_df.columns if c.startswith("MACDs_")]
        hist_col = [c for c in macd_df.columns if c.startswith("MACDh_")]
        
        return {
            "macd": macd_df[macd_col[0]] if macd_col else empty_series,
            "signal": macd_df[signal_col[0]] if signal_col else empty_series,
            "histogram": macd_df[hist_col[0]] if hist_col else empty_series,
        }
    except Exception as e:
        logger.error(f"Error computing MACD: {e}")
        return default_result


def compute_bollinger(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> Dict[str, pd.Series]:
    """Compute Bollinger Bands (Upper, Middle, Lower)."""
    empty_series = pd.Series(index=df.index, dtype=float)
    default_result = {"upper": empty_series, "middle": empty_series, "lower": empty_series}
    
    try:
        bb_df = df.ta.bbands(length=period, std=std)
        if bb_df is None or bb_df.empty:
            return default_result
            
        # Find columns dynamically by prefix
        lower_col = [c for c in bb_df.columns if c.startswith("BBL_")]
        middle_col = [c for c in bb_df.columns if c.startswith("BBM_")]
        upper_col = [c for c in bb_df.columns if c.startswith("BBU_")]
        
        return {
            "lower": bb_df[lower_col[0]] if lower_col else empty_series,
            "middle": bb_df[middle_col[0]] if middle_col else empty_series,
            "upper": bb_df[upper_col[0]] if upper_col else empty_series,
        }
    except Exception as e:
        logger.error(f"Error computing Bollinger Bands: {e}")
        return default_result


def compute_ema(df: pd.DataFrame, periods: List[int] = [9, 21, 50, 200]) -> Dict[int, pd.Series]:
    """Compute Exponential Moving Averages (EMA) for specified periods."""
    results = {}
    for p in periods:
        empty_series = pd.Series(index=df.index, dtype=float)
        try:
            ema = df.ta.ema(length=p)
            results[p] = ema if ema is not None and not ema.empty else empty_series
        except Exception as e:
            logger.error(f"Error computing EMA {p}: {e}")
            results[p] = empty_series
    return results


def compute_all(df: pd.DataFrame) -> Dict[str, Union[pd.Series, Dict]]:
    """Compute all technical indicators on the given DataFrame."""
    # Ensure columns exist and clean up df
    clean_df = df.copy()
    
    rsi = compute_rsi(clean_df)
    macd = compute_macd(clean_df)
    bb = compute_bollinger(clean_df)
    emas = compute_ema(clean_df)
    
    return {
        "rsi": rsi,
        "macd": macd,
        "bollinger": bb,
        "ema": emas,
    }
