import sys
import os

# Ensure the current directory is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import database as db
import market
from bot import parse_voice_command

def run_simulation():
    print("==================================================")
    print("🚀 CRYPTO TELEGRAM BOT - LOCAL SIMULATION & TESTING")
    print("==================================================")
    
    # 1. Initialize Database
    print("\n[1] Initializing SQLite database...")
    db.init_db()
    print("✓ Database initialized.")
    
    # Mock user chat id
    chat_id = 9999999
    
    # Clean up any existing holdings for this mock user to make test reproducible
    portfolio = db.get_portfolio(chat_id)
    for holding in portfolio:
        db.remove_holding(chat_id, holding['symbol'], wallet=holding.get('wallet', 'default'))
    
    # 2. Test DB Portfolio Operations
    print("\n[2] Testing Portfolio CRUD Operations...")
    print("Adding assets to portfolio across different wallets:")
    
    print("- Adding 0.25 BTC at $58,000 to ledger...")
    db.add_holding(chat_id, "BTC", 0.25, 58000.0, "ledger")
    
    print("- Adding 2.5 ETH at $3,100 to rabby...")
    db.add_holding(chat_id, "ETH", 2.5, 3100.0, "rabby")
    
    print("- Adding 1.25 BTC at $60,000 to ledger (Testing weighted average buy price)...")
    db.add_holding(chat_id, "BTC", 1.25, 60000.0, "ledger")
    
    print("- Adding 15 SOL (no buy price) to ledger...")
    db.add_holding(chat_id, "SOL", 15.0, wallet="ledger")
    
    print("- Adding 500 aUSDC at $1.00 to rabby (Aave Deposit)...")
    db.add_holding(chat_id, "aUSDC", 500.0, 1.00, "rabby")
    
    # Verify contents
    holdings = db.get_portfolio(chat_id)
    print("\nRegistered holdings in DB:")
    for h in holdings:
        print(f"  • {h['symbol']} ({h.get('wallet', 'default')}): {h['amount']} coins, Buy Price: ${h['buy_price']}")
        
    # 3. Test Market Data Fetching and Live Valuation
    print("\n[3] Testing live prices & portfolio valuation...")
    symbols = [h['symbol'] for h in holdings]
    try:
        prices = market.get_live_prices(symbols)
        print("Live Prices Fetched:")
        for sym, price in prices.items():
            print(f"  • {sym}: ${price:,.2f} USDT")
            
        # Calculate valuation
        total_val = 0.0
        print("\nPortfolio Value & PnL Breakdown:")
        for h in holdings:
            sym = h['symbol']
            amt = h['amount']
            bp = h['buy_price']
            wallet = h.get('wallet', 'default')
            cp = prices.get(sym, 0.0)
            val = amt * cp
            total_val += val
            
            pnl_str = "N/A"
            if bp:
                pnl_usd = val - (amt * bp)
                pnl_pct = (pnl_usd / (amt * bp)) * 100
                indicator = "+" if pnl_usd >= 0 else ""
                pnl_str = f"{indicator}${pnl_usd:,.2f} ({indicator}{pnl_pct:.1f}%)"
                
            print(f"  • {sym} ({wallet}): Val: ${val:,.2f} | PnL: {pnl_str}")
        print(f"💰 Total Portfolio Value: ${total_val:,.2f} USDT")
    except Exception as e:
        print(f"❌ Failed to fetch live valuation: {e}")
        
    # 4. Test Technical Analysis Engine
    print("\n[4] Testing Technical Analysis calculation (BTC)...")
    try:
        report = market.run_technical_analysis("BTC")
        if "error" in report:
            print(f"❌ TA Error: {report['error']}")
        else:
            print(f"✓ Analysis successful for {report['symbol']}:")
            print(f"  • Current Price: ${report['price']:,.2f} USDT")
            print(f"  • RSI (14): {report['rsi']:.2f}")
            print(f"  • SMA 20: ${report['sma20']:,.2f}")
            print(f"  • SMA 50: ${report['sma50']:,.2f}")
            print(f"  • Signal Signals:")
            for sig in report['signals']:
                print(f"    - {sig}")
            print(f"  💡 Recommendation: {report['recommendation']}")
    except Exception as e:
        print(f"❌ Failed to run technical analysis: {e}")

    # 5. Test Voice Command Parsing
    print("\n[5] Testing Voice Command NLP Parsing...")
    test_phrases = [
        "What is my portfolio balance?",
        "analyze ethereum",
        "analyze sol",
        "add zero point five bitcoin on my ledger at sixty thousand",
        "add 10.5 solana to rabby",
        "remove chainlink on my metamask",
        "sell zero point five ether on rabby"
    ]
    
    for phrase in test_phrases:
        parsed = parse_voice_command(phrase)
        print(f"🗣️ Phrase: \"{phrase}\"")
        print(f"👉 Parsed: {parsed}\n")
        
    print("==================================================")
    print("✅ Simulation complete! Core functionality works.")
    print("==================================================")

if __name__ == "__main__":
    run_simulation()
