import os
import re
import logging
import asyncio
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, LinkPreviewOptions, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from pydub import AudioSegment
import speech_recognition as sr

# Import local modules
import database as db
import market

# Load environment variables
from functools import wraps

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_TELEGRAM_CHAT_ID = os.getenv("ALLOWED_TELEGRAM_CHAT_ID")
if ALLOWED_TELEGRAM_CHAT_ID:
    try:
        ALLOWED_TELEGRAM_CHAT_ID = int(ALLOWED_TELEGRAM_CHAT_ID)
    except ValueError:
        ALLOWED_TELEGRAM_CHAT_ID = None

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def restricted(func):
    """Decorator to restrict access to command/message handlers to a specific chat ID."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat_id = update.effective_chat.id
        if ALLOWED_TELEGRAM_CHAT_ID and chat_id != ALLOWED_TELEGRAM_CHAT_ID:
            logger.warning(f"Unauthorized access attempt by chat_id {chat_id}")
            await update.message.reply_text(
                "❌ *Unauthorized Access.*\nThis bot is restricted to its owner.",
                parse_mode="Markdown"
            )
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# Map spoken asset names to standard tickers
COIN_MAPPING = {
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH", "ether": "ETH",
    "solana": "SOL", "sol": "SOL",
    "cardano": "ADA", "ada": "ADA",
    "ripple": "XRP", "xrp": "XRP",
    "polkadot": "DOT", "dot": "DOT",
    "dogecoin": "DOGE", "doge": "DOGE",
    "avalanche": "AVAX", "avax": "AVAX",
    "link": "LINK", "chainlink": "LINK",
    "polygon": "MATIC", "matic": "MATIC",
    "near": "NEAR",
    "sui": "SUI",
    "pepe": "PEPE"
}

def parse_spoken_number(text: str) -> float:
    """Parses text representing a number (e.g., 'zero point five' or '10.5') to float."""
    num_words = {
        "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
        "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
        "half": "0.5", "point": "."
    }
    
    words = text.lower().split()
    processed_words = []
    for w in words:
        if w in num_words:
            processed_words.append(num_words[w])
        else:
            processed_words.append(w)
            
    joined = "".join(processed_words)
    # Search for numeric parts like "0.5" or "100"
    match = re.search(r'\d+(\.\d+)?', joined)
    if match:
        return float(match.group())
    return None

def parse_voice_command(text: str) -> dict:
    """Parses transcribed voice command text into structured action dictionary."""
    text_lower = text.lower().strip()
    
    # 1. Balance check
    if any(k in text_lower for k in ["balance", "portfolio", "allocation", "holdings", "how much"]):
        return {"action": "balance"}
        
    # 2. Analysis / TA
    if any(k in text_lower for k in ["analyze", "analysis", "signal", "chart", "evaluate"]):
        # Look for a coin name in mapping
        for name, ticker in COIN_MAPPING.items():
            if name in text_lower:
                return {"action": "analyze", "symbol": ticker}
        # Fallback to extracting the next word after "analyze/analysis"
        words = text_lower.split()
        for idx, w in enumerate(words):
            if w in ["analyze", "analysis", "evaluate"] and idx + 1 < len(words):
                return {"action": "analyze", "symbol": words[idx+1].upper()}
                
    # 3. Add coin
    if any(k in text_lower for k in ["add", "buy", "acquire"]):
        # Find coin
        found_coin = None
        for name, ticker in COIN_MAPPING.items():
            if name in text_lower:
                found_coin = ticker
                break
                
        amount = parse_spoken_number(text_lower)
        
        # Fallback for ticker parsing (e.g. "add BTC")
        if not found_coin:
            words = re.findall(r'\b[a-z]{3,5}\b', text_lower)
            for w in words:
                if w.upper() not in ["USDT", "USD", "ADD", "BUY"]:
                    found_coin = w.upper()
                    break
                    
        # Check for price
        buy_price = None
        price_match = re.search(r'(?:at|price|for)\s+(\d+(?:\.\d+)?)(?:\s*thousand)?', text_lower)
        if price_match:
            price_val = float(price_match.group(1))
            if "thousand" in price_match.group(0):
                price_val *= 1000
            buy_price = price_val
            
        if found_coin and amount is not None:
            # Check for wallet keyword
            wallet = 'default'
            if 'ledger' in text_lower or 'cold' in text_lower:
                wallet = 'ledger'
            elif 'rabby' in text_lower or 'hot' in text_lower:
                wallet = 'rabby'
            elif 'metamask' in text_lower:
                wallet = 'metamask'
            return {"action": "add", "symbol": found_coin, "amount": amount, "buy_price": buy_price, "wallet": wallet}
            
    # 4. Remove coin
    if any(k in text_lower for k in ["remove", "sell", "delete", "reduce"]):
        found_coin = None
        for name, ticker in COIN_MAPPING.items():
            if name in text_lower:
                found_coin = ticker
                break
        amount = parse_spoken_number(text_lower)
        
        if not found_coin:
            words = re.findall(r'\b[a-z]{3,5}\b', text_lower)
            for w in words:
                if w.upper() not in ["USDT", "USD", "SELL", "REMOVE"]:
                    found_coin = w.upper()
                    break
                    
        if found_coin:
            # Check for wallet keyword
            wallet = 'default'
            if 'ledger' in text_lower or 'cold' in text_lower:
                wallet = 'ledger'
            elif 'rabby' in text_lower or 'hot' in text_lower:
                wallet = 'rabby'
            elif 'metamask' in text_lower:
                wallet = 'metamask'
            return {"action": "remove", "symbol": found_coin, "amount": amount, "wallet": wallet}
            
    return {"action": "unknown", "text": text}

def make_allocation_bar(percentage: float, width: int = 10) -> str:
    """Generates a text-based progress bar for allocation visual."""
    filled = int(round(percentage / 100 * width))
    empty = width - filled
    return "▓" * filled + "░" * empty

async def get_portfolio_summary_text(chat_id: int) -> str:
    """Helper to generate a formatted Markdown summary of the user's portfolio."""
    portfolio = db.get_portfolio(chat_id)
    if not portfolio:
        return "❌ *Your portfolio is empty.*\nUse `/add <symbol> <amount> [buy_price] [wallet]` to add coins!"
        
    # Get all symbols to fetch prices in batch
    symbols = [item['symbol'] for item in portfolio]
    try:
        prices = market.get_live_prices(symbols)
    except Exception as e:
        logger.error(f"Error fetching live prices: {e}")
        return "⚠️ *Error fetching live prices.* Please try again later."
        
    total_val = 0.0
    items_data = []
    
    # Calculate values
    for item in portfolio:
        symbol = item['symbol']
        amount = item['amount']
        buy_price = item['buy_price']
        wallet = item.get('wallet', 'default')
        
        current_price = prices.get(symbol, 0.0)
        current_value = amount * current_price
        total_val += current_value
        
        # Calculate PnL if buy price is registered
        pnl_pct = 0.0
        pnl_usd = 0.0
        if buy_price and buy_price > 0:
            pnl_usd = current_value - (amount * buy_price)
            pnl_pct = (pnl_usd / (amount * buy_price)) * 100
            
        items_data.append({
            "symbol": symbol,
            "amount": amount,
            "current_price": current_price,
            "current_value": current_value,
            "buy_price": buy_price,
            "pnl_usd": pnl_usd,
            "pnl_pct": pnl_pct,
            "wallet": wallet
        })
        
    if total_val == 0.0:
        total_val = 1.0  # Prevent division by zero if all values are zero
        
    # Group items by wallet
    wallets_grouped = {}
    for item in items_data:
        w = item['wallet'].lower()
        if w not in wallets_grouped:
            wallets_grouped[w] = []
        wallets_grouped[w].append(item)
        
    # Build text response
    msg = f"📊 *Portfolio Balance Overview*\n"
    msg += f"📅 _As of {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n\n"
    msg += f"💰 *Total Balance:* `${total_val:,.2f} USD`\n\n"
    
    # Sort wallet names: 'default' first, then others alphabetically
    def wallet_sort_key(name):
        if name == 'default':
            return '0'
        return name
        
    sorted_wallets = sorted(wallets_grouped.keys(), key=wallet_sort_key)
    
    for wallet_name in sorted_wallets:
        items = wallets_grouped[wallet_name]
        display_name = wallet_name.capitalize()
        
        if wallet_name == 'ledger':
            icon = "🔒 Ledger (Cold)"
        elif wallet_name == 'rabby':
            icon = "🦊 Rabby (Hot)"
        elif wallet_name == 'metamask':
            icon = "🦊 MetaMask (Hot)"
        elif wallet_name == 'default':
            icon = "💼 General Portfolio"
        else:
            icon = f"💼 {display_name} Wallet"
            
        msg += f"*{icon}:*\n"
        items.sort(key=lambda x: x['current_value'], reverse=True)
        for item in items:
            pnl_str = ""
            if item['buy_price'] and item['buy_price'] > 0:
                indicator = "🟢 +" if item['pnl_usd'] >= 0 else "🔴 "
                pnl_str = f"\n   └ PnL: {indicator}${item['pnl_usd']:,.2f} ({item['pnl_pct']:.1f}%)"
                
            msg += f" • *{item['symbol']}*: {item['amount']:.4f} @ ${item['current_price']:,.2f} = *${item['current_value']:,.2f}*{pnl_str}\n"
        msg += "\n"
        
    # Allocation section (aggregated across all wallets)
    msg += "🍕 *Total Asset Allocation:*\n"
    symbol_totals = {}
    for item in items_data:
        sym = item['symbol']
        symbol_totals[sym] = symbol_totals.get(sym, 0.0) + item['current_value']
        
    sorted_symbols = sorted(symbol_totals.items(), key=lambda x: x[1], reverse=True)
    for sym, val in sorted_symbols:
        alloc_pct = (val / total_val) * 100
        bar = make_allocation_bar(alloc_pct)
        msg += f"`{sym:<5}` | {bar} | *{alloc_pct:.1f}%*\n"
        
    return msg

