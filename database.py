import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = "portfolio.db"

def get_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            weekly_report_enabled INTEGER DEFAULT 1,
            weekly_report_time TEXT DEFAULT 'Sun 18:00',
            last_report_sent TEXT,
            created_at TEXT
        )
    """)
    
    # Check if 'portfolio' table already exists and if it has 'wallet' column
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        # Check if 'wallet' column exists
        cursor.execute("PRAGMA table_info(portfolio)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'wallet' not in columns:
            # We need to migrate!
            logger.info("Migrating portfolio table schema to support wallets...")
            try:
                # Rename old table
                cursor.execute("ALTER TABLE portfolio RENAME TO portfolio_old")
                
                # Create new table with updated constraints and columns
                cursor.execute("""
                    CREATE TABLE portfolio (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER,
                        symbol TEXT NOT NULL,
                        amount REAL NOT NULL,
                        buy_price REAL,
                        wallet TEXT NOT NULL DEFAULT 'default',
                        updated_at TEXT,
                        FOREIGN KEY (chat_id) REFERENCES users(chat_id),
                        UNIQUE(chat_id, wallet, symbol)
                    )
                """)
                
                # Copy data
                cursor.execute("""
                    INSERT INTO portfolio (chat_id, symbol, amount, buy_price, wallet, updated_at)
                    SELECT chat_id, symbol, amount, buy_price, 'default', updated_at FROM portfolio_old
                """)
                
                # Drop old table
                cursor.execute("DROP TABLE portfolio_old")
                conn.commit()
                logger.info("Migration successful.")
            except Exception as e:
                conn.rollback()
                logger.error(f"Migration failed: {e}")
                raise e
    else:
        # Create new portfolio table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                symbol TEXT NOT NULL,
                amount REAL NOT NULL,
                buy_price REAL,
                wallet TEXT NOT NULL DEFAULT 'default',
                updated_at TEXT,
                FOREIGN KEY (chat_id) REFERENCES users(chat_id),
                UNIQUE(chat_id, wallet, symbol)
            )
        """)
        conn.commit()
        
    conn.close()
    logger.info("Database initialized successfully.")

def register_user(chat_id: int):
    """Registers a user if they are not already in the database."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT chat_id FROM users WHERE chat_id = ?", (chat_id,))
        if not cursor.fetchone():
            cursor.execute(
                "INSERT INTO users (chat_id, created_at) VALUES (?, ?)",
                (chat_id, datetime.utcnow().isoformat())
            )
            conn.commit()
            logger.info(f"Registered new user: {chat_id}")
    except Exception as e:
        logger.error(f"Error registering user {chat_id}: {e}")
    finally:
        conn.close()

def add_holding(chat_id: int, symbol: str, amount: float, buy_price: float = None, wallet: str = 'default'):
    """Adds a crypto holding or updates it if it already exists in the given wallet."""
    symbol = symbol.upper().strip()
    wallet = wallet.lower().strip() if wallet else 'default'
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # First ensure the user exists
        register_user(chat_id)
        
        # Check if holding exists in the specific wallet
        cursor.execute("SELECT amount, buy_price FROM portfolio WHERE chat_id = ? AND symbol = ? AND wallet = ?", (chat_id, symbol, wallet))
        row = cursor.fetchone()
        
        now_str = datetime.utcnow().isoformat()
        if row:
            # Update existing holding (calculate average buy price if buy_price is provided, otherwise keep old)
            old_amount = row['amount']
            old_buy_price = row['buy_price']
            
            new_amount = old_amount + amount
            if new_amount < 0:
                new_amount = 0.0
                
            new_buy_price = old_buy_price
            if buy_price is not None and buy_price > 0:
                # If we are adding more coins and have a new buy price, we calculate weighted average buy price
                if amount > 0 and old_buy_price is not None:
                    new_buy_price = ((old_amount * old_buy_price) + (amount * buy_price)) / new_amount
                else:
                    new_buy_price = buy_price
            
            cursor.execute("""
                UPDATE portfolio 
                SET amount = ?, buy_price = ?, updated_at = ? 
                WHERE chat_id = ? AND symbol = ? AND wallet = ?
            """, (new_amount, new_buy_price, now_str, chat_id, symbol, wallet))
        else:
            # Insert new holding
            if amount > 0:
                cursor.execute("""
                    INSERT INTO portfolio (chat_id, symbol, amount, buy_price, wallet, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (chat_id, symbol, amount, buy_price, wallet, now_str))
                
        conn.commit()
        logger.info(f"Updated holding for user {chat_id} in {wallet}: {symbol} amount={amount}")
    except Exception as e:
        logger.error(f"Error adding holding for {chat_id} in {wallet}: {e}")
        raise e
    finally:
        conn.close()

