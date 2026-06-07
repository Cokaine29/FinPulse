"""FinPulse Backtest Unit Tests

Tests strategy signal generation and simulation logic of the BacktestEngine.
"""

import numpy as np
import pandas as pd
import pytest

from finpulse.backtest.strategy import RSIMeanReversion, EMACrossover
from finpulse.backtest.engine import BacktestEngine


@pytest.fixture
def mock_trending_data():
    """Generate mock price data with explicit buy/sell setups."""
    dates = pd.date_range(start="2026-01-01", periods=100)
    
    # Simple sine wave trend to simulate price oscillation
    x = np.linspace(0, 10, 100)
    close = 100.0 + np.sin(x) * 10
    high = close + 1.0
    low = close - 1.0
    open_ = close - 0.5
    volume = np.ones(100) * 10000
    
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


def test_rsi_strategy_signals(mock_trending_data):
    strat = RSIMeanReversion()
    df_with_indicators = strat.compute_indicators(mock_trending_data)
    signals = strat.generate_signals(df_with_indicators)
    
    assert isinstance(signals, pd.Series)
    assert len(signals) == len(mock_trending_data)
    
    # Check that signals contain values in [-1, 0, 1]
    assert set(signals.unique()).issubset({-1, 0, 1})


@pytest.mark.asyncio
async def test_backtest_engine_run(mock_trending_data):
    strat = RSIMeanReversion()
    # Mock download function to return our fixture data instead of yfinance download
    engine = BacktestEngine(strat, initial_capital=100000.0, brokerage_pct=0.0)
    
    # We override the private downloader of the engine instance to return our mock fixture
    engine._fetch_data = lambda symbol, years: mock_trending_data
    
    result = await engine.run("MOCK_SYMBOL", years=1)
    
    assert result is not None
    assert result.symbol == "MOCK_SYMBOL"
    assert result.initial_capital == 100000.0
    assert result.final_value > 0
    assert isinstance(result.equity_curve, pd.Series)
    
    # Trade accounting validation
    if len(result.trades) > 0:
        for t in result.trades:
            assert "pnl" in t
            assert "pnl_pct" in t
            assert t["qty"] > 0
            assert t["entry_price"] > 0
            assert t["exit_price"] > 0
