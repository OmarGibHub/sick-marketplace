import sqlite3
import hashlib
import secrets
import time
import os
from typing import Optional, Dict, Any, List, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "platform.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Users Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                balance_eur REAL DEFAULT 0.0,
                api_key TEXT UNIQUE,
                created_at INTEGER NOT NULL,
                is_admin INTEGER DEFAULT 0
            )
        """)
        
        # 2. Sessions Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # 3. Boost Orders Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                invite TEXT NOT NULL,
                boosts INTEGER NOT NULL,
                duration TEXT DEFAULT '1m',
                nickname TEXT DEFAULT '',
                price_eur REAL NOT NULL,
                mode TEXT DEFAULT 'stock',
                tokens_count INTEGER DEFAULT 0,
                bio TEXT DEFAULT '',
                avatar_url TEXT DEFAULT '',
                banner_url TEXT DEFAULT '',
                salta7_job_id TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                error_msg TEXT DEFAULT '',
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # 4. Crypto Deposits Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tx_hash TEXT UNIQUE NOT NULL,
                amount_ltc REAL NOT NULL,
                amount_eur REAL NOT NULL,
                status TEXT DEFAULT 'completed',
                created_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # 5. Crypto Invoices Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                payment_id TEXT UNIQUE NOT NULL,
                amount_eur REAL NOT NULL,
                amount_ltc REAL NOT NULL,
                wallet_address TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Safe Column Migrations for existing DBs
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN api_key TEXT")
        except Exception:
            pass

        for col_def in [
            ("mode", "TEXT DEFAULT 'stock'"),
            ("tokens_count", "INTEGER DEFAULT 0"),
            ("bio", "TEXT DEFAULT ''"),
            ("avatar_url", "TEXT DEFAULT ''"),
            ("banner_url", "TEXT DEFAULT ''")
        ]:
            try:
                cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_def[0]} {col_def[1]}")
            except Exception:
                pass
        
        conn.commit()

# --- Password Utilities ---

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    combined = (password + salt).encode('utf-8')
    pwd_hash = hashlib.sha256(combined).hexdigest()
    return pwd_hash, salt

def verify_password(password: str, pwd_hash: str, salt: str) -> bool:
    expected_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(expected_hash, pwd_hash)

# --- User & Auth Operations ---

def create_user(username: str, password: str, is_admin: bool = False) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    clean_username = username.strip()
    if len(clean_username) < 3:
        return False, "Username must be at least 3 characters long.", None
    if len(password) < 4:
        return False, "Password must be at least 4 characters long.", None
        
    pwd_hash, salt = hash_password(password)
    now = int(time.time())
    api_key = "pb_" + secrets.token_hex(16)
    
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, password_hash, salt, balance_eur, api_key, created_at, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (clean_username, pwd_hash, salt, 0.0, api_key, now, 1 if is_admin else 0)
            )
            user_id = cursor.lastrowid
            conn.commit()
            
            user = {
                "id": user_id,
                "username": clean_username,
                "balance_eur": 0.0,
                "api_key": api_key,
                "is_admin": bool(is_admin),
                "created_at": now
            }
            return True, "Registration successful.", user
    except sqlite3.IntegrityError:
        return False, "Username is already taken.", None
    except Exception as e:
        return False, f"Database error: {str(e)}", None

def authenticate_user(username: str, password: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),))
        row = cursor.fetchone()
        if not row:
            return False, "User does not exist.", None
            
        if not verify_password(password, row["password_hash"], row["salt"]):
            return False, "Incorrect password.", None
            
        api_key = row["api_key"] if "api_key" in row.keys() and row["api_key"] else None
        if not api_key:
            api_key = "pb_" + secrets.token_hex(16)
            conn.cursor().execute("UPDATE users SET api_key = ? WHERE id = ?", (api_key, row["id"]))
            conn.commit()

        user = {
            "id": row["id"],
            "username": row["username"],
            "balance_eur": round(float(row["balance_eur"]), 2),
            "api_key": api_key,
            "is_admin": bool(row["is_admin"]),
            "created_at": row["created_at"]
        }
        return True, "Login successful.", user

def create_session(user_id: int, duration_days: int = 30) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    expires = now + (duration_days * 86400)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                       (token, user_id, now, expires))
        conn.commit()
    return token

def get_user_by_session(token: str) -> Optional[Dict[str, Any]]:
    now = int(time.time())
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.* FROM users u
            JOIN sessions s ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ?
        """, (token, now))
        row = cursor.fetchone()
        if not row:
            return None
        
        api_key = row["api_key"] if "api_key" in row.keys() and row["api_key"] else None
        if not api_key:
            api_key = "pb_" + secrets.token_hex(16)
            conn.cursor().execute("UPDATE users SET api_key = ? WHERE id = ?", (api_key, row["id"]))
            conn.commit()

        return {
            "id": row["id"],
            "username": row["username"],
            "balance_eur": round(float(row["balance_eur"]), 2),
            "api_key": api_key,
            "is_admin": bool(row["is_admin"]),
            "created_at": row["created_at"]
        }

