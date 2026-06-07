"""FinPulse Formatting Unit Tests

Tests Indian number formatting, percentage change formatting,
and morning briefing formatter using mock snapshots and articles.
"""

from datetime import datetime
import pytest

from finpulse.utils.formatting import format_indian_number, format_change, format_briefing
from finpulse.data.market import MarketSnapshot, IndexQuote, StockQuote, CommodityQuote
from finpulse.data.news import NewsArticle


def test_format_indian_number():
    assert format_indian_number(100.0) == "100.00"
    assert format_indian_number(1234.56) == "1,234.56"
    assert format_indian_number(123456.78) == "1,23,456.78"
    assert format_indian_number(10000000.0) == "1,00,00,000.00"
    assert format_indian_number(-123456.78) == "-1,23,456.78"
    assert format_indian_number(123456.78, decimals=0) == "1,23,457"  # Rounding check


def test_format_change():
    assert format_change(1.234) == "▲ +1.23%"
    assert format_change(-0.555) == "▼ -0.56%"
    assert format_change(0.0) == "  0.00%"


def test_format_briefing():
    # Setup mock market snapshot
    indices = {
        "Nifty 50": IndexQuote("^NSEI", 22000.5, 0.45),
        "Sensex": IndexQuote("^BSESN", 72000.0, -0.1),
    }
    gainers = [StockQuote("RELIANCE.NS", "Reliance", 2900.0, 1.2)]
    losers = [StockQuote("TCS.NS", "TCS", 3800.0, -1.5)]
    commodities = {
        "Gold": CommodityQuote("GC=F", 2300.5, 0.2),
        "USD/INR": CommodityQuote("USDINR=X", 83.5, 0.05),
    }
    
    snapshot = MarketSnapshot(
        indices=indices,
        gainers=gainers,
        losers=losers,
        commodities=commodities,
        timestamp=datetime(2026, 6, 6, 9, 25),
        is_market_closed=False,
    )
    
    news = [
        NewsArticle(
            title="Markets open positive",
            link="http://test.com",
            source="Moneycontrol",
            published_at=datetime.now(),
            sentiment_score=0.45,
            sentiment_label="🟢 Bullish",
        )
    ]
    
    report = format_briefing(snapshot, news)
    
    # Assert key texts are present
    assert "FinPulse Morning Briefing — 06 Jun 2026" in report
    assert "Nifty 50" in report
    assert "22,000.50" in report
    assert "▲ +0.45%" in report
    assert "Reliance" in report
    assert "TCS" in report
    assert "Gold" in report
    assert "Markets open positive" in report
    assert "🟢 Bullish" in report
