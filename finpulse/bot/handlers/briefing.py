"""FinPulse Morning Briefing Handler

Handles the /briefing command by pulling market data and news,
formatting them, and sending a comprehensive report to the authorized user.
"""

import asyncio
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from finpulse.config import load_config
from finpulse.data.market import fetch_market_snapshot
from finpulse.data.news import fetch_news_with_sentiment
from finpulse.utils.formatting import format_briefing
from finpulse.logger import get_logger

logger = get_logger("bot.handlers.briefing")


async def briefing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a manual morning briefing to the user."""
    # Safety check: update could be triggered by inline query or message
    if not update.message or not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    config = load_config()
    
    # Restrict to configured chat ID (single-user bot security)
    if chat_id != config.telegram_chat_id:
        logger.warning(f"Unauthorized briefing query attempt from chat ID: {chat_id}")
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
        
    # Send a temporary loading message
    status_message = await update.message.reply_text(
        "⏳ Fetching live market data and news headlines... Please wait."
    )
    
    try:
        # Show typing indicator in chat
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # Fetch market snapshot and news concurrently (force fresh update on manual trigger)
        snapshot_task = fetch_market_snapshot(use_cache=False)
        news_task = fetch_news_with_sentiment(config, n=5, use_cache=False)
        
        snapshot, news = await asyncio.gather(snapshot_task, news_task)
        
        # Format the HTML briefing report
        report = format_briefing(snapshot, news)
        
        # Delete loading status message
        await status_message.delete()
        
        # Send the final formatted report
        await update.message.reply_html(
            report,
            disable_web_page_preview=True,
        )
        logger.info(f"Manually sent morning briefing to chat ID: {chat_id}")
        
    except Exception as e:
        logger.exception("Failed to generate and send morning briefing")
        try:
            await status_message.edit_text("❌ Failed to generate briefing. Please check the logs.")
        except Exception:
            await update.message.reply_text("❌ Failed to generate briefing. Please check the logs.")
