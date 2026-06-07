"""FinPulse Backtesting Metrics Calculator Module

Calculates key performance metrics for trading strategy backtests:
- CAGR (Compound Annual Growth Rate)
- Annualized Sharpe Ratio (using 6% risk-free rate for Indian markets)
- Max Drawdown (percentage peak-to-trough drop)
- Win Rate (percentage of winning trades)
- Profit Factor (gross profits divided by gross losses)
- Calmar Ratio (CAGR divided by Max Drawdown)
"""

import math
from typing import Dict, List, Optional
import numpy as np
import pandas as pd


def calculate_metrics(
    equity_curve: pd.Series,
    trades: List[Dict],
    initial_capital: float,
    risk_free_annual: float = 0.06,
) -> Dict[str, float]:
    """Calculate comprehensive performance metrics from an equity curve and trades list.

    Args:
        equity_curve: Daily portfolio values.
        trades: List of round-trip trade dictionaries.
        initial_capital: Starting capital.
        risk_free_annual: Annual risk-free rate (default 6% for India).

    Returns:
        Dict[str, float]: Calculated metrics.
    """
    if equity_curve.empty:
        return {}
        
    final_value = float(equity_curve.iloc[-1])
    total_return_pct = ((final_value - initial_capital) / initial_capital) * 100
    
    # Calculate duration in years
    days = (equity_curve.index[-1] - equity_curve.index[0]).days
    years = max(days / 365.25, 0.001)
    
    # CAGR
    if final_value > 0 and initial_capital > 0:
        cagr = ((final_value / initial_capital) ** (1.0 / years) - 1.0) * 100
    else:
        cagr = -100.0
        
    # Daily returns for Sharpe Ratio
    daily_returns = equity_curve.pct_change().dropna()
    
    # Risk-free daily rate (equivalent of annual rate)
    daily_rf = (1.0 + risk_free_annual) ** (1.0 / 252.0) - 1.0
    
    if len(daily_returns) > 1:
        excess_returns = daily_returns - daily_rf
        mean_excess = excess_returns.mean()
        std_returns = daily_returns.std()
        
        if std_returns > 0:
            # Annualize daily Sharpe: (mean / std) * sqrt(252)
            sharpe_ratio = (mean_excess / std_returns) * math.sqrt(252.0)
        else:
            sharpe_ratio = 0.0
    else:
        sharpe_ratio = 0.0
        
    # Max Drawdown
    peaks = equity_curve.cummax()
    drawdowns = (equity_curve - peaks) / peaks
    max_dd_pct = abs(float(drawdowns.min())) * 100
    
    # Trade statistics
    total_trades = len(trades)
    winning_trades = len([t for t in trades if t["pnl"] > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    
    gross_profits = sum([t["pnl"] for t in trades if t["pnl"] > 0])
    gross_losses = abs(sum([t["pnl"] for t in trades if t["pnl"] < 0]))
    
    if gross_losses > 0:
        profit_factor = gross_profits / gross_losses
    else:
        profit_factor = 999.0 if gross_profits > 0 else 1.0
        
    # Calmar Ratio
    calmar_ratio = (cagr / max_dd_pct) if max_dd_pct > 0 else 999.0
    
    # Average trade return
    avg_pnl = sum([t["pnl"] for t in trades]) / total_trades if total_trades > 0 else 0.0
    avg_pnl_pct = sum([t["pnl_pct"] for t in trades]) / total_trades if total_trades > 0 else 0.0
    
    return {
        "final_value": final_value,
        "total_return_pct": total_return_pct,
        "cagr": cagr,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown_pct": max_dd_pct,
        "total_trades": float(total_trades),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "calmar_ratio": calmar_ratio,
        "avg_pnl": avg_pnl,
        "avg_pnl_pct": avg_pnl_pct,
    }
