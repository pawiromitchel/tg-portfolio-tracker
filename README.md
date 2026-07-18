# 🤖 Crypto Portfolio Telegram Bot with Voice Commands

A powerful, privacy-respecting Telegram Bot that helps you track your cryptocurrency holdings across multiple wallets (e.g. Ledger, Rabby, Kamino, Kraken), evaluate technical analysis indicators on-demand, and receive scheduled weekly performance reports. 

It supports natural speech voice commands (Speech-to-Text) and automatically configures autocomplete commands in the Telegram client.

---

## ✨ Features
1. **Multi-Wallet Tracking:** Organize assets under specific wallets or platforms (e.g. `ledger`, `rabby`, `kamino`, `kraken`, `aave`) to see individual balances and total aggregated portfolio allocations.
2. **Dynamic CRUD Commands:** `/add` and `/remove` coins from specific wallets directly from Telegram.
3. **Automated Weekly Digest:** Scheduled broadcasts of your portfolio performance on **Mondays at 08:00 AM**, including a technical analysis summary of your volatile assets.
4. **On-Demand Technical Analysis:** Retrieve technical indicators (RSI, MACD, SMA 20/50) and buy/sell signals on-demand with `/analyze <symbol>` or get a consolidated overview of all your volatile holdings with `/analyze all`.
5. **Speech Commands:** Control the bot by sending voice messages!
6. **Built-in Security (Access Control):** Restrict the bot to respond ONLY to your Telegram Chat ID.
7. **Smart Asset Pegs:** Automatically values common stablecoins and yield tokens (e.g., `USDC`, `USDT`, `aUSDC`, `aUSDT`, `DAI`, `BUSD`) at $1.00 and resolves Aave yield tokens (e.g. `aETH`, `acbBTC`) to their underlying asset price.

---

## 🛠️ Prerequisites
- Python 3.9+
- `ffmpeg` (required for converting voice notes from Telegram `.ogg` to `.wav`)

---

## 🚀 Setup & Execution

### 1. Set Your Environment Variables
Copy `.env.example` to `.env` and fill in your details:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
ALLOWED_TELEGRAM_CHAT_ID=your_telegram_chat_id_here
```
*Note: To restrict the bot to your account, configure `ALLOWED_TELEGRAM_CHAT_ID` with your Chat ID.*

### 2. Run the Local Simulation Test
Verify that the database, stablecoin mapping, technical indicators, and speech commands parse correctly on your machine:
```bash
.venv/bin/python simulate.py
```

### 3. Start the Bot
Run the bot service:
```bash
.venv/bin/python bot.py
```

---

## 🗣️ Voice Commands Guide
You can send voice notes to the bot instead of typing. Try saying:
* *"What is my portfolio balance?"*
* *"Analyze Bitcoin"*
* *"Add zero point five Bitcoin on my ledger"*
* *"Add ten Ethereum to my aave wallet"*
* *"Remove Solana from my kamino wallet"*

---

## 📝 Commands list for Telegram
The bot automatically configures these commands upon startup so they auto-complete when you type `/` in Telegram:
* `/balance` - Show your current portfolio value and asset allocation
* `/add <symbol> <amount> [price] [wallet]` - Add coins to a specific wallet
* `/remove <symbol> [amount] [wallet]` - Remove holdings from a wallet
* `/analyze <symbol> or all` - Run technical analysis on one or all assets
* `/schedule [Day HH:MM]` - Customize or disable the weekly summary report
* `/help` - Show bot instructions and command usage
