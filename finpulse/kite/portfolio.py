"""FinPulse Zerodha Portfolio Module

Fetches stock holdings and futures/options/intraday positions from Zerodha Kite.
Calculates overall portfolio statistics, daily M2M P&L, and gainer/loser rankings.
"""

import asyncio
from dataclasses import dataclass
from typing import List, Optional, Tuple
from kiteconnect import KiteConnect

from finpulse.logger import get_logger

logger = get_logger("kite.portfolio")


@dataclass
class Holding:
    """Represents a long-term equity holding in the portfolio."""
    symbol: str
    qty: int
    avg_price: float
    last_price: float
    pnl: float
    pnl_pct: float


@dataclass
class Position:
    """Represents a derivative or intraday position in the portfolio."""
    symbol: str
    qty: int
    avg_price: float
    last_price: float
    pnl: float
    product: str  # e.g., "MIS", "NRML", "CNC"


@dataclass
class PortfolioSummary:
    """Consolidated summary of the user's trading portfolio."""
    holdings: List[Holding]
    positions: List[Position]
    total_invested: float
    current_value: float
    total_pnl: float
    total_pnl_pct: float
    day_pnl: float
    top_gainer: Optional[Holding]
    top_loser: Optional[Holding]


def _fetch_holdings_sync(kite: KiteConnect) -> List[Holding]:
    """Fetch holdings synchronously from Kite."""
    raw_holdings = kite.holdings()
    holdings = []
    
    for h in raw_holdings:
        symbol = h.get("tradingsymbol", "")
        qty = int(h.get("quantity", 0) + h.get("t1_quantity", 0))  # Include T1 holdings
        if qty <= 0:
            continue
            
        avg_price = float(h.get("average_price", 0.0))
        last_price = float(h.get("last_price", 0.0))
        pnl = float(h.get("pnl", 0.0))
        
        # Calculate P&L %
        invested = qty * avg_price
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
        
        holdings.append(
            Holding(
                symbol=symbol,
                qty=qty,
                avg_price=avg_price,
                last_price=last_price,
                pnl=pnl,
                pnl_pct=pnl_pct,
            )
        )
    return holdings


def _fetch_positions_sync(kite: KiteConnect) -> List[Position]:
    """Fetch active positions synchronously from Kite."""
    raw_positions = kite.positions()
    positions = []
    
    # Zerodha returns a dict with 'net' and 'day' lists
    for p in raw_positions.get("net", []):
        qty = int(p.get("quantity", 0))
        # Keep open positions or closed intraday positions
        symbol = p.get("tradingsymbol", "")
        avg_price = float(p.get("average_price", 0.0))
        last_price = float(p.get("last_price", 0.0))
        pnl = float(p.get("pnl", 0.0))
        product = p.get("product", "")
        
        positions.append(
            Position(
                symbol=symbol,
                qty=qty,
                avg_price=avg_price,
                last_price=last_price,
                pnl=pnl,
                product=product,
            )
        )
    return positions


async def get_portfolio_summary(kite: KiteConnect) -> Optional[PortfolioSummary]:
    """Retrieve full holdings, positions, and compute summary metrics concurrently.

    Args:
        kite: Authenticated KiteConnect client instance.

    Returns:
        Optional[PortfolioSummary]: Summary details, or None if failed.
    """
    logger.info("Fetching portfolio data from Zerodha...")
    
    try:
        # Run Kite API requests concurrently in threadpools
        holdings_task = asyncio.to_thread(_fetch_holdings_sync, kite)
        positions_task = asyncio.to_thread(_fetch_positions_sync, kite)
        
        holdings, positions = await asyncio.gather(holdings_task, positions_task)
        
        # Portfolio math
        total_invested = 0.0
        current_value = 0.0
        day_pnl = 0.0
        
        # We need to query raw holdings to calculate day_pnl accurately because
        # day_pnl depends on the previous day close price, which is not in our parsed Holding dataclass.
        raw_holdings = await asyncio.to_thread(kite.holdings)
        for h in raw_holdings:
            qty = int(h.get("quantity", 0) + h.get("t1_quantity", 0))
            if qty > 0:
                last_price = float(h.get("last_price", 0.0))
                close_price = float(h.get("close_price", 0.0))
                # If close_price is 0 (first day/new listing/error), fallback to average cost
                if close_price <= 0:
                    close_price = float(h.get("average_price", 0.0))
                day_pnl += (last_price - close_price) * qty
                
        # Also include day P&L from positions (which is m2m)
        raw_positions = await asyncio.to_thread(kite.positions)
        for p in raw_positions.get("net", []):
            day_pnl += float(p.get("m2m", 0.0))
            
        for h in holdings:
            total_invested += h.qty * h.avg_price
            current_value += h.qty * h.last_price
            
        total_pnl = current_value - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
        
        # Top Gainer & Loser
        top_gainer = None
        top_loser = None
        if holdings:
            sorted_by_pnl = sorted(holdings, key=lambda x: x.pnl_pct, reverse=True)
            top_gainer = sorted_by_pnl[0]
            top_loser = sorted_by_pnl[-1]
            
        return PortfolioSummary(
            holdings=holdings,
            positions=positions,
            total_invested=total_invested,
            current_value=current_value,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
            day_pnl=day_pnl,
            top_gainer=top_gainer,
            top_loser=top_loser,
        )
        
    except Exception as e:
        logger.exception("Failed to retrieve or process Zerodha portfolio summary")
        return None
