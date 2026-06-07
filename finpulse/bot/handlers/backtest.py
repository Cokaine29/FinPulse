"""FinPulse Backtest Command Handlers Module

Handles `/backtest <STRATEGY> <SYMBOL> [YEARS]` and `/strategies` commands.
Validates the inputs, executes the historical simulation, and returns
the performance statistics along with the visual equity curve chart.
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from finpulse.config import load_config
from finpulse.data.market import validate_symbol
from finpulse.backtest.strategy import STRATEGY_REGISTRY
from finpulse.backtest.engine import BacktestEngine
from finpulse.backtest.report import format_backtest_report, generate_backtest_chart
from finpulse.logger import get_logger

logger = get_logger("bot.handlers.backtest")


async def strategies_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all available backtesting strategies."""
    if not update.message or not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    config = load_config()
    
    # Security check (single-user mode)
    if chat_id != config.telegram_chat_id:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
        
    lines = [
        "⚙️ <b>Available Backtesting Strategies:</b>",
        "",
        "1. <code>RSI_MEAN_REVERSION</code> - Buys when RSI falls below 35 (oversold), sells when RSI rises above 65 (overbought).",
        "2. <code>MACD_CROSSOVER</code> - Buys on bullish MACD histogram crossovers, sells on bearish crossovers.",
        "3. <code>BOLLINGER_BOUNCE</code> - Buys when price dips below the lower Bollinger Band, sells when it breaches the upper band.",
        "4. <code>EMA_CROSSOVER</code> - Buys on Golden Cross (EMA9 crossing above EMA21), sells on Death Cross.",
        "",
        "💡 <i>Usage:</i> <code>/backtest &lt;STRATEGY&gt; &lt;SYMBOL&gt; [YEARS]</code>",
    ]
    await update.message.reply_html("\n".join(lines))


async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run a strategy backtest and send visual and textual performance results."""
    if not update.message or not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    config = load_config()
    
    # Security check
    if chat_id != config.telegram_chat_id:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
        
    # Check arguments
    if not context.args or len(context.args) < 2:
        await update.message.reply_html(
            "❌ <b>Missing arguments.</b>\n\n"
            "Usage: <code>/backtest &lt;STRATEGY&gt; &lt;SYMBOL&gt; [YEARS]</code>\n"
            "Example: <code>/backtest RSI_MEAN_REVERSION RELIANCE 3</code>\n\n"
            "Type /strategies to see the list of available strategies."
        )
        return
        
    strategy_name = context.args[0].upper().strip()
    symbol = context.args[1].upper().strip()
    
    # Parse years (optional, default to 3)
    years = 3
    if len(context.args) >= 3:
        try:
            years = int(context.args[2])
            if years <= 0 or years > 10:
                await update.message.reply_text("❌ Years must be between 1 and 10.")
                return
        except ValueError:
            await update.message.reply_text("❌ Invalid years parameter. Must be an integer (e.g., 3).")
            return
            
    # Validate strategy
    if strategy_name not in STRATEGY_REGISTRY:
        strategies_list = ", ".join([f"<code>{s}</code>" for s in STRATEGY_REGISTRY.keys()])
        await update.message.reply_html(
            f"❌ Strategy <b>'{strategy_name}'</b> not found.\n\n"
            f"Valid strategies are: {strategies_list}"
        )
        return
        
    # Validate symbol
    status_message = await update.message.reply_html(f"🔍 Validating stock symbol <b>'{symbol}'</b>...")
    is_valid = await validate_symbol(symbol)
    if not is_valid:
        await status_message.edit_text(
            f"❌ Symbol <b>'{symbol}'</b> is invalid or not found on NSE.\n"
            f"Please verify the spelling (e.g. RELIANCE, TCS, INFY).",
            parse_mode=ParseMode.HTML,
        )
        return
        
    await status_message.edit_text(
        f"⏳ Running <code>{strategy_name}</code> backtest simulation for <b>'{symbol}'</b> over {years} years... Please wait."
    )
    
    try:
        # Show typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action="upload_photo")
        
        # Instantiate strategy and engine
        strategy_class = STRATEGY_REGISTRY[strategy_name]
        strategy = strategy_class()
        engine = BacktestEngine(strategy)
        
        # Run simulation
        result = await engine.run(symbol, years)
        if not result:
            await status_message.edit_text(f"❌ Backtest simulation failed for '{symbol}'.")
            return
            
        # Format HTML summary report
        report_html = format_backtest_report(result)
        
        # Generate chart bytes
        chart_bytes = generate_backtest_chart(result)
        
        # Delete temporary loading status message
        await status_message.delete()
        
        if chart_bytes:
            # Send chart with metrics summary as caption
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=chart_bytes,
                caption=report_html,
                parse_mode=ParseMode.HTML,
            )
        else:
            # Fallback to text only if chart generation fails
            await update.message.reply_html(report_html)
            
        logger.info(f"Successfully ran and sent backtest for {strategy_name} on {symbol}")
        
    except Exception as e:
        logger.exception(f"Error handling /backtest command for {strategy_name} on {symbol}")
        try:
            await status_message.edit_text("❌ Failed to complete backtest. Please check logs.")
        except Exception:
            await update.message.reply_text("❌ Failed to complete backtest. Please check logs.")