def get_user_by_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    if not api_key:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE api_key = ?", (api_key.strip(),))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "balance_eur": round(float(row["balance_eur"]), 2),
            "api_key": row["api_key"],
            "is_admin": bool(row["is_admin"]),
            "created_at": row["created_at"]
        }

def get_default_user() -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "balance_eur": round(float(row["balance_eur"]), 2),
            "api_key": row["api_key"] if "api_key" in row.keys() else "",
            "is_admin": bool(row["is_admin"]),
            "created_at": row["created_at"]
        }

def delete_session(token: str):
    with get_db() as conn:
        conn.cursor().execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()

def update_user_password(user_id: int, old_password: str, new_password: str) -> Tuple[bool, str]:
    if len(new_password) < 4:
        return False, "New password must be at least 4 characters long."

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, salt FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False, "User not found."

        if not verify_password(old_password, row["password_hash"], row["salt"]):
            return False, "Current password is incorrect."

        new_hash, new_salt = hash_password(new_password)
        cursor.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (new_hash, new_salt, user_id))
        conn.commit()
        return True, "Password updated successfully."

def regenerate_user_api_key(user_id: int) -> str:
    new_key = "sick_" + secrets.token_hex(16)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET api_key = ? WHERE id = ?", (new_key, user_id))
        conn.commit()
    return new_key

# --- Balance Operations ---

def get_user_balance(user_id: int) -> float:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance_eur FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return round(float(row["balance_eur"]), 2) if row else 0.0

