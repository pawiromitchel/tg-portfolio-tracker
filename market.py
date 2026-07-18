import ccxt
import pandas as pd
import numpy as np
import logging
import re
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# Initialize the exchange client (Binance by default for public data)
exchange = ccxt.binance({
    'timeout': 15000,
    'enableRateLimit': True,
})

def get_live_price(symbol: str) -> float:
    """
    Fetches the current price of a cryptocurrency symbol in USDT.
    Accepts symbols like 'BTC', 'ETH', 'BTC/USDT'.
    """
    symbol = symbol.upper().strip()
    
    # 1. Match standard stablecoins or their Aave counterparts (e.g. USDT, USDC, aUSDC, aUSDT, DAI, BUSD)
    if re.match(r'^(A?USDT|A?USDC|A?DAI|BUSD|USD)$', symbol):
        return 1.0
        
    # 2. Match cbBTC (Coinbase Wrapped BTC) and map it to standard BTC price
    if symbol == 'CBBTC':
        return get_live_price('BTC')
        
    # 3. Match wstETH (Wrapped staked ETH) and add fallback to standard ETH * 1.16
    if symbol == 'WSTETH':
        try:
            pair = "WSTETH/USDT"
            ticker = exchange.fetch_ticker(pair)
            return float(ticker['last'])
        except Exception:
            return get_live_price('ETH') * 1.16
            
    # 4. Handle Aave interest-bearing volatile assets (e.g. AETH, ACBBTC, AWSTETH) by querying underlying
    if symbol.startswith('A') and len(symbol) > 3 and symbol not in ['ADA', 'AVAX', 'APT', 'APE']:
        underlying = symbol[1:]
        try:
            return get_live_price(underlying)
        except Exception:
            pass
        
    pair = symbol if '/' in symbol else f"{symbol}/USDT"
    try:
        ticker = exchange.fetch_ticker(pair)
        return float(ticker['last'])
    except Exception as e:
        logger.error(f"Error fetching live price for {pair} on Binance: {e}")
        # Try a fallback exchange (e.g. Coinbase) if Binance fails
        try:
            coinbase = ccxt.coinbase()
            # Coinbase pair syntax might be different (BTC/USD)
            cb_pair = pair.replace('USDT', 'USD')
            ticker = coinbase.fetch_ticker(cb_pair)
            return float(ticker['last'])
        except Exception as e2:
            logger.error(f"Fallback fetch for {pair} on Coinbase also failed: {e2}")
            raise ValueError(f"Could not fetch price for symbol: {symbol}")

def get_live_prices(symbols: List[str]) -> Dict[str, float]:
    """
    Fetches current prices for a list of symbols.
    Returns a dictionary of {symbol: price}.
    """
    prices = {}
    for s in set(symbols):
        try:
            prices[s] = get_live_price(s)
        except Exception:
            prices[s] = 0.0
    return prices

def resolve_ta_symbol(symbol: str) -> str:
    """Resolves wrapped/yield tokens (e.g. aETH, acbBTC, cbBTC, wstETH) to standard underlying volatile assets for TA charting."""
    symbol = symbol.upper().strip()
    if symbol == 'CBBTC':
        return 'BTC'
    if symbol == 'WSTETH':
        return 'ETH'
    if symbol.startswith('A') and len(symbol) > 3 and symbol not in ['ADA', 'AVAX', 'APT', 'APE']:
        underlying = symbol[1:]
        return resolve_ta_symbol(underlying)
    return symbol

def fetch_ohlcv(symbol: str, timeframe: str = '1d', limit: int = 100) -> pd.DataFrame:
    """
    Fetches historical candle data (OHLCV) and returns a pandas DataFrame.
    """
    symbol = resolve_ta_symbol(symbol)
    pair = symbol if '/' in symbol else f"{symbol}/USDT"
    try:
        ohlcv = exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        logger.error(f"Error fetching historical data for {pair}: {e}")
        raise ValueError(f"Could not fetch historical data for {symbol}")

def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index (RSI)."""
    close = df['close']
    delta = close.diff()
    
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # Wilder's smoothing/EMA method
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    # Avoid division by zero
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)  # Default neutral value if calculation is empty

def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates MACD line, signal line, and histogram."""
    close = df['close']
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    macd_hist = macd_line - signal_line
    
    return macd_line, signal_line, macd_hist

