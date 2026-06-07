"""FinPulse Bot Application Setup

Central module that creates the Telegram bot application,
registers all command handlers, and configures error handling.
"""

import html
import traceback

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from finpulse.config import Config
from finpulse.logger import get_logger

logger = get_logger("bot.app")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for the bot.
    
    Logs the error and sends a user-friendly message.
    """
    logger.error(
        "Exception while handling an update:",
        exc_info=context.error,
    )

    # Build error message for the user
    if update and isinstance(update, Update) and update.effective_message:
        error_text = (
            "⚠️ *An error occurred*\n\n"
            "Something went wrong while processing your request. "
            "Please try again later.\n\n"
            f"Error: `{html.escape(str(context.error)[:200])}`"
        )
        try:
            await update.effective_message.reply_text(
                error_text,
                parse_mode="Markdown",
            )
        except Exception:
            # If we can't even send the error message, just log it
            logger.error("Failed to send error message to user")


def build_application(config: Config) -> Application:
    """Build and configure the Telegram bot application.
    
    Args:
        config: Application configuration.
    
    Returns:
        Configured Application instance ready for polling.
    """
    logger.info("Building Telegram bot application...")

    # Build application
    app = (
        Application.builder()
        .token(config.telegram_token)
        .build()
    )

    # Store config in bot_data for access in handlers
    app.bot_data["config"] = config

    # Register handlers (imported lazily to avoid circular imports)
    _register_handlers(app)

    # Setup job queue scheduler
    from finpulse.bot.scheduler import setup_scheduler
    setup_scheduler(app, config)

    # Register global error handler
    app.add_error_handler(error_handler)

    logger.info("Bot application built successfully")
    return app


def _register_handlers(app: Application) -> None:
    """Register all command and message handlers."""
    from finpulse.bot.handlers.start import start_command, help_command
    from finpulse.bot.handlers.briefing import briefing_command
    from finpulse.bot.handlers.signal import signal_command
    from finpulse.bot.handlers.backtest import backtest_command, strategies_command
    from finpulse.bot.handlers.portfolio import kitelogin_command, portfolio_command

    # Core commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("briefing", briefing_command))
    app.add_handler(CommandHandler("signal", signal_command))
    app.add_handler(CommandHandler("backtest", backtest_command))
    app.add_handler(CommandHandler("strategies", strategies_command))
    app.add_handler(CommandHandler("kitelogin", kitelogin_command))
    app.add_handler(CommandHandler("portfolio", portfolio_command))

    logger.info("Registered handlers: /start, /help, /briefing, /signal, /backtest, /strategies, /kitelogin, /portfolio")
