"""FinPulse Technical Indicators Unit Tests

Tests computation of RSI, MACD, Bollinger Bands, and EMAs using mock market data.
"""

import numpy as np
import pandas as pd
import pytest

from finpulse.analysis.indicators import compute_rsi, compute_macd, compute_bollinger, compute_ema, compute_all


@pytest.fixture
def mock_stock_data():
    """Generate 100 days of mock stock price data."""
    np.random.seed(42)
    dates = pd.date_range(start="2026-01-01", periods=100)
    
    # Generate a random walk for prices
    close = 100.0 + np.random.randn(100).cumsum()
    high = close + np.random.rand(100) * 2
    low = close - np.random.rand(100) * 2
    open_ = close + np.random.randn(100)
    volume = np.random.randint(1000, 50000, size=100)
    
    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=dates,
    )
    return df


def test_rsi_calculation(mock_stock_data):
    rsi = compute_rsi(mock_stock_data, period=14)
    assert isinstance(rsi, pd.Series)
    assert len(rsi) == len(mock_stock_data)
    # The first value should be NaN
    assert pd.isna(rsi.iloc[0])
    # The remaining should be valid RSI values (0-100)
    assert rsi.iloc[14:].notna().all()
    assert (rsi.dropna() >= 0).all() and (rsi.dropna() <= 100).all()


def test_macd_calculation(mock_stock_data):
    macd_data = compute_macd(mock_stock_data)
    assert "macd" in macd_data
    assert "signal" in macd_data
    assert "histogram" in macd_data
    
    assert len(macd_data["macd"]) == len(mock_stock_data)
    # The first few MACD values should be NaN (slow period = 26)
    assert macd_data["macd"].iloc[:25].isna().all()
    assert macd_data["macd"].iloc[33:].notna().all()


def test_bollinger_calculation(mock_stock_data):
    bb = compute_bollinger(mock_stock_data, period=20)
    assert "lower" in bb
    assert "middle" in bb
    assert "upper" in bb
    
    assert len(bb["lower"]) == len(mock_stock_data)
    # Check that upper >= middle >= lower
    valid_data = pd.DataFrame(bb).dropna()
    assert (valid_data["upper"] >= valid_data["middle"]).all()
    assert (valid_data["middle"] >= valid_data["lower"]).all()


def test_ema_calculation(mock_stock_data):
    emas = compute_ema(mock_stock_data, periods=[9, 21])
    assert 9 in emas
    assert 21 in emas
    assert isinstance(emas[9], pd.Series)
    assert isinstance(emas[21], pd.Series)
    assert len(emas[9]) == len(mock_stock_data)


def test_compute_all(mock_stock_data):
    res = compute_all(mock_stock_data)
    assert "rsi" in res
    assert "macd" in res
    assert "bollinger" in res
    assert "ema" in res