def run_technical_analysis(symbol: str) -> Dict[str, Any]:
    """
    Computes indicators (RSI, MACD, SMAs) and returns a technical analysis report.
    """
    try:
        df = fetch_ohlcv(symbol, timeframe='1d', limit=100)
    except Exception as e:
        return {"error": str(e)}
        
    if df.empty or len(df) < 50:
        return {"error": f"Not enough historical data to analyze {symbol}."}
        
    # Calculate indicators
    df['rsi'] = calculate_rsi(df)
    macd_line, signal_line, macd_hist = calculate_macd(df)
    df['macd'] = macd_line
    df['macd_signal'] = signal_line
    df['macd_hist'] = macd_hist
    
    # Moving Averages
    df['sma20'] = df['close'].rolling(window=20).mean()
    df['sma50'] = df['close'].rolling(window=50).mean()
    
    # Get last row values
    last_row = df.iloc[-1]
    prev_row = df.iloc[-2]
    
    close_price = float(last_row['close'])
    rsi_val = float(last_row['rsi'])
    macd_val = float(last_row['macd'])
    macd_sig = float(last_row['macd_signal'])
    macd_hist_val = float(last_row['macd_hist'])
    
    sma20_val = float(last_row['sma20'])
    sma50_val = float(last_row['sma50'])
    
    # Generate rule-based signals
    signals = []
    score = 0  # positive = buy, negative = sell
    
    # RSI Signals
    if rsi_val < 30:
        signals.append("RSI shows asset is heavily Oversold (Bullish buy signal).")
        score += 2
    elif rsi_val > 70:
        signals.append("RSI shows asset is heavily Overbought (Bearish sell signal).")
        score -= 2
    else:
        signals.append(f"RSI is neutral at {rsi_val:.1f}.")
        
    # MACD Crossover Signals
    # Bullish crossover: MACD crossed above Signal line recently
    if last_row['macd'] > last_row['macd_signal'] and prev_row['macd'] <= prev_row['macd_signal']:
        signals.append("MACD Bullish Crossover (Line crossed above Signal line).")
        score += 2
    # Bearish crossover: MACD crossed below Signal line recently
    elif last_row['macd'] < last_row['macd_signal'] and prev_row['macd'] >= prev_row['macd_signal']:
        signals.append("MACD Bearish Crossover (Line crossed below Signal line).")
        score -= 2
    else:
        # Trend indicators based on absolute MACD values
        if macd_hist_val > 0:
            signals.append("MACD histogram is positive (bullish momentum).")
            score += 0.5
        else:
            signals.append("MACD histogram is negative (bearish momentum).")
            score -= 0.5
            
    # Moving Average Trend Signals
    if close_price > sma20_val > sma50_val:
        signals.append("Price is in a strong uptrend (Price > SMA20 > SMA50).")
        score += 1.5
    elif close_price < sma20_val < sma50_val:
        signals.append("Price is in a strong downtrend (Price < SMA20 < SMA50).")
        score -= 1.5
    elif close_price > sma20_val:
        signals.append("Price is above SMA20 (Short-term bullish).")
        score += 0.5
    else:
        signals.append("Price is below SMA20 (Short-term bearish).")
        score -= 0.5

    # Determine overall suggestion
    if score >= 2.0:
        recommendation = "🟢 STRONG BUY"
    elif 0.5 <= score < 2.0:
        recommendation = "🟢 BUY / ACCUMULATE"
    elif -0.5 < score < 0.5:
        recommendation = "🟡 HOLD / NEUTRAL"
    elif -2.0 < score <= -0.5:
        recommendation = "🔴 WEAK SELL / REDUCE"
    else:
        recommendation = "🔴 STRONG SELL"
        
    return {
        "symbol": symbol,
        "price": close_price,
        "rsi": rsi_val,
        "macd": macd_val,
        "macd_signal": macd_sig,
        "sma20": sma20_val,
        "sma50": sma50_val,
        "signals": signals,
        "recommendation": recommendation,
        "score": score
    }
