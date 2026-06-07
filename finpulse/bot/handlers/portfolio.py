"""FinPulse Zerodha Portfolio Telegram Handlers Module

Handles `/kitelogin` (authentication) and `/portfolio` (display holdings & stats) commands.
Restricts access to the authorized user (via Config.telegram_chat_id) and handles sessions.
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from finpulse.config import load_config
from finpulse.kite.auth import KiteAuthManager
from finpulse.kite.portfolio import get_portfolio_summary
from finpulse.utils.formatting import format_indian_number, format_change
from finpulse.logger import get_logger

logger = get_logger("bot.handlers.portfolio")


def _get_auth_manager() -> KiteAuthManager:
    """Helper to initialize auth manager with current config."""
    config = load_config()
    return KiteAuthManager(api_key=config.kite_api_key, api_secret=config.kite_api_secret)


async def kitelogin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide Zerodha login link or complete the login flow if token is provided."""
    if not update.message or not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    config = load_config()
    
    # Security check (single-user mode)
    if chat_id != config.telegram_chat_id:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
        
    auth = _get_auth_manager()
    
    # Check if Zerodha keys are configured in .env
    if not auth.is_configured():
        await update.message.reply_html(
            "❌ <b>Zerodha API keys are not configured.</b>\n\n"
            "Please add KITE_API_KEY and KITE_API_SECRET to your <code>.env</code> file "
            "and restart the bot to activate this feature."
        )
        return
        
    # Check if a request token was passed as an argument (e.g. /kitelogin <token>)
    if context.args:
        request_token = context.args[0].strip()
        status_message = await update.message.reply_text("⏳ Exchanging request token for session access token...")
        
        try:
            session_data = auth.complete_login(request_token)
            user_name = session_data.get("user_name", "User")
            await status_message.edit_text(
                f"✅ <b>Success!</b> Authenticated successfully with Zerodha.\n\n"
                f"Welcome, <b>{user_name}</b>! You can now use `/portfolio` to view holdings.",
                parse_mode=ParseMode.HTML,
            )
            logger.info(f"Successfully logged in user {user_name} to Zerodha")
        except Exception as e:
            logger.exception("Failed to exchange request token")
            await status_message.edit_text(
                f"❌ <b>Authentication failed.</b>\n\n"
                f"Error: <code>{str(e)}</code>\n"
                f"Please ensure the request token is correct and hasn't expired (valid for 5 mins).",
                parse_mode=ParseMode.HTML,
            )
        return
        
    # Standard flow: send login URL
    try:
        login_url = auth.get_login_url()
        lines = [
            "🔑 <b>Zerodha Kite OAuth Login</b>",
            "━━━━━━━━━━━━━━━━━━━━",
            "Please follow these steps to connect your Zerodha account:",
            "",
            f"1. Open this <a href='{login_url}'><b>Zerodha Login Link</b></a> in your browser.",
            "2. Log in with your Zerodha credentials.",
            "3. After logging in, you will be redirected to your Redirect URL. Look at the browser URL bar and copy the <code>request_token</code> parameter.",
            "4. Send it back to the bot like this:",
            "   <code>/kitelogin your_request_token</code>",
            "",
            "⚠️ <i>Note: The request token is valid only for 5 minutes.</i>",
        ]
        await update.message.reply_html("\n".join(lines), disable_web_page_preview=True)
    except Exception as e:
        logger.exception("Failed to generate login URL")
        await update.message.reply_text(f"❌ Failed to generate Zerodha login link: {e}")