# --- COMMAND HANDLERS ---

@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends start message and registers user."""
    chat_id = update.effective_chat.id
    db.register_user(chat_id)
    
    welcome_text = (
        "🤖 *Welcome to the Crypto Portfolio Companion Bot!*\n\n"
        "I can help you track your crypto holdings, analyze markets, and send you weekly digests.\n\n"
        "📝 *Available Commands:*\n"
        "• `/balance` - Check your total balance and allocation\n"
        "• `/add <symbol> <amount> [price] [wallet]` - Add coin to portfolio (e.g. `/add BTC 0.5 60000 ledger`)\n"
        "• `/remove <symbol> [amount] [wallet]` - Remove holdings (e.g. `/remove ETH 1 ledger` or `/remove SOL rabby` to delete completely)\n"
        "• `/analyze <symbol>` - Run Technical Analysis on a coin (e.g. `/analyze BTC`)\n"
        "• `/schedule <Day HH:MM>` - Customize weekly report time (e.g. `/schedule Sun 18:00`)\n\n"
        "🎙️ *Voice Notes:*\n"
        "You can also **send a voice note** telling me what to do! Try saying:\n"
        "• _'What is my portfolio balance?'_\n"
        "• _'Analyze Solana'_ \n"
        "• _'Add zero point five Bitcoin on my ledger'_"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends list of commands."""
    await start_command(update, context)

