"""FinPulse Daily Briefing Scheduler

Integrates with python-telegram-bot's JobQueue to schedule the morning briefing daily.
Uses timezone-aware scheduling (Asia/Kolkata) to target 9:25 AM IST.
"""

import datetime
import pytz
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

from finpulse.config import Config, load_config
from finpulse.data.market import fetch_market_snapshot
from finpulse.data.news import fetch_news_with_sentiment
from finpulse.utils.formatting import format_briefing
from finpulse.logger import get_logger

logger = get_logger("bot.scheduler")


async def scheduled_briefing_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled task callback that fetches data and sends the morning briefing."""
    config = load_config()
    chat_id = config.telegram_chat_id
    
    logger.info("Executing scheduled morning briefing...")
    
    try:
        # Fetch fresh data (ignore cache for scheduled execution to guarantee latest post-open data)
        snapshot = await fetch_market_snapshot(use_cache=False)
        news = await fetch_news_with_sentiment(config, n=5, use_cache=False)
        
        # Format the briefing report
        report = format_briefing(snapshot, news)
        
        # Send message to configured chat ID
        await context.bot.send_message(
            chat_id=chat_id,
            text=report,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        logger.info(f"Scheduled morning briefing sent to chat ID: {chat_id}")
        
    except Exception as e:
        logger.exception("Error executing scheduled morning briefing")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text="❌ Scheduled morning briefing failed. Please check the logs.",
            )
        except Exception:
            pass


def setup_scheduler(application: Application, config: Config) -> None:
    """Register the scheduled morning briefing job in the application's JobQueue."""
    job_queue = application.job_queue
    if not job_queue:
        logger.error("JobQueue is not enabled/available in the Telegram application!")
        return
        
    # Get Asia/Kolkata (IST) timezone
    ist_tz = pytz.timezone("Asia/Kolkata")
    
    # Create timezone-aware time object for the run
    job_time = datetime.time(
        hour=config.briefing_hour,
        minute=config.briefing_minute,
        tzinfo=ist_tz,
    )
    
    # Register daily job
    job = job_queue.run_daily(
        callback=scheduled_briefing_callback,
        time=job_time,
        name="daily_morning_briefing",
    )
    
    logger.info(
        f"Scheduled morning briefing daily job registered at {config.briefing_hour:02d}:{config.briefing_minute:02d} IST"
    )
