"""FinPulse Signal Command Handler Module

Handles the /signal <SYMBOL> command. Validates the symbol, generates a SignalReport,
renders a technical analysis chart, and replies to the user with the chart and formatted report.
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from finpulse.config import load_config
from finpulse.data.market import validate_symbol
from finpulse.analysis.signals import generate_signal
from finpulse.utils.charts import generate_stock_chart
from finpulse.utils.formatting import format_indian_number
from finpulse.logger import get_logger

logger = get_logger("bot.handlers.signal")


def get_signal_emoji(signal: str) -> str:
    """Helper to return appropriate emoji based on signal label."""
    if signal == "BUY":
        return "🟢"
    elif signal == "SELL":
        return "🔴"
    return "😐"


async def signal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Analyze a specific stock symbol and reply with indicators, ML signals, and chart."""
    if not update.message or not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    config = load_config()
    
    # Security check (single-user mode)
    if chat_id != config.telegram_chat_id:
        logger.warning(f"Unauthorized signal request from chat ID: {chat_id}")
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
        
    # Check arguments
    if not context.args:
        await update.message.reply_text(
            "Usage: /signal &lt;SYMBOL&gt;\nExample: <code>/signal RELIANCE</code>",
            parse_mode=ParseMode.HTML,
        )
        return
        
    symbol = context.args[0].upper().strip()
    
    # Check if NSE or BSE symbol is valid
    status_message = await update.message.reply_text(f"🔍 Validating symbol '{symbol}'...")
    is_valid = await validate_symbol(symbol)
    if not is_valid:
        await status_message.edit_text(
            f"❌ Symbol <b>'{symbol}'</b> is invalid or not found on NSE.\n"
            f"Please double check the spelling (e.g. RELIANCE, TCS, INFY).",
            parse_mode=ParseMode.HTML,
        )
        return
        
    await status_message.edit_text(f"⏳ Analyzing <b>'{symbol}'</b> and generating signals...")
    
    try:
        # Show typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        
        # Generate signal report and retrieve historical DataFrame
        result = await generate_signal(symbol)
        if not result:
            await status_message.edit_text(f"❌ Failed to generate signal analysis for '{symbol}'.")
            return
            
        report, df = result
        
        # Build text report
        price_fmt = format_indian_number(report.current_price, decimals=2)
        support_fmt = format_indian_number(report.support_level, decimals=2)
        res_fmt = format_indian_number(report.resistance_level, decimals=2)
        
        comb_emoji = get_signal_emoji(report.signal)
        rsi_emoji = get_signal_emoji(report.rsi_signal)
        macd_emoji = get_signal_emoji(report.macd_signal)
        bb_emoji = get_signal_emoji(report.bollinger_signal)
        ema_emoji = get_signal_emoji(report.ema_signal)
        ml_emoji = get_signal_emoji(report.ml_prediction)
        
        message_lines = [
            f"📊 <b>Signal Report — {report.symbol}</b>",
            "",
            f"<b>Combined Signal:</b> {comb_emoji} <b>{report.signal}</b>  (Confidence: <b>{report.confidence:.1f}%</b>)",
            f"💰 <b>Current Price:</b> ₹{price_fmt}",
            "",
            "📏 <b>TECHNICAL INDICATORS</b>",
            f"• RSI (14): {report.rsi_value:.1f}  ({rsi_emoji} {report.rsi_signal})",
            f"• MACD: {macd_emoji} {report.macd_signal}",
            f"• Bollinger Bands: {bb_emoji} {report.bollinger_signal}",
            f"• EMA (9/21): {ema_emoji} {report.ema_signal}",
            "",
            "🤖 <b>MACHINE LEARNING MODEL</b>",
            f"• Prediction: {ml_emoji} <b>{report.ml_prediction}</b>  (Confidence: <b>{report.ml_confidence:.1f}%</b>)",
            "",
            f"📈 <b>Support Level:</b> ₹{support_fmt}",
            f"📉 <b>Resistance Level:</b> ₹{res_fmt}",
            "",
            "⚠️ <i>This is not financial advice. Perform your own research.</i>",
        ]
        caption = "\n".join(message_lines)
        
        # Generate chart image
        chart_bytes = generate_stock_chart(symbol, df)
        
        # Delete the temporary status message
        await status_message.delete()
        
        if chart_bytes:
            # Send chart with the caption
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=chart_bytes,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
        else:
            # Fallback to text only if chart generation fails
            await update.message.reply_html(caption)
            
        logger.info(f"Successfully generated and sent signal report for {symbol} to chat ID: {chat_id}")
        
    except Exception as e:
        logger.exception(f"Error handling /signal command for {symbol}")
        try:
            await status_message.edit_text(f"❌ Error occurred during analysis of '{symbol}'. Please check logs.")
        except Exception:
            await update.message.reply_text(f"❌ Error occurred during analysis of '{symbol}'. Please check logs.")
