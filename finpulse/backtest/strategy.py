"""FinPulse Backtesting Strategies Module

Defines the base Strategy class and built-in trading strategies:
1. RSI_MEAN_REVERSION: Buy RSI < 35, Sell RSI > 65
2. MACD_CROSSOVER: Buy on bullish crossover (histogram > 0), Sell on bearish crossover (histogram < 0)
3. BOLLINGER_BOUNCE: Buy price < lower band, Sell price > upper band
4. EMA_CROSSOVER: Buy golden cross (EMA9 > EMA21), Sell death cross (EMA9 < EMA21)
"""

from abc import ABC, abstractmethod
from typing import Dict, Type
import numpy as np
import pandas as pd

from finpulse.analysis.indicators import compute_rsi, compute_macd, compute_bollinger, compute_ema


class Strategy(ABC):
    """Abstract Base Class for all backtesting strategies."""

    @abstractmethod
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute technical indicators required for the strategy and append them to the DataFrame."""
        pass

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """Generate trading signals for each day.

        Returns:
            pd.Series: A Series of integers: +1 (BUY), -1 (SELL), 0 (HOLD/NO ACTION).
        """
        pass


class RSIMeanReversion(Strategy):
    """RSI Mean Reversion Strategy.

    Buy when RSI is oversold (< 35).
    Sell when RSI is overbought (> 65).
    """

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["RSI"] = compute_rsi(df, period=14)
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        if "RSI" not in df.columns:
            return signals
            
        rsi = df["RSI"]
        # Buy signal on oversold
        signals[rsi < 35] = 1
        # Sell signal on overbought
        signals[rsi > 65] = -1
        
        # Keep only the transition signals to avoid consecutive identical signals
        # (e.g. if RSI stays below 35 for 5 days, only trigger BUY on the first day)
        return signals


class MACDCrossover(Strategy):
    """MACD Crossover Strategy.

    Buy on bullish crossover (histogram turns positive).
    Sell on bearish crossover (histogram turns negative).
    """

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        macd_data = compute_macd(df)
        df["MACD_hist"] = macd_data["histogram"]
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        if "MACD_hist" not in df.columns:
            return signals
            
        hist = df["MACD_hist"]
        prev_hist = hist.shift(1)
        
        # Bullish cross: hist crosses above 0
        signals[(hist > 0) & (prev_hist <= 0)] = 1
        # Bearish cross: hist crosses below 0
        signals[(hist < 0) & (prev_hist >= 0)] = -1
        
        return signals


class BollingerBounce(Strategy):
    """Bollinger Bounce Strategy.

    Buy when close price touches/pierces the lower band.
    Sell when close price touches/pierces the upper band.
    """

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        bb = compute_bollinger(df, period=20, std=2.0)
        df["BB_lower"] = bb["lower"]
        df["BB_upper"] = bb["upper"]
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        if "BB_lower" not in df.columns or "BB_upper" not in df.columns:
            return signals
            
        # Buy if price falls below lower band
        signals[df["Close"] < df["BB_lower"]] = 1
        # Sell if price rises above upper band
        signals[df["Close"] > df["BB_upper"]] = -1
        
        return signals


class EMACrossover(Strategy):
    """EMA Crossover Strategy (Golden Cross / Death Cross).

    Buy when EMA9 crosses above EMA21.
    Sell when EMA9 crosses below EMA21.
    """

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        emas = compute_ema(df, [9, 21])
        df["EMA9"] = emas[9]
        df["EMA21"] = emas[21]
        return df

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=df.index)
        if "EMA9" not in df.columns or "EMA21" not in df.columns:
            return signals
            
        ema9 = df["EMA9"]
        ema21 = df["EMA21"]
        prev_ema9 = ema9.shift(1)
        prev_ema21 = ema21.shift(1)
        
        # Golden Cross
        signals[(ema9 > ema21) & (prev_ema9 <= prev_ema21)] = 1
        # Death Cross
        signals[(ema9 < ema21) & (prev_ema9 >= prev_ema21)] = -1
        
        return signals


# Registry mapping string names to strategy classes
STRATEGY_REGISTRY: Dict[str, Type[Strategy]] = {
    "RSI_MEAN_REVERSION": RSIMeanReversion,
    "MACD_CROSSOVER": MACDCrossover,
    "BOLLINGER_BOUNCE": BollingerBounce,
    "EMA_CROSSOVER": EMACrossover,
}
