# Todo: Crypto Portfolio Telegram Bot

## 📋 Project Roadmap

- [x] **Phase 1: Architecture & Requirements Gathering**
  - [x] Create project structure and design specification
  - [x] Gather user requirements and API keys / Telegram Token <!-- id: 0 -->
  - [x] Setup virtual environment and install dependencies <!-- id: 1 -->

- [x] **Phase 2: Database & Core Data Layer**
  - [x] Design and initialize SQLite database (`portfolio.db`) for tracking user holdings and schedules <!-- id: 2 -->
  - [x] Implement data models/services for portfolio management (CRUD operations) <!-- id: 3 -->
  - [x] Build Market Data Service (integrate CoinGecko/Binance public API via CCXT or simple requests) <!-- id: 4 -->

- [x] **Phase 3: Technical Analysis (TA) Engine**
  - [x] Implement utility to fetch daily OHLCV historical candle data <!-- id: 5 -->
  - [x] Implement TA indicators: RSI, MACD, Simple Moving Averages (SMA 20/50/200) <!-- id: 6 -->
  - [x] Implement a rule-based Signal Generator (Buy / Sell / Hold classification) <!-- id: 7 -->

- [x] **Phase 4: Telegram Bot Logic & Commands**
  - [x] Initialize Telegram Bot handler using `python-telegram-bot` <!-- id: 8 -->
  - [x] Implement Command: `/start` and `/help` <!-- id: 9 -->
  - [x] Implement Portfolio Commands: `/balance`, `/allocation`, `/holdings` <!-- id: 10 -->
  - [x] Implement Transaction Commands: `/add <symbol> <amount> [price]`, `/remove <symbol>` <!-- id: 11 -->
  - [x] Implement Analysis Command: `/analyze <symbol>` <!-- id: 12 -->
  - [x] Implement Voice Note Command Handler (Speech-to-Text transcription and execution) <!-- id: 18 -->

- [x] **Phase 5: Weekly Digest & Scheduler**
  - [x] Setup `APScheduler` for weekly portfolio summary broadcasts <!-- id: 13 -->
  - [x] Format weekly update message (Total balance change, top performers, allocation changes, TA summaries) <!-- id: 14 -->

- [ ] **Phase 6: Testing & Deployment Guide**
  - [x] Create interactive simulation script to test bot commands without running full telegram polling <!-- id: 15 -->
  - [ ] Create detailed deployment instructions (running systemd, Docker, or background processes) <!-- id: 16 -->
  - [ ] Final verification and user walk-through <!-- id: 17 -->

---

## 🛠️ Architectural Choices

- **Language**: Python 3.10+
- **Key Libraries**:
  - `python-telegram-bot`: Modern, asynchronous python library for Telegram bots.
  - `ccxt`: Cryptocurrency Exchange Calculator and Trading library for fetching reliable market prices and OHLCV from Binance, Coinbase, etc. without needing keys for public data.
  - `pandas`: For data structuring and easy calculations of indicators.
  - `apscheduler`: Advanced Python Scheduler for scheduling weekly reports.
  - `sqlite3`: Lightweight, zero-config relational database for saving portfolio balances.
  - `matplotlib` (Optional): To generate allocation pie charts and send them as Telegram photos.
  - `SpeechRecognition` or `openai`: For transcribing voice notes to text commands.
  - `pydub` / `ffmpeg`: For audio file conversion (Telegram sends `.ogg` files).
- **Security**: Environment variables (`.env`) for storing the Telegram Bot Token and speech-to-text API keys. No API keys stored in code.