@restricted
async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Replies with user portfolio balance."""
    chat_id = update.effective_chat.id
    msg = await get_portfolio_summary_text(chat_id)
    await update.message.reply_text(msg, parse_mode="Markdown")

@restricted
async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adds a holding to the portfolio."""
    chat_id = update.effective_chat.id
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text(
            "❌ *Usage:* `/add <symbol> <amount> [buy_price] [wallet]`\nExample: `/add BTC 0.5 60000 ledger` or `/add ETH 2 rabby`",
            parse_mode="Markdown"
        )
        return
        
    symbol = args[0].upper().strip()
    try:
        amount = float(args[1])
        buy_price = None
        wallet = 'default'
        
        if len(args) > 2:
            try:
                buy_price = float(args[2])
                if len(args) > 3:
                    wallet = args[3].strip()
            except ValueError:
                wallet = args[2].strip()
                
        # Verify symbol with exchange to prevent typo additions
        try:
            market.get_live_price(symbol)
        except Exception:
            await update.message.reply_text(f"⚠️ *Warning:* Symbol '{symbol}' could not be verified on the exchange. Adding anyway...")
            
        db.add_holding(chat_id, symbol, amount, buy_price, wallet)
        
        success_msg = f"✅ Added *{amount:.4f} {symbol}* to your *{wallet}* wallet."
        if buy_price:
            success_msg += f" (Buy price: ${buy_price:,.2f})"
        await update.message.reply_text(success_msg, parse_mode="Markdown")
        
    except ValueError:
        await update.message.reply_text("❌ Amount and price must be valid numbers.")