def remove_holding(chat_id: int, symbol: str, amount: float = None, wallet: str = 'default'):
    """
    Removes a holding entirely or reduces its amount from the given wallet.
    If amount is None, removes the asset entirely from that wallet.
    """
    symbol = symbol.upper().strip()
    wallet = wallet.lower().strip() if wallet else 'default'
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if amount is None:
            cursor.execute("DELETE FROM portfolio WHERE chat_id = ? AND symbol = ? AND wallet = ?", (chat_id, symbol, wallet))
        else:
            cursor.execute("SELECT amount FROM portfolio WHERE chat_id = ? AND symbol = ? AND wallet = ?", (chat_id, symbol, wallet))
            row = cursor.fetchone()
            if row:
                current_amount = row['amount']
                new_amount = current_amount - amount
                if new_amount <= 0:
                    cursor.execute("DELETE FROM portfolio WHERE chat_id = ? AND symbol = ? AND wallet = ?", (chat_id, symbol, wallet))
                else:
                    cursor.execute("""
                        UPDATE portfolio 
                        SET amount = ?, updated_at = ? 
                        WHERE chat_id = ? AND symbol = ? AND wallet = ?
                    """, (new_amount, datetime.utcnow().isoformat(), chat_id, symbol, wallet))
        conn.commit()
        logger.info(f"Removed holding for user {chat_id} in {wallet}: {symbol} amount={amount}")
    except Exception as e:
        logger.error(f"Error removing holding for {chat_id} in {wallet}: {e}")
        raise e
    finally:
        conn.close()

def get_portfolio(chat_id: int):
    """Returns all crypto holdings for a user with their associated wallets."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT symbol, amount, buy_price, wallet FROM portfolio WHERE chat_id = ? AND amount > 0", (chat_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching portfolio for {chat_id}: {e}")
        return []
    finally:
        conn.close()

def update_weekly_schedule(chat_id: int, enabled: bool, time_str: str = "Sun 18:00"):
    """Updates user weekly report preferences."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        register_user(chat_id)
        cursor.execute("""
            UPDATE users 
            SET weekly_report_enabled = ?, weekly_report_time = ? 
            WHERE chat_id = ?
        """, (1 if enabled else 0, time_str, chat_id))
        conn.commit()
        logger.info(f"Updated schedule for user {chat_id}: enabled={enabled}, time={time_str}")
    except Exception as e:
        logger.error(f"Error updating schedule for {chat_id}: {e}")
        raise e
    finally:
        conn.close()

def get_weekly_schedule(chat_id: int):
    """Gets user weekly report settings."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT weekly_report_enabled, weekly_report_time FROM users WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return {"weekly_report_enabled": 1, "weekly_report_time": "Sun 18:00"}
    except Exception as e:
        logger.error(f"Error fetching schedule for {chat_id}: {e}")
        return {"weekly_report_enabled": 1, "weekly_report_time": "Sun 18:00"}
    finally:
        conn.close()

def get_all_users_for_weekly():
    """Gets all registered users who have weekly reports enabled."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT chat_id, weekly_report_time, last_report_sent FROM users WHERE weekly_report_enabled = 1")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error fetching all weekly users: {e}")
        return []
    finally:
        conn.close()

def update_last_report_sent(chat_id: int, date_str: str):
    """Updates the date when the weekly report was last sent to the user."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET last_report_sent = ? WHERE chat_id = ?", (date_str, chat_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating last report sent: {e}")
    finally:
        conn.close()