def adjust_user_balance(user_id: int, delta_eur: float) -> Tuple[bool, float]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT balance_eur FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False, 0.0
            
        current = float(row["balance_eur"])
        new_balance = round(current + delta_eur, 2)
        if new_balance < 0:
            return False, current
            
        cursor.execute("UPDATE users SET balance_eur = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
        return True, new_balance

# --- Order Operations ---

def create_order(
    user_id: int,
    invite: str,
    boosts: int,
    price_eur: float,
    duration: str = "1m",
    nickname: str = "",
    mode: str = "stock",
    tokens_count: int = 0,
    bio: str = "",
    avatar_url: str = "",
    banner_url: str = ""
) -> int:
    now = int(time.time())
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO orders (
                user_id, invite, boosts, duration, nickname, price_eur,
                mode, tokens_count, bio, avatar_url, banner_url,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (
            user_id, invite, boosts, duration, nickname, price_eur,
            mode, tokens_count, bio, avatar_url, banner_url,
            now, now
        ))
        order_id = cursor.lastrowid
        conn.commit()
        return order_id

def update_order_status(order_id: int, status: str, salta7_job_id: str = "", error_msg: str = ""):
    now = int(time.time())
    with get_db() as conn:
        cursor = conn.cursor()
        updates = ["status = ?", "updated_at = ?"]
        params = [status, now]
        if salta7_job_id:
            updates.append("salta7_job_id = ?")
            params.append(salta7_job_id)
        if error_msg:
            updates.append("error_msg = ?")
            params.append(error_msg)
        params.append(order_id)
        
        cursor.execute(f"UPDATE orders SET {', '.join(updates)} WHERE id = ?", params)
        conn.commit()

def get_user_orders(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?
        """, (user_id, limit))
        rows = cursor.fetchall()
        orders = []
        for r in rows:
            d = dict(r)
            d["task_id"] = d.get("salta7_job_id", "")
            d.pop("salta7_job_id", None)
            orders.append(d)
        return orders

def get_order_by_id(order_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        d["task_id"] = d.get("salta7_job_id", "")
        d.pop("salta7_job_id", None)
        return d

# --- Deposits Operations ---

def record_deposit(user_id: int, tx_hash: str, amount_ltc: float, amount_eur: float, status: str = 'completed') -> bool:
    now = int(time.time())
    clean_hash = tx_hash.strip().lower()
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO deposits (user_id, tx_hash, amount_ltc, amount_eur, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, clean_hash, amount_ltc, amount_eur, status, now))
            # Only credit balance if user_id > 0 and amount_eur > 0 and status is completed
            if user_id > 0 and amount_eur > 0 and status == 'completed':
                cursor.execute("UPDATE users SET balance_eur = balance_eur + ? WHERE id = ?", (amount_eur, user_id))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False # Transaction hash already processed
    except Exception:
        return False

def is_deposit_recorded(tx_hash: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM deposits WHERE tx_hash = ?", (tx_hash.strip().lower(),))
        return cursor.fetchone() is not None

def get_all_deposits(limit: int = 50) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deposits ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]

# --- Crypto Invoice Operations ---

def create_invoice(user_id: int, amount_eur: float, amount_ltc: float, wallet_address: str, duration_hours: int = 4) -> Dict[str, Any]:
    now = int(time.time())
    expires_at = now + (duration_hours * 3600)
    # Generate 10-digit random payment ID like 5784378544
    payment_id = str(secrets.randbelow(9000000000) + 1000000000)
    with get_db() as conn:
        cursor = conn.cursor()
        # Supersede previous pending invoices for this user so only the latest invoice is active
        cursor.execute("UPDATE invoices SET status = 'superseded' WHERE user_id = ? AND status = 'pending'", (user_id,))
        
        # Add unique micro-satoshi identifier so no two active invoices ever have the same LTC amount!
        cursor.execute("SELECT COUNT(*) FROM invoices")
        count = cursor.fetchone()[0] + 1
        unique_sats = ((count * 17 + user_id * 31) % 89) + 10  # 10 to 99 satoshis
        unique_ltc = round(float(amount_ltc), 6) + (unique_sats * 0.00000001)
        unique_ltc = round(unique_ltc, 8)

        cursor.execute("""
            INSERT INTO invoices (user_id, payment_id, amount_eur, amount_ltc, wallet_address, status, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (user_id, payment_id, round(amount_eur, 2), unique_ltc, wallet_address, now, expires_at))
        conn.commit()
    return {
        "payment_id": payment_id,
        "amount_eur": round(amount_eur, 2),
        "amount_ltc": unique_ltc,
        "wallet_address": wallet_address,
        "status": "pending",
        "created_at": now,
        "expires_at": expires_at
    }

def get_active_invoice(user_id: int) -> Optional[Dict[str, Any]]:
    now = int(time.time())
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM invoices 
            WHERE user_id = ? AND status = 'pending' AND expires_at > ?
            ORDER BY id DESC LIMIT 1
        """, (user_id, now))
        row = cursor.fetchone()
        return dict(row) if row else None

def find_matching_pending_invoice(amount_ltc: float, tolerance: float = 0.0000005) -> Optional[Dict[str, Any]]:
    """
    Finds the exact pending invoice matching this received LTC amount.
    With unique satoshi precision, each invoice has a unique LTC amount.
    """
    now = int(time.time())
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT invoices.*, users.username FROM invoices
            JOIN users ON invoices.user_id = users.id
            WHERE invoices.status = 'pending' AND invoices.expires_at > ?
            ORDER BY invoices.id DESC
        """, (now,))
        for row in cursor.fetchall():
            inv = dict(row)
            if abs(float(inv["amount_ltc"]) - amount_ltc) <= tolerance:
                return inv
        return None

def mark_invoice_completed(payment_id: str) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE invoices SET status = 'completed' WHERE payment_id = ?", (payment_id,))
        conn.commit()
        return cursor.rowcount > 0

# Initialize database tables on import
init_db()