@restricted
async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Removes a holding from the portfolio."""
    chat_id = update.effective_chat.id
    args = context.args
    
    if len(args) < 1:
        await update.message.reply_text(
            "❌ *Usage:* `/remove <symbol> [amount] [wallet]`\nExample: `/remove ETH ledger` or `/remove ETH 0.5 rabby`",
            parse_mode="Markdown"
        )
        return
        
    symbol = args[0].upper().strip()
    amount = None
    wallet = 'default'
    
    if len(args) > 1:
        try:
            amount = float(args[1])
            if len(args) > 2:
                wallet = args[2].strip()
        except ValueError:
            wallet = args[1].strip()
            
    try:
        db.remove_holding(chat_id, symbol, amount, wallet)
        if amount:
            await update.message.reply_text(f"✅ Removed *{amount:.4f} {symbol}* from your *{wallet}* holdings.", parse_mode="Markdown")
        else:
            await update.message.reply_text(f"✅ Removed *{symbol}* completely from your *{wallet}* wallet.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error removing asset: {e}")

@restricted
async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs technical analysis report for a coin or all portfolio coins."""
    chat_id = update.effective_chat.id
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ *Usage:* `/analyze <symbol>` or `/analyze all`",
            parse_mode="Markdown"
        )
        return
        
    symbol = args[0].upper().strip()
    
    if symbol == "ALL":
        portfolio = db.get_portfolio(chat_id)
        if not portfolio:
            await update.message.reply_text("❌ *Your portfolio is empty.*", parse_mode="Markdown")
            return
            
        # Get unique symbols resolved to underlying standard assets, excluding stablecoins
        unique_symbols = sorted(list(set(
            market.resolve_ta_symbol(item['symbol']) for item in portfolio
            if not re.match(r'^(A?USDT|A?USDC|A?DAI|BUSD|USD)$', market.resolve_ta_symbol(item['symbol']))
        )))
        
        if not unique_symbols:
            await update.message.reply_text("❌ No analyzeable assets (excluding stablecoins) found in your portfolio.")
            return
            
        await update.message.reply_text(f"🔍 Analyzing unique portfolio assets: {', '.join(unique_symbols)}... Please wait.", parse_mode="Markdown")
        
        msg = "📈 *Portfolio Technical Analysis Overview*\n\n"
        for sym in unique_symbols:
            report = market.run_technical_analysis(sym)
            if "error" in report:
                msg += f"• *{sym}*: ❌ Error ({report['error']})\n\n"
            else:
                # Brief details
                detail_parts = []
                if report['rsi'] < 30:
                    detail_parts.append("Oversold")
                elif report['rsi'] > 70:
                    detail_parts.append("Overbought")
                
                crossover = [s for s in report['signals'] if "Crossover" in s]
                if crossover:
                    detail_parts.append("MACD cross")
                    
                details = f" ({', '.join(detail_parts)})" if detail_parts else ""
                msg += (
                    f"• *{sym}*: `${report['price']:,.2f}` ➔ *{report['recommendation']}*{details}\n"
                    f"  RSI: `{report['rsi']:.1f}` | SMA20: `${report['sma20']:,.2f}`\n\n"
                )
                
        await update.message.reply_text(msg, parse_mode="Markdown")
        return
        
    # Single symbol analysis
    await update.message.reply_text(f"🔍 Fetching data and analyzing *{symbol}*... Please wait.", parse_mode="Markdown")
    
    report = market.run_technical_analysis(symbol)
    if "error" in report:
        await update.message.reply_text(f"❌ *Analysis Failed:* {report['error']}", parse_mode="Markdown")
        return
        
    # Format analysis report
    msg = f"📈 *Technical Analysis Report: {report['symbol']}*\n"
    msg += f"💵 *Current Price:* `${report['price']:,.2f} USDT`\n\n"
    
    msg += f"📊 *Indicators:*\n"
    msg += f"• *RSI (14):* `{report['rsi']:.1f}`\n"
    msg += f"• *MACD Line:* `{report['macd']:.4f}` | *Signal Line:* `{report['macd_signal']:.4f}`\n"
    msg += f"• *SMA (20):* `${report['sma20']:,.2f}`\n"
    msg += f"• *SMA (50):* `${report['sma50']:,.2f}`\n\n"
    
    msg += f"🧠 *Signal Breakdown:*\n"
    for sig in report['signals']:
        msg += f"  - {sig}\n"
        
    msg += f"\n💡 *Recommendation:* *{report['recommendation']}*\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

