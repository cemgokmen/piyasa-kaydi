"""
Veritabanı işleri: bağlantı açmak ve tabloları oluşturmak.
"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "kayitlar.db"


def get_connection():
    """Veritabanına bağlanır."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Tablolar yoksa oluşturur. Varsa hiçbir şey yapmaz."""
    conn = get_connection()

    # --- Yönetici ve kongre işlemleri (Form 4) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id       TEXT NOT NULL UNIQUE,
            source          TEXT NOT NULL,

            person          TEXT NOT NULL,
            chamber         TEXT,
            state           TEXT,
            party           TEXT,
            committee       TEXT,
            job_title       TEXT,
            company         TEXT,

            ticker          TEXT NOT NULL,
            asset_name      TEXT,
            action          TEXT NOT NULL,
            amount_min      INTEGER,
            amount_max      INTEGER,
            currency        TEXT NOT NULL DEFAULT 'USD',

            transaction_date TEXT NOT NULL,
            disclosed_date   TEXT NOT NULL,
            source_url       TEXT,
            fetched_at       TEXT
        )
    """)

    # --- Fon ve banka pozisyonları (13F) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id       TEXT NOT NULL UNIQUE,

            fon_adi         TEXT NOT NULL,
            fon_slug        TEXT NOT NULL,
            cik             TEXT NOT NULL,

            donem           TEXT NOT NULL,
            bildirim_tarihi TEXT NOT NULL,

            sirket_adi      TEXT NOT NULL,
            cusip           TEXT NOT NULL,
            ticker          TEXT,

            deger           INTEGER,
            adet            REAL,

            source_url      TEXT,
            fetched_at      TEXT
        )
    """)

    # --- Tamamlanan indirme günleri ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fetched_days (
            gun          TEXT PRIMARY KEY,
            kayit_sayisi INTEGER,
            biten_zaman  TEXT
        )
    """)

    # --- İndeksler ---
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON transactions(ticker)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person ON transactions(person)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_disclosed ON transactions(disclosed_date)")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_fon ON holdings(fon_slug)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_donem ON holdings(donem)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_cusip ON holdings(cusip)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_ticker ON holdings(ticker)")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Veritabanı hazır: {DB_PATH}")