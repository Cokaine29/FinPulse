"""FinPulse Configuration Module

Loads settings from .env file and provides typed Config dataclass.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv


# Index symbols for yfinance
INDEX_SYMBOLS = {
    "Nifty 50": "^NSEI",
    "Sensex": "^BSESN",
    "Bank Nifty": "^NSEBANK",
}

COMMODITY_SYMBOLS = {
    "Gold": "GC=F",
    "Crude Oil": "CL=F",
    "USD/INR": "USDINR=X",
}

RSS_FEEDS = {
    "Moneycontrol": "https://www.moneycontrol.com/rss/marketreports.xml",
    "Economic Times": "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
}


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Required
    telegram_token: str = ""
    telegram_chat_id: int = 0

    # Optional
    newsapi_key: str = ""
    kite_api_key: str = ""
    kite_api_secret: str = ""

    # Scheduling
    briefing_hour: int = 9
    briefing_minute: int = 25

    # Constants
    index_symbols: dict = field(default_factory=lambda: INDEX_SYMBOLS)
    commodity_symbols: dict = field(default_factory=lambda: COMMODITY_SYMBOLS)
    rss_feeds: dict = field(default_factory=lambda: RSS_FEEDS)


def load_config(env_path: Optional[str] = None) -> Config:
    """Load configuration from .env file.

    Args:
        env_path: Optional path to .env file. Defaults to project root.

    Returns:
        Config: Validated configuration object.

    Raises:
        ValueError: If required environment variables are missing.
    """
    load_dotenv(env_path)

    # Required vars
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id_str = os.getenv("TELEGRAM_CHAT_ID", "0")

    if not telegram_token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN is required. "
            "Get one from @BotFather on Telegram."
        )

    if telegram_chat_id_str == "0":
        raise ValueError(
            "TELEGRAM_CHAT_ID is required. "
            "Send a message to @userinfobot on Telegram to get your chat ID."
        )

    return Config(
        telegram_token=telegram_token,
        telegram_chat_id=int(telegram_chat_id_str),
        newsapi_key=os.getenv("NEWSAPI_KEY", ""),
        kite_api_key=os.getenv("KITE_API_KEY", ""),
        kite_api_secret=os.getenv("KITE_API_SECRET", ""),
        briefing_hour=int(os.getenv("BRIEFING_HOUR", "9")),
        briefing_minute=int(os.getenv("BRIEFING_MINUTE", "25")),
    )