@restricted
async def schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Updates user weekly report schedule."""
    chat_id = update.effective_chat.id
    args = context.args
    
    if not args:
        sched = db.get_weekly_schedule(chat_id)
        status = "enabled" if sched['weekly_report_enabled'] else "disabled"
        await update.message.reply_text(
            f"📅 *Your Current Schedule:* `{sched['weekly_report_time']}` ({status})\n\n"
            f"To change, use: `/schedule <Day HH:MM>`\n"
            f"Example: `/schedule Sun 18:00` or `/schedule Mon 09:30`\n"
            f"To disable, use `/schedule disable`",
            parse_mode="Markdown"
        )
        return
        
    option = args[0].strip().lower()
    if option == "disable":
        db.update_weekly_schedule(chat_id, enabled=False)
        await update.message.reply_text("✅ Weekly report digest has been *disabled*.", parse_mode="Markdown")
        return
        
    # Attempt to parse Day HH:MM
    try:
        time_str = " ".join(args)
        # Validate format
        parts = time_str.split()
        if len(parts) != 2:
            raise ValueError()
        
        day_part = parts[0].capitalize()
        time_part = parts[1]
        
        if not re.match(r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)$', day_part, re.IGNORECASE):
            raise ValueError()
        if not re.match(r'^\d{2}:\d{2}$', time_part):
            raise ValueError()
            
        short_day = day_part[:3]
        clean_sched = f"{short_day} {time_part}"
        
        db.update_weekly_schedule(chat_id, enabled=True, time_str=clean_sched)
        await update.message.reply_text(f"✅ Schedule updated! You will receive weekly reports on *{clean_sched}*.", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ Invalid format. Please use `Day HH:MM`. Example: `/schedule Sun 18:00`")

# --- VOICE NOTE HANDLER ---

@restricted
async def voice_note_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming Telegram voice notes, transcribes them, and runs commands."""
    chat_id = update.effective_chat.id
    voice = update.message.voice
    
    if not voice:
        return
        
    await update.message.reply_text("🎙️ _Voice note received. Downloading and transcribing..._")
    
    # Create temp directory for audio conversion
    with tempfile.TemporaryDirectory() as temp_dir:
        ogg_path = os.path.join(temp_dir, "voice.ogg")
        wav_path = os.path.join(temp_dir, "voice.wav")
        
        try:
            # Download file
            file = await context.bot.get_file(voice.file_id)
            await file.download_to_drive(ogg_path)
            
            # Convert OGG to WAV using pydub
            audio = AudioSegment.from_file(ogg_path, format="ogg")
            audio.export(wav_path, format="wav")
            
            # Transcribe audio using SpeechRecognition
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
                
            # Perform transcription via Google Web Speech (Free, Option A)
            try:
                transcription = recognizer.recognize_google(audio_data)
                logger.info(f"Transcribed voice note for {chat_id}: {transcription}")
                await update.message.reply_text(f"🗣️ *Transcribed speech:* \"{transcription}\"")
            except sr.UnknownValueError:
                await update.message.reply_text("❌ Could not understand the voice note. Please speak clearly and try again.")
                return
            except sr.RequestError as e:
                await update.message.reply_text(f"⚠️ Speech Recognition service error: {e}")
                return
                
            # Parse the voice command
            parsed = parse_voice_command(transcription)
            action = parsed.get("action")
            
            if action == "balance":
                await update.message.reply_text("🔄 Processing: *Check Portfolio Balance*...")
                msg = await get_portfolio_summary_text(chat_id)
                await update.message.reply_text(msg, parse_mode="Markdown")
                
            elif action == "analyze":
                symbol = parsed.get("symbol")
                await update.message.reply_text(f"🔄 Processing: *Analyze {symbol}*...")
                report = market.run_technical_analysis(symbol)
                if "error" in report:
                    await update.message.reply_text(f"❌ *Analysis Failed:* {report['error']}")
                    return
                msg = (
                    f"📈 *Technical Analysis: {report['symbol']}*\n"
                    f"💵 *Price:* `${report['price']:,.2f} USDT`\n"
                    f"💡 *Signal:* *{report['recommendation']}*\n"
                    f"RSI: `{report['rsi']:.1f}` | MACD: `{report['macd']:.4f}`"
                )
                await update.message.reply_text(msg, parse_mode="Markdown")
                
            elif action == "add":
                symbol = parsed.get("symbol")
                amount = parsed.get("amount")
                buy_price = parsed.get("buy_price")
                wallet = parsed.get("wallet", "default")
                await update.message.reply_text(f"🔄 Processing: *Add {amount} {symbol} to {wallet}*...")
                
                db.add_holding(chat_id, symbol, amount, buy_price, wallet)
                success = f"✅ Added *{amount:.4f} {symbol}* to your *{wallet}* wallet."
                if buy_price:
                    success += f" (Buy price: ${buy_price:,.2f})"
                await update.message.reply_text(success, parse_mode="Markdown")
                
            elif action == "remove":
                symbol = parsed.get("symbol")
                amount = parsed.get("amount")
                wallet = parsed.get("wallet", "default")
                await update.message.reply_text(f"🔄 Processing: *Remove {symbol} from {wallet}*...")
                
                db.remove_holding(chat_id, symbol, amount, wallet)
                if amount:
                    await update.message.reply_text(f"✅ Removed *{amount:.4f} {symbol}* from your *{wallet}* holdings.", parse_mode="Markdown")
                else:
                    await update.message.reply_text(f"✅ Removed *{symbol}* completely from your *{wallet}* wallet.", parse_mode="Markdown")
                    
            else:
                await update.message.reply_text(
                    "❓ I understood your speech, but couldn't map it to a specific action.\n"
                    "Try phrases like:\n"
                    "• _'Show my balance'_\n"
                    "• _'Analyze Bitcoin'_\n"
                    "• _'Add one point five Ethereum'_\n"
                    "• _'Remove Solana'_",
                    parse_mode="Markdown"
                )
        except Exception as e:
            logger.error(f"Error handling voice note: {e}")
            await update.message.reply_text("❌ An error occurred while processing your voice note.")

