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

    # --- 13F CUSIP → hisse kodu eşlemesi (OpenFIGI) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cusip_ticker (
            cusip       TEXT PRIMARY KEY,
            ticker      TEXT,
            kaynak      TEXT,
            guncelleme  TEXT
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

    # --- Emtialar: CFTC fon konumları, EIA stokları, FRED faizleri ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cot (
            emtia          TEXT NOT NULL,
            tarih          TEXT NOT NULL,
            acik_pozisyon  INTEGER,
            fon_uzun       INTEGER,
            fon_kisa       INTEGER,
            uretici_uzun   INTEGER,
            uretici_kisa   INTEGER,
            PRIMARY KEY (emtia, tarih)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eia_stok (
            seri   TEXT NOT NULL,
            tarih  TEXT NOT NULL,
            deger  REAL,
            PRIMARY KEY (seri, tarih)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS makro (
            seri   TEXT NOT NULL,
            tarih  TEXT NOT NULL,
            deger  REAL,
            PRIMARY KEY (seri, tarih)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emtia_guncelleme (
            anahtar  TEXT PRIMARY KEY,
            zaman    TEXT
        )
    """)

    # --- Analiz: fiyat geçmişi, sektörler, Meclis komiteleri ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fiyat_gecmisi (
            ticker   TEXT NOT NULL,
            tarih    TEXT NOT NULL,
            kapanis  REAL,
            PRIMARY KEY (ticker, tarih)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sirket (
            ticker        TEXT PRIMARY KEY,
            cik           INTEGER,
            sic           INTEGER,
            sic_aciklama  TEXT,
            sektor        TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sirket_profili (
            ticker      TEXT PRIMARY KEY,
            ozet        TEXT,
            ozet_en     TEXT,
            sektor      TEXT,
            endustri    TEXT,
            calisan     INTEGER,
            merkez      TEXT,
            site        TEXT,
            guncelleme  TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uye (
            bioguide  TEXT PRIMARY KEY,
            ad        TEXT,
            slug      TEXT,
            parti     TEXT,
            bolge     TEXT,
            gorev     TEXT
        )
    """)
    sutunlari_tamamla(conn, "uye", [("gorev", "TEXT")])
    conn.execute("""
        CREATE TABLE IF NOT EXISTS komite_uyeligi (
            bioguide  TEXT NOT NULL,
            komite    TEXT NOT NULL,
            unvan     TEXT,
            PRIMARY KEY (bioguide, komite)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS islem_getirisi (
            islem_id  INTEGER NOT NULL,
            baz       TEXT NOT NULL,      -- 'islem' ya da 'bildirim' tarihinden
            ufuk      TEXT NOT NULL,      -- '30', '90', '180' gün ya da 'bugun'
            getiri    REAL,               -- hissenin getirisi
            endeks    REAL,               -- aynı dönemde S&P 500 (SPY)
            PRIMARY KEY (islem_id, baz, ufuk)
        )
    """)

    # --- Yürütme (Başkan, Başkan Yardımcısı): OGE mali durum bildirimleri ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS yurutme_bildirimi (
            adres     TEXT PRIMARY KEY,   -- belgenin PDF adresi
            kisi      TEXT NOT NULL,      -- adres dostu ad: donald-j-trump
            tur       TEXT NOT NULL,      -- islem | yillik | ayrilis
            baslik    TEXT,
            tarih     TEXT                -- OGE'nin belgeyi yayımladığı gün
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS yurutme_rapor (
            adres    TEXT PRIMARY KEY,
            kisi     TEXT NOT NULL,
            sayfa    INTEGER,
            islenme  TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS yurutme_varlik (
            kisi     TEXT NOT NULL,
            hesap    TEXT,
            ad       TEXT,
            ticker   TEXT,               -- eşlenemediyse boş
            alt      INTEGER,
            ust      INTEGER,
            eslesme  TEXT,               -- tam | onek | yakin | kod | bitisik | elendi | tahvil_hesabi
            rapor    TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS yurutme_islem (
            kisi     TEXT NOT NULL,
            hesap    TEXT,
            ad       TEXT,
            ticker   TEXT,
            islem    TEXT,               -- buy | sell
            tarih    TEXT,
            alt      INTEGER,
            ust      INTEGER,
            eslesme  TEXT,
            rapor    TEXT
        )
    """)

    sutunlari_tamamla(conn, "yurutme_varlik", [("sirket", "TEXT")])
    sutunlari_tamamla(conn, "yurutme_islem", [("sirket", "TEXT")])

    # --- İndeksler ---
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON transactions(ticker)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person ON transactions(person)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_disclosed ON transactions(disclosed_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_person_slug ON transactions(person_slug)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_uye_slug ON uye(slug)")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_fon ON holdings(fon_slug)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_donem ON holdings(donem)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_cusip ON holdings(cusip)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_ticker ON holdings(ticker)")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Veritabanı hazır: {DB_PATH}")
