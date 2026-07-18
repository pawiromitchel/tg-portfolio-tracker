# 🤖 Crypto Portfolio Telegram Bot with Voice Commands

A Telegram Bot that helps you track your cryptocurrency holdings, evaluate technical analysis indicators on-demand, and receive scheduled weekly summary reports. It supports natural speech voice commands (Speech-to-Text).

---

## ✨ Features
1. **On-the-go Portfolio Tracking**: View your total balance and allocation breakdown.
2. **Dynamic CRUD Commands**: `/add` and `/remove` coins from your portfolio directly from Telegram.
3. **Automated Weekly Digest**: Scheduled broadcasts of your portfolio performance.
4. **On-Demand Technical Analysis**: Retrieve indicators (RSI, MACD, Moving Averages) and buy/sell signals with `/analyze <symbol>`.
5. **Speech Commands**: Control the bot by sending voice messages!

---

## 🛠️ Prerequisites
- Python 3.9+
- `ffmpeg` (already installed on this machine, required for voice note conversion)

---

## 🚀 Setup & Execution

### 1. Set Your Telegram Bot Token
1. Message `@BotFather` on Telegram.
2. Create a new bot with `/newbot` and follow the steps to retrieve your API token.
3. Open the `.env` file in the project folder and replace the placeholder token with your actual token:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   ```

### 2. Run the Local Simulation Test
Verify that the database, live pricing, and natural speech command parser work correctly on your machine:
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
* *"Add zero point five Ethereum at three thousand"*
* *"Remove Solana"*

---

## 📝 Commands list for Telegram
Copy and paste this list into `@BotFather` -> `/setcommands` to configure auto-completion:
```text
balance - Show your current portfolio value and asset allocation
add - Add coins to portfolio: /add <symbol> <amount> [price]
remove - Remove holdings: /remove <symbol> [amount]
analyze - Run technical analysis: /analyze <symbol>
schedule - Customize or disable weekly reports: /schedule [Day HH:MM]
help - Show bot instructions and command usage
```