# --- SCHEDULER JOB ---

async def weekly_digest_job(context: ContextTypes.DEFAULT_TYPE):
    """Job that runs periodically (every 10 min) to check schedule and send weekly digests."""
    now = datetime.now()
    current_day = now.strftime("%a")       # Sun, Mon, etc.
    current_hour_min = now.strftime("%H:%M") # 18:00, etc.
    current_date = now.strftime("%Y-%m-%d")  # 2026-07-18
    
    # Format to look for in DB: "Sun 18:00"
    current_sched_key = f"{current_day} {current_hour_min}"
    
    users = db.get_all_users_for_weekly()
    for user in users:
        chat_id = user["chat_id"]
        scheduled_time = user["weekly_report_time"] # e.g. "Sun 18:00"
        last_sent = user["last_report_sent"]        # e.g. "2026-07-12"
        
        # Parse user scheduled details
        try:
            parts = scheduled_time.split()
            user_day = parts[0][:3].capitalize() # Ensure "Sun" or "Mon" etc.
            user_time = parts[1]                 # "18:00"
            
            # Check if current day matches and we are within the target hour
            # (To be safe with scheduling, we check if current day and hour match, 
            # and we haven't sent the report on this calendar date yet).
            now_day = now.strftime("%a")
            now_hour = now.hour
            
            user_hour = int(user_time.split(":")[0])
            
            if now_day == user_day and now_hour == user_hour and last_sent != current_date:
                logger.info(f"Triggering scheduled weekly report for chat {chat_id}")
                
                # Send a header
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="🔔 *Your Scheduled Weekly Portfolio Summary is ready!*",
                    parse_mode="Markdown"
                )
                
                # Send portfolio overview
                summary = await get_portfolio_summary_text(chat_id)
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=summary,
                    parse_mode="Markdown"
                )
                
                # Send technical analysis for portfolio assets
                portfolio = db.get_portfolio(chat_id)
                unique_symbols = sorted(list(set(
                    market.resolve_ta_symbol(item['symbol']) for item in portfolio
                    if not re.match(r'^(A?USDT|A?USDC|A?DAI|BUSD|USD)$', market.resolve_ta_symbol(item['symbol']))
                )))
                
                if unique_symbols:
                    ta_text = "📈 *Weekly Technical Analysis Summary:*\n\n"
                    for symbol in unique_symbols:
                        try:
                            report = market.run_technical_analysis(symbol)
                            if "error" in report:
                                ta_text += f"• *{symbol}*: Error calculating TA ({report['error']})\n"
                            else:
                                ta_text += (
                                    f"• *{symbol}*: `${report['price']:,.2f}` | "
                                    f"RSI: `{report['rsi']:.1f}` | "
                                    f"Signal: *{report['recommendation']}*\n"
                                )
                        except Exception as e:
                            ta_text += f"• *{symbol}*: Failed to fetch TA data: {e}\n"
                            
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text=ta_text,
                        parse_mode="Markdown"
                    )
                
                # Update last sent date to avoid double sends in the same hour
                db.update_last_report_sent(chat_id, current_date)
        except Exception as e:
            logger.error(f"Error executing weekly job for user {chat_id}: {e}")

