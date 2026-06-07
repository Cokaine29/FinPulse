"""FinPulse Start & Help Command Handlers

Handles /start and /help commands — the bot's entry points.
"""

from telegram import Update
from telegram.ext import ContextTypes

from finpulse.logger import get_logger

logger = get_logger("bot.handlers.start")

WELCOME_MESSAGE = """
🚀 *Welcome to FinPulse!*

Your AI-powered Indian market intelligence assistant.

━━━━━━━━━━━━━━━━━━━━━━━━

📋 *Commands:*

📊 /briefing — Morning market digest
📈 /signal `SYMBOL` — Buy/Sell/Hold signal
🧪 /backtest `STRAT SYMBOL YEARS` — Backtest a strategy
📜 /strategies — List available strategies
📂 /portfolio — Your Zerodha holdings & P&L
🔑 /kitelogin — Connect your Zerodha account
❓ /help — This message

━━━━━━━━━━━━━━━━━━━━━━━━

⏰ *Auto-briefing:* Daily at 9:25 AM IST (Mon-Fri)

⚠️ _This bot provides analysis only, not financial advice._
"""

HELP_MESSAGE = """
❓ *FinPulse Help*

━━━━━━━━━━━━━━━━━━━━━━━━

📊 *Market Briefing*
`/briefing` — Get today's market digest including:
  • Nifty 50, Sensex, Bank Nifty
  • Top gainers & losers
  • Commodities (Gold, Crude, USD/INR)
  • Top news with sentiment analysis

📈 *Signal Analysis*
`/signal RELIANCE` — Get a Buy/Sell/Hold signal for any NSE stock.
Uses RSI, MACD, Bollinger Bands, EMA + ML model.

🧪 *Backtesting*
`/backtest RSI_MEAN_REVERSION RELIANCE 3`
Test a trading strategy on historical data.
  • Strategy name (use /strategies to list)
  • Stock symbol
  • Number of years

📂 *Portfolio*
`/portfolio` — View your Zerodha holdings & P&L.
`/kitelogin` — Connect your Zerodha account first.

━━━━━━━━━━━━━━━━━━━━━━━━

💡 _Tip: The briefing runs automatically at 9:25 AM IST on weekdays._
"""


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command — welcome message."""
    user = update.effective_user
    logger.info(f"/start command from user {user.id} ({user.first_name})")

    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode="Markdown",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /help command — detailed help message."""
    user = update.effective_user
    logger.info(f"/help command from user {user.id} ({user.first_name})")

    await update.message.reply_text(
        HELP_MESSAGE,
        parse_mode="Markdown",
    )