async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and display Zerodha portfolio holdings, M2M, and P&L."""
    if not update.message or not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    config = load_config()
    
    # Security check
    if chat_id != config.telegram_chat_id:
        await update.message.reply_text("❌ You are not authorized to use this bot.")
        return
        
    auth = _get_auth_manager()
    
    if not auth.is_configured():
        await update.message.reply_text("❌ Zerodha API keys are not configured in .env.")
        return
        
    # Check if authenticated
    if not auth.is_authenticated():
        await update.message.reply_html(
            "❌ <b>Not logged into Zerodha.</b>\n\n"
            "Please run /kitelogin to authenticate your Zerodha session for today."
        )
        return
        
    status_message = await update.message.reply_text("⏳ Fetching your Zerodha portfolio... Please wait.")
    
    try:
        # Show typing status
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        
        # Fetch summary
        summary = await get_portfolio_summary(auth.kite)
        if not summary:
            await status_message.edit_text("❌ Failed to retrieve portfolio details. Please check logs.")
            return
            
        # Format holdings list
        lines = [
            "📂 <b>Your Zerodha Portfolio</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"📊 <b>HOLDINGS ({len(summary.holdings)} stocks)</b>",
            "",
            "<b>Symbol   Qty    Avg     LTP      P&L</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        
        if summary.holdings:
            for h in summary.holdings:
                # Format numbers
                avg_fmt = format_indian_number(h.avg_price, decimals=1)
                ltp_fmt = format_indian_number(h.last_price, decimals=1)
                pnl_val_fmt = format_indian_number(h.pnl, decimals=0)
                
                # Emojis
                change_emoji = "▲" if h.pnl >= 0 else "▼"
                sign = "+" if h.pnl >= 0 else ""
                
                # Shorten symbol if too long for tabular format
                sym = h.symbol[:8].ljust(8)
                qty = str(h.qty).ljust(5)
                
                lines.append(
                    f"<code>{sym} {qty} ₹{avg_fmt} ₹{ltp_fmt}</code>\n"
                    f"   {change_emoji} {sign}₹{pnl_val_fmt} ({h.pnl_pct:+.1f}%)"
                )
        else:
            lines.append("<i>No holdings found in your account</i>")
            
        # Format active positions summary if present
        if summary.positions:
            lines.extend([
                "",
                f"⚡ <b>ACTIVE POSITIONS ({len(summary.positions)})</b>",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            ])
            for p in summary.positions:
                ltp_fmt = format_indian_number(p.last_price, decimals=1)
                pnl_fmt = format_indian_number(p.pnl, decimals=0)
                change_emoji = "▲" if p.pnl >= 0 else "▼"
                sign = "+" if p.pnl >= 0 else ""
                
                sym = p.symbol[:8].ljust(8)
                qty = str(p.qty).ljust(5)
                
                lines.append(
                    f"<code>{sym} {qty} {p.product.ljust(4)} ₹{ltp_fmt}</code>\n"
                    f"   {change_emoji} {sign}₹{pnl_fmt}"
                )
                
        # Format summary section
        total_invested_fmt = format_indian_number(summary.total_invested, decimals=0)
        curr_val_fmt = format_indian_number(summary.current_value, decimals=0)
        total_pnl_fmt = format_indian_number(summary.total_pnl, decimals=0)
        day_pnl_fmt = format_indian_number(summary.day_pnl, decimals=0)
        
        pnl_change_fmt = format_change(summary.total_pnl_pct)
        day_pnl_emoji = "▲ +" if summary.day_pnl >= 0 else "▼ -"
        
        lines.extend([
            "",
            "💰 <b>PORTFOLIO SUMMARY</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            f"• Total Invested:  ₹{total_invested_fmt}",
            f"• Current Value:   ₹{curr_val_fmt}",
            f"• Overall P&L:     ₹{total_pnl_fmt}  ({pnl_change_fmt})",
            f"• Today's M2M P&L: {day_pnl_emoji}₹{format_indian_number(abs(summary.day_pnl), decimals=0)}",
        ])
        
        # Add top gainer/loser
        if summary.top_gainer:
            lines.append(f"🏆 Top Gainer: <b>{summary.top_gainer.symbol}</b> (+{summary.top_gainer.pnl_pct:.1f}%)")
        if summary.top_loser:
            lines.append(f"💀 Top Loser:  <b>{summary.top_loser.symbol}</b> ({summary.top_loser.pnl_pct:.1f}%)")
            
        await status_message.delete()
        await update.message.reply_html("\n".join(lines))
        logger.info(f"Successfully displayed portfolio for user on chat ID: {chat_id}")
        
    except Exception as e:
        logger.exception("Error displaying portfolio")
        try:
            await status_message.edit_text("❌ Error occurred while retrieving your portfolio details. Please check logs.")
        except Exception:
            await update.message.reply_text("❌ Error occurred while retrieving your portfolio details. Please check logs.")
