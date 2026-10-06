"""
Veritabanı işleri: bağlantı açmak ve tabloları oluşturmak.
"""

import sqlite3

from piyasa.ayarlar import VERITABANI

DB_PATH = VERITABANI


def get_connection():
    """Veritabanına bağlanır."""
    # Toplayıcı yazarken site okuyabilsin diye kilit beklemesi uzun
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# Tabloya ilk sürümden sonra eklenen sütunlar. Eski veritabanlarında
# eksikse init_db() bunları ekler.
SONRADAN_EKLENEN_SUTUNLAR = [
    ("share_count", "REAL"),      # işlem gören adet
    ("share_price", "REAL"),      # birim fiyat
    ("security_name", "TEXT"),    # menkul kıymetin adı
    ("suspect", "INTEGER"),       # 1 ise şüpheli, sitede gösterilmez
    ("person_slug", "TEXT"),      # kişi sayfasının adresi
]


def sutunlari_tamamla(conn, tablo, sutunlar):
    """Tabloda olmayan sütunları ekler."""
    mevcut = {s["name"] for s in conn.execute(f"PRAGMA table_info({tablo})")}
    for ad, tur in sutunlar:
        if ad not in mevcut:
            conn.execute(f"ALTER TABLE {tablo} ADD COLUMN {ad} {tur}")


def init_db():
    """Tablolar yoksa oluşturur, eksik sütunları tamamlar."""
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
            fetched_at       TEXT,

            share_count     REAL,
            share_price     REAL,
            security_name   TEXT,
            suspect         INTEGER,
            person_slug     TEXT
        )
    """)
    sutunlari_tamamla(conn, "transactions", SONRADAN_EKLENEN_SUTUNLAR)

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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person_slug ON transactions(person_slug)")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_fon ON holdings(fon_slug)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_donem ON holdings(donem)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_cusip ON holdings(cusip)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_ticker ON holdings(ticker)")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Veritabanı hazır: {DB_PATH}")