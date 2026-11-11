import os
import sqlite3
import json
import uuid
import hashlib
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

DB_PATH = os.environ.get("CRYPTOLAB_DB", "cryptolab.db")

def load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k_clean = k.strip()
                        if k_clean not in os.environ:
                            os.environ[k_clean] = v.strip()
        except Exception:
            pass

load_env_file()

def get_utc_now_iso():
    return datetime.now(timezone.utc).isoformat()

def hash_admin_password(password: str) -> str:
    # SHA-256 with cryptographic salt to prevent rainbow table attacks
    salt = "CryptoLab_Audit_Salt_2026_BanRep_COT"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def get_admin_credentials():
    load_env_file()
    user = os.environ.get("CRYPTOLAB_ADMIN_USER", "admin_forense").strip()
    pwd = os.environ.get("CRYPTOLAB_ADMIN_PASSWORD", "SecForensik#2026_xK9mQ7vL").strip()
    return user, pwd

def get_db_connection(db_path=None):
    path = db_path or os.environ.get("CRYPTOLAB_DB", "cryptolab.db")
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db(db_path=None):
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # Rooms table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN', -- 'OPEN', 'CLOSED'
        initial_bank_balance_cop REAL NOT NULL DEFAULT 50000000.0,
        created_at TEXT NOT NULL,
        closed_at TEXT
    );
    """)

    # Admin credentials & sessions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        session_token TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Participants table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS participants (
        id TEXT PRIMARY KEY,
        room_code TEXT NOT NULL,
        alias TEXT NOT NULL,
        alias_normalized TEXT NOT NULL,
        session_token TEXT NOT NULL,
        bank_balance_cop REAL NOT NULL DEFAULT 0.0,
        wallet_cop REAL NOT NULL DEFAULT 0.0,
        wallet_btc REAL NOT NULL DEFAULT 0.0,
        wallet_eth REAL NOT NULL DEFAULT 0.0,
        wallet_usdt REAL NOT NULL DEFAULT 0.0,
        wallet_sol REAL NOT NULL DEFAULT 0.0,
        created_at TEXT NOT NULL,
        last_active_at TEXT NOT NULL,
        FOREIGN KEY (room_code) REFERENCES rooms (code) ON DELETE CASCADE,
        UNIQUE(room_code, alias_normalized)
    );
    """)

    # Transactions ledger
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id TEXT PRIMARY KEY,
        room_code TEXT NOT NULL,
        tx_type TEXT NOT NULL, 
        -- 'DEPOSIT_BANK_TO_WALLET', 'WITHDRAW_WALLET_TO_BANK', 
        -- 'BUY_CRYPTO', 'SELL_CRYPTO', 
        -- 'TRANSFER_INTERNAL', 'TRANSFER_EXTERNAL'
        sender_alias TEXT,
        receiver_alias TEXT,
        is_external INTEGER NOT NULL DEFAULT 0,
        asset TEXT NOT NULL, -- 'COP', 'BTC', 'ETH', 'USDT', 'SOL'
        amount REAL NOT NULL,
        fee_cop REAL NOT NULL DEFAULT 0.0,
        unit_price_cop REAL,
        gross_amount_cop REAL,
        net_amount_cop REAL,
        tx_hash TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'CONFIRMED',
        metadata TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (room_code) REFERENCES rooms (code) ON DELETE CASCADE
    );
    """)

    # Indexes for rapid forensic trace & lookups
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_room ON transactions(room_code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_sender ON transactions(room_code, sender_alias);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_receiver ON transactions(room_code, receiver_alias);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_created ON transactions(created_at);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_part_session ON participants(session_token);")

    # Cache table for market prices
    cur.execute("""
    CREATE TABLE IF NOT EXISTS price_cache (
        asset TEXT PRIMARY KEY,
        price_cop REAL NOT NULL,
        change_24h REAL NOT NULL DEFAULT 0.0,
        last_updated TEXT NOT NULL,
        source TEXT NOT NULL
    );
    """)

    # Audit log for administrative actions
    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin_audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        details TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Configure secure admin credentials from environment/.env
    admin_user, admin_pass = get_admin_credentials()
    pass_hash = hash_admin_password(admin_pass)

    # Purge old insecure or obsolete admin credentials
    cur.execute("DELETE FROM admins WHERE username = 'admin' OR username != ?;", (admin_user,))

    # Insert or update configured secure administrator
    cur.execute("SELECT username FROM admins WHERE username = ?", (admin_user,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
            (admin_user, pass_hash, get_utc_now_iso())
        )
    else:
        cur.execute(
            "UPDATE admins SET password_hash = ? WHERE username = ?",
            (pass_hash, admin_user)
        )

    # Seed baseline prices if empty (conforme a TRM oficial $3.269,88)
    cur.execute("SELECT COUNT(*) as count FROM price_cache")
    if cur.fetchone()["count"] == 0:
        now_iso = get_utc_now_iso()
        seeds = [
            ("BTC", 244184510.0, 1.25, now_iso, "Sistema Base (TRM $3.269,88 BanRep)"),
            ("ETH", 6928548.0, -0.45, now_iso, "Sistema Base (TRM $3.269,88 BanRep)"),
            ("USDT", 3269.88, 0.05, now_iso, "Sistema Base (TRM $3.269,88 BanRep)"),
            ("SOL", 281013.0, 3.10, now_iso, "Sistema Base (TRM $3.269,88 BanRep)")
        ]
        cur.executemany(
            "INSERT OR REPLACE INTO price_cache (asset, price_cop, change_24h, last_updated, source) VALUES (?, ?, ?, ?, ?)",
            seeds
        )

    conn.commit()
    conn.close()

def generate_tx_hash(tx_id: str, sender: str, receiver: str, asset: str, amount: float, timestamp: str) -> str:
    raw = f"{tx_id}:{sender}:{receiver}:{asset}:{amount}:{timestamp}:{uuid.uuid4().hex[:8]}"
    return "0x" + hashlib.sha256(raw.encode()).hexdigest()

def round_amount(val: float, decimals: int = 8) -> float:
    d = Decimal(str(val))
    return float(d.quantize(Decimal('1e-' + str(decimals)), rounding=ROUND_HALF_UP))