async def post_init(application: Application):
    """Sets up auto-complete bot commands in the Telegram interface."""
    commands = [
        BotCommand("balance", "Show portfolio balance and allocation"),
        BotCommand("add", "Add holdings: /add <symbol> <amount> [price] [wallet]"),
        BotCommand("remove", "Remove holdings: /remove <symbol> [amount] [wallet]"),
        BotCommand("analyze", "Run technical analysis: /analyze <symbol> or all"),
        BotCommand("schedule", "Customize weekly report: /schedule [Day HH:MM]"),
        BotCommand("help", "Show instructions and command usage")
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Auto-complete commands configured successfully.")

# --- MAIN ---

def main():
    """Starts the bot."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("❌ ERROR: Please configure TELEGRAM_BOT_TOKEN in the .env file.")
        return
        
    # Initialize DB
    db.init_db()
    
    # Build application
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("portfolio", balance_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("analyze", analyze_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    
    # Register voice note handler
    application.add_handler(MessageHandler(filters.VOICE, voice_note_handler))
    
    # Register job queue check running every 10 minutes (600 seconds)
    # This will check the database schedules
    job_queue = application.job_queue
    job_queue.run_repeating(weekly_digest_job, interval=600, first=10)
    
    logger.info("Bot started and listening for commands/voices...")
    application.run_polling()

if __name__ == "__main__":
    main()
