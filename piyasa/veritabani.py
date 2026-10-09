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
    # --- Devlet sözleşmeleri (USAspending.gov): şirkete yeni para bağlanan işlemler ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ihale (
            kimlik     TEXT PRIMARY KEY,
            ticker     TEXT NOT NULL,
            alici      TEXT,
            kurum      TEXT,
            alt_kurum  TEXT,
            tutar      REAL,
            tarih      TEXT,
            aciklama   TEXT,
            adres      TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ihale_tarama (
            ticker      TEXT PRIMARY KEY,
            arama_adi   TEXT,
            bulunan     INTEGER,
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

    # --- Borsa İstanbul ve KAP ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bist_sirket (
            kod        TEXT PRIMARY KEY,
            unvan      TEXT,
            mkk_oid    TEXT,
            xu100      INTEGER DEFAULT 0,
            xu030      INTEGER DEFAULT 0,
            guncelleme TEXT
        )
    """)
    # KAP bildirimleri: pay alım satım, geri alım ve (BIST 100 için) özel durum açıklamaları
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kap_bildirim (
            indeks        INTEGER PRIMARY KEY,   -- KAP bildirim numarası
            kod           TEXT,                  -- ilgili şirketin borsa kodu
            gonderen      TEXT,                  -- bildirimi gönderen kurum
            baslik        TEXT,
            ozet          TEXT,
            yayin         TEXT,                  -- 'YYYY-MM-DD HH:MM:SS'
            tur           TEXT,                  -- pay | geri_alim | ozel
            metin         TEXT,                  -- açıklama metni (pay ve geri alım için)
            detay_alindi  INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kap_pay_islem (
            indeks       INTEGER PRIMARY KEY,
            kod          TEXT,
            kisi         TEXT,                   -- işlemi yapan kişi, şirket ya da fon kurucusu
            kisi_turu    TEXT,                   -- kisi | sirket | fon
            islem        TEXT,                   -- buy | sell | NULL (ayrıntı ekte)
            islem_tarihi TEXT,
            nominal      REAL,                   -- işleme konu payların nominal tutarı (1 TL nominal = 1 pay)
            fiyat        REAL,                   -- ortalama ya da aralığın ortası
            fiyat_alt    REAL,
            fiyat_ust    REAL,
            tutar        REAL,                   -- nominal × fiyat, TL
            oran_sonra   REAL,                   -- işlemden sonraki sermaye payı, %
            gorev        TEXT                    -- bildirimdeki görevi (yönetim kurulu üyesi, genel müdür…)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kap_geri_alim (
            kod          TEXT NOT NULL,
            islem_tarihi TEXT NOT NULL,
            nominal      REAL NOT NULL,
            oran         REAL,                   -- sermayeye oranı, %
            fiyat        REAL,
            indeks       INTEGER,
            PRIMARY KEY (kod, islem_tarihi, nominal, fiyat)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kap_kod ON kap_bildirim(kod, yayin)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kap_pay_kod ON kap_pay_islem(kod, islem_tarihi)")

    # --- Kripto ---
    # Kongre üyelerinin kripto para ve kripto fonu (ETF) işlemleri. Hisse analizlerine
    # karışmasın diye transactions tablosundan ayrı tutulur.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kripto_islem (
            source_id        TEXT PRIMARY KEY,
            source           TEXT NOT NULL,
            person           TEXT NOT NULL,
            person_slug      TEXT,
            chamber          TEXT,
            state            TEXT,
            party            TEXT,
            coin             TEXT NOT NULL,      -- kripto/tanimlar.py'deki slug
            varlik           TEXT,               -- bildirimde yazan ad ('Bitcoin', 'iShares Bitcoin Trust')
            ticker           TEXT,               -- fon ise borsa kodu (IBIT)
            action           TEXT NOT NULL,      -- buy | sell
            amount_min       INTEGER,
            amount_max       INTEGER,
            transaction_date TEXT,
            disclosed_date   TEXT,
            source_url       TEXT,
            sahip            TEXT,
            fetched_at       TEXT
        )
    """)
    # CFTC haftalık raporu (finansal vadeliler): kurumsal yatırımcılar ve hedge fonları
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kripto_cot (
            coin           TEXT NOT NULL,
            tarih          TEXT NOT NULL,
            acik_pozisyon  INTEGER,
            kurum_uzun     INTEGER,
            kurum_kisa     INTEGER,
            hedge_uzun     INTEGER,
            hedge_kisa     INTEGER,
            PRIMARY KEY (coin, tarih)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kripto_coin ON kripto_islem(coin, transaction_date)")

    sutunlari_tamamla(conn, "kap_pay_islem", [("gorev", "TEXT")])
    sutunlari_tamamla(conn, "bist_sirket", [("sehir", "TEXT")])
    sutunlari_tamamla(conn, "yurutme_varlik", [("sirket", "TEXT")])
    sutunlari_tamamla(conn, "yurutme_islem", [("sirket", "TEXT")])
    sutunlari_tamamla(conn, "sirket_profili", [("kurulus", "INTEGER")])

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
    # Fon başına son çeyrek sorgusu (fon listesi, hisse sayfası) bu dizinle hızlanır
    conn.execute("CREATE INDEX IF NOT EXISTS idx_h_fon_donem ON holdings(fon_slug, donem)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ihale_ticker ON ihale(ticker, tarih)")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Veritabanı hazır: {DB_PATH}")
