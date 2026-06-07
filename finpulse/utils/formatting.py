"""FinPulse Formatting Utilities Module

Provides helper functions for formatting numbers (Indian numbering system),
percentage changes (with emojis), and the daily morning briefing message.
"""

import html
from datetime import datetime
from typing import List, Optional

from finpulse.data.market import MarketSnapshot
from finpulse.data.news import NewsArticle


def format_indian_number(n: float, decimals: int = 2) -> str:
    """Format a number according to the Indian numbering system.

    Example: 123456.78 -> 1,23,456.78
             10000000.5 -> 1,00,00,000.50
    """
    is_negative = n < 0
    abs_n = abs(n)
    
    # Format with requested decimals
    s = f"{abs_n:.{decimals}f}"
    parts = s.split(".")
    integer_part = parts[0]
    decimal_part = parts[1] if len(parts) > 1 else ""
    
    if len(integer_part) <= 3:
        res = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while remaining:
            if len(remaining) >= 2:
                groups.insert(0, remaining[-2:])
                remaining = remaining[:-2]
            else:
                groups.insert(0, remaining)
                remaining = ""
        res = ",".join(groups) + "," + last_three
        
    formatted = f"{res}.{decimal_part}" if decimal_part else res
    if is_negative:
        return f"-{formatted}"
    return formatted


def format_change(pct: float) -> str:
    """Format a percentage change with direction indicator and sign.

    Example: 1.25 -> ▲ +1.25%
             -0.85 -> ▼ -0.85%
             0.0 ->   0.00%
    """
    if pct > 0:
        return f"▲ +{pct:.2f}%"
    elif pct < 0:
        return f"▼ {pct:.2f}%"
    else:
        return f"  0.00%"


def format_briefing(snapshot: MarketSnapshot, news_articles: List[NewsArticle]) -> str:
    """Format the morning market digest into a clean, Telegram-friendly HTML/Markdown message."""
    # Use HTML formatting for Telegram since it is more reliable for nested styles and lists
    date_str = snapshot.timestamp.strftime("%d %b %Y")
    
    lines = []
    lines.append(f"🌅 <b>FinPulse Morning Briefing — {date_str}</b>")
    if snapshot.is_market_closed:
        lines.append("⚠️ <i>Note: Market is currently closed. Showing last available data.</i>")
    lines.append("")
    
    # 📊 Indices Section
    lines.append("📊 <b>MARKET INDICES</b>")
    for name, quote in snapshot.indices.items():
        price_fmt = format_indian_number(quote.price, decimals=2)
        change_fmt = format_change(quote.change_pct)
        lines.append(f"• <b>{name}</b>: {price_fmt}  ({change_fmt})")
    lines.append("")
    
    # 🏆 Top Gainers Section (Nifty 50)
    lines.append("🏆 <b>TOP GAINERS (Nifty 50)</b>")
    if snapshot.gainers:
        for i, quote in enumerate(snapshot.gainers):
            price_fmt = format_indian_number(quote.price, decimals=2)
            change_fmt = format_change(quote.change_pct)
            lines.append(f"{i+1}. <b>{quote.company_name}</b> (₹{price_fmt})  ({change_fmt})")
    else:
        lines.append("<i>No gainer data available</i>")
    lines.append("")
    
    # 📉 Top Losers Section (Nifty 50)
    lines.append("📉 <b>TOP LOSERS (Nifty 50)</b>")
    if snapshot.losers:
        for i, quote in enumerate(snapshot.losers):
            price_fmt = format_indian_number(quote.price, decimals=2)
            change_fmt = format_change(quote.change_pct)
            lines.append(f"{i+1}. <b>{quote.company_name}</b> (₹{price_fmt})  ({change_fmt})")
    else:
        lines.append("<i>No loser data available</i>")
    lines.append("")
    
    # 🌍 Commodities & Forex Section
    lines.append("🌍 <b>COMMODITIES & FOREX</b>")
    for name, quote in snapshot.commodities.items():
        # Add currency prefix dynamically
        if quote.symbol == "USDINR=X":
            price_fmt = f"₹{format_indian_number(quote.price, decimals=2)}"
        elif quote.symbol in ["GC=F", "CL=F"]:
            price_fmt = f"${format_indian_number(quote.price, decimals=2)}"
        else:
            price_fmt = format_indian_number(quote.price, decimals=2)
            
        change_fmt = format_change(quote.change_pct)
        lines.append(f"• <b>{name}</b>: {price_fmt}  ({change_fmt})")
    lines.append("")
    
    # 📰 Top News Section
    lines.append("📰 <b>TOP NEWS & SENTIMENT</b>")
    if news_articles:
        for i, art in enumerate(news_articles):
            # Clean and escape any HTML in news title to prevent Telegram formatting crash
            escaped_title = html.escape(art.title)
            # Truncate title if it's too long
            if len(escaped_title) > 90:
                escaped_title = escaped_title[:87] + "..."
            
            lines.append(
                f"{i+1}. <a href='{art.link}'>{escaped_title}</a> "
                f"[{art.source}] — <b>{art.sentiment_label}</b>"
            )
    else:
        lines.append("<i>No recent news articles available</i>")
        
    return "\n".join(lines)
