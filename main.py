"""FinPulse — Indian Market Intelligence Bot

Entry point for the FinPulse Telegram bot.
Initializes configuration, sets up the bot application,
and starts the polling loop.

Usage:
    python main.py
"""

import asyncio
import sys

from finpulse.config import load_config
from finpulse.logger import get_logger, setup_logging
from finpulse.bot.app import build_application

logger = get_logger("main")

BANNER = r"""
╔═══════════════════════════════════════════╗
║                                           ║
║   📊 FinPulse v1.0                        ║
║   Indian Market Intelligence Bot          ║
║                                           ║
║   Telegram • yfinance • ML Signals        ║
║                                           ║
╚═══════════════════════════════════════════╝
"""


def main() -> None:
    """Main entry point — loads config, builds bot, starts polling."""
    # Initialize logging
    setup_logging()

    logger.info(BANNER)
    logger.info("Starting FinPulse...")

    # Load configuration
    try:
        config = load_config()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error(
            "Please create a .env file based on .env.example "
            "and fill in the required values."
        )
        sys.exit(1)

    logger.info(f"Briefing scheduled at {config.briefing_hour:02d}:{config.briefing_minute:02d} IST")
    logger.info(f"Chat ID: {config.telegram_chat_id}")
    logger.info(f"NewsAPI: {'configured' if config.newsapi_key else 'not configured (RSS only)'}")
    logger.info(f"Kite API: {'configured' if config.kite_api_key else 'not configured'}")

    # Build and run bot
    app = build_application(config)

    logger.info("Bot is starting... Press Ctrl+C to stop.")
    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
