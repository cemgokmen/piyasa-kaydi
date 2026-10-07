"""
Testler gerçek veritabanına ve internete dokunmaz: her oturumda geçici bir
SQLite dosyası örnek kayıtlarla doldurulur, fiyat servisi sahte veriyle
değiştirilir.
"""

from datetime import UTC, date, timedelta

import pandas as pd
import pytest

from piyasa import fiyat, hisse_haberleri, sirket_profili, temel, veritabani
from piyasa.emtia import haberler, serit
from piyasa.web import create_app

BUGUN = date.today()


def gun(n):
    return (BUGUN - timedelta(days=n)).isoformat()


def _islem(no, **alanlar):
    kayit = {
        "source_id": f"test-{no}",
        "source": "edgar_form4",
        "person": "Doe John",
        "person_slug": "doe-john",
        "job_title": "CEO",
        "company": "Örnek Şirket",
        "ticker": "ORNK",
        "asset_name": "ORNEK CORP",
        "action": "buy",
        "amount_min": 100_000,
        "amount_max": 100_000,
        "currency": "USD",
        "transaction_date": gun(3),
        "disclosed_date": gun(2),
        "source_url": "https://www.sec.gov/ornek",
        "share_price": 10.0,
        "suspect": 0,
    }
    kayit.update(alanlar)
    return kayit


def ornek_kayitlar():
    kayitlar = []
    # Sayfalama denensin diye 60 yönetici işlemi (sayfa boyutu 50)
    for i in range(60):
        kayitlar.append(_islem(
            i,
            person=f"Yonetici {i % 6}",
            person_slug=f"yonetici-{i % 6}",
            action="buy" if i % 3 else "sell",
            amount_min=1_000 * (i + 1),
            amount_max=1_000 * (i + 1),
            transaction_date=gun(5 + i % 20),
            disclosed_date=gun(3 + i % 20),
        ))
    # Geç bildirilmiş bir yönetici işlemi
    kayitlar.append(_islem(100, transaction_date=gun(40), disclosed_date=gun(10)))
    # Yahoo'da fiyatı olmayan hisse (sahte_fiyat None döner)
    kayitlar.append(_islem(102, ticker="YOK", asset_name="FIYATSIZ CORP"))
    # Şüpheli kayıt: hiçbir yerde görünmemeli
    kayitlar.append(_islem(101, person="Hatali Kayit", person_slug="hatali-kayit",
                           ticker="HATA", suspect=1, amount_max=10**13))

    # Siyasetçiler: biri yüklü alım, biri geç bildirim
    siyaset = {"source": "house_ptr", "chamber": "Temsilciler Meclisi",
               "job_title": "Temsilciler Meclisi üyesi", "share_price": None}
    kayitlar += [
        _islem(200, person="Jane Senator", person_slug="jane-senator", party="D",
               state="CA-11", ticker="NVDA", asset_name="NVIDIA Corporation",
               amount_min=250_001, amount_max=500_000, **siyaset),
        _islem(201, person="Jane Senator", person_slug="jane-senator", party="D",
               state="CA-11", ticker="AAPL", asset_name="Apple Inc.", action="sell",
               amount_min=1_001, amount_max=15_000, **siyaset),
        _islem(202, person="Bob Rep", person_slug="bob-rep", party="R", state="TX-02",
               ticker="NVDA", asset_name="NVIDIA Corporation", amount_min=1_001,
               amount_max=15_000, transaction_date=gun(120), disclosed_date=gun(20),
               **siyaset),
    ]
    for i in range(12):
        kayitlar.append(_islem(
            300 + i, person="Jane Senator", person_slug="jane-senator", party="D", state="CA-11",
            ticker="NVDA", asset_name="NVIDIA Corporation", amount_min=15_001, amount_max=50_000,
            transaction_date=gun(200 + i * 10), disclosed_date=gun(180 + i * 10), **siyaset,
        ))
    return kayitlar


def ornek_fonlar():
    satirlar = []
    for donem, adet in (("2026-03-31", 100), ("2026-06-30", 150)):
        for kod, cusip in (("NVDA", "67066G104"), ("ORNK", "000000001")):
            satirlar.append({
                "source_id": f"fon-{donem}-{kod}", "fon_adi": "Örnek Fon", "fon_slug": "ornek-fon",
                "cik": "0000000001", "donem": donem, "bildirim_tarihi": donem,
                "sirket_adi": f"{kod} CORP", "cusip": cusip, "ticker": kod,
                "deger": adet * 1_000_000, "adet": adet * 1_000,
            })
    # Yalnız önceki çeyrekte olan pozisyon: "tamamen çıkılan"
    satirlar.append({**satirlar[0], "source_id": "fon-cikis", "cusip": "000000009",
                     "ticker": "CIKS", "sirket_adi": "CIKIS CORP"})
    return satirlar


def ornek_emtia_verisi(conn):
    """CFTC, EIA ve FRED tablolarına iki yıllık sahte haftalık veri."""
    for hafta in range(104):
        t = gun(7 * (103 - hafta))
        for slug in ("altin", "gumus", "brent"):
            conn.execute(
                "INSERT INTO cot VALUES (?, ?, ?, ?, ?, ?, ?)",
                (slug, t, 500_000, 100_000 + hafta * 500, 50_000, 20_000, 60_000),
            )
        conn.execute("INSERT INTO eia_stok VALUES ('ham_petrol', ?, ?)", (t, 420_000 + hafta * 10))
    for i in range(800):
        t = gun(800 - i)
        conn.execute("INSERT INTO makro VALUES ('fed_faiz', ?, ?)", (t, 4.25 if i < 400 else 4.0))
        conn.execute("INSERT INTO makro VALUES ('abd_10y', ?, ?)", (t, 4.0 + i / 1000))
        conn.execute("INSERT INTO makro VALUES ('reel_faiz', ?, ?)", (t, 2.0 + i / 2000))
    conn.execute("INSERT INTO emtia_guncelleme VALUES ('son', ?)", (gun(0) + "T00:00:00",))


def ornek_analiz_verisi(conn):
    """Komiteler, sektörler, fiyat geçmişi; ardından getiriler hesaplanır."""
    conn.executemany("INSERT INTO uye VALUES (?, ?, ?, ?, ?, ?)", [
        ("J000001", "Jane Senator", "jane-senator", "D", "CA-11", "House Minority Whip"),
        ("B000001", "Bob Rep", "bob-rep", "R", "TX-02", None),
    ])
    # Jane, teknolojiyi denetleyen Bilim komitesinde: NVDA alımları çıkar çatışması sayılır
    conn.executemany("INSERT INTO komite_uyeligi VALUES (?, ?, ?)", [
        ("J000001", "HSSY", None), ("B000001", "HSAG", "Chairman"),
    ])
    conn.executemany("INSERT INTO yurutme_bildirimi VALUES (?, ?, ?, ?, ?)", [
        ("https://oge.gov/t1.pdf", "donald-j-trump", "islem", "278 Transaction", gun(14)),
        ("https://oge.gov/y1.pdf", "donald-j-trump", "yillik", "Annual (2026)", gun(90)),
    ])
    conn.executemany(
        "INSERT INTO yurutme_varlik (kisi, hesap, ad, ticker, alt, ust, eslesme, rapor, sirket) VALUES (?,?,?,?,?,?,?,?,?)", [
            ("donald-j-trump", "INVESTMENT ACCOUNT #1", "NVIDIACORP", "NVDA", 1_000_001, 5_000_000, "tam", "https://oge.gov/y1.pdf", "NVIDIA CORP"),
            ("donald-j-trump", "INVESTMENT ACCOUNT #2", "APPLE INC", "AAPL", 250_001, 500_000, "tam", "https://oge.gov/y1.pdf", "Apple Inc."),
            ("donald-j-trump", "INVESTMENT ACCOUNT #4", "CITY OF X GO BONDS", None, 100_001, 250_000, "tahvil_hesabi", "https://oge.gov/y1.pdf", None),
        ])
    conn.executemany(
        "INSERT INTO yurutme_islem (kisi, hesap, ad, ticker, islem, tarih, alt, ust, eslesme, rapor, sirket) VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
            ("donald-j-trump", "INVESTMENT ACCOUNT #2", "APPLE INC", "AAPL", "buy", gun(200), 15_001, 50_000, "tam", "https://oge.gov/y1.pdf", "Apple Inc."),
            ("donald-j-trump", "INVESTMENT ACCOUNT #2", "NVIDIACORP", "NVDA", "sell", gun(150), 1_001, 15_000, "tam", "https://oge.gov/y1.pdf", "NVIDIA CORP"),
        ])
    conn.execute("INSERT INTO yurutme_rapor VALUES (?, ?, ?, ?)", ("https://oge.gov/y1.pdf", "donald-j-trump", 927, gun(0)))
    conn.executemany("INSERT INTO sirket VALUES (?, ?, ?, ?, ?)", [
        ("NVDA", 1045810, 3674, "Semiconductors", "Teknoloji"),
        ("AAPL", 320193, 3571, "Electronic Computers", "Teknoloji"),
        ("ORNK", 1, 3812, "Defense", "Savunma ve havacılık"),
    ])
    tarihler = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=500)
    for i, t in enumerate(tarihler):
        g = t.strftime("%Y-%m-%d")
        conn.executemany("INSERT INTO fiyat_gecmisi VALUES (?, ?, ?)", [
            ("SPY", g, 400 + i * 0.2), ("NVDA", g, 100 + i * 0.5),
            ("AAPL", g, 200 - i * 0.1), ("ORNK", g, 50 + (i % 20)),
        ])


def sahte_haberler(sorgu):
    from datetime import datetime
    return [{
        "baslik": f"Örnek haber {i}: OPEC üretim kararı" if i % 2 else f"Fed faiz kararı sonrası emtialar {i}",
        "kaynak": "Örnek Ajans",
        "adres": f"https://ornek.com/haber/{i}",
        "zaman": datetime(2026, 10, 1 + i, tzinfo=UTC),
        "tarih": f"2026-10-0{1 + i}",
        "etiketler": ["OPEC", "Arz"] if i % 2 else ["Merkez bankası"],
    } for i in range(5)]


def sahte_fiyat(kod):
    if kod in ("YOK", "HATA"):
        return None
    tarihler = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=2700)
    kapanis = pd.Series(range(100, 100 + len(tarihler)), index=tarihler, dtype=float)
    tablo = pd.DataFrame({"Close": kapanis, "Volume": 1_000})
    return {
        "kod": kod,
        "fiyat": float(kapanis.iloc[-1]),
        "tarih": tarihler[-1].strftime("%Y-%m-%d"),
        "degisimler": [
            {"anahtar": a, "etiket": e, "oran": fiyat._degisim(kapanis, g)}
            for a, e, g in fiyat.DEGISIM_DONEMLERI
        ],
        "hacim": fiyat._hacim_ozeti(tablo),
        "seriler": {a: fiyat._seri(tablo, g, o) for a, g, o in fiyat.GRAFIK_ARALIKLARI},
    }


def sahte_anlik(kod):
    if kod in ("YOK", "HATA"):
        return None
    return {"kod": kod, "fiyat": 123.45, "onceki_kapanis": 120.0, "degisim": 123.45 / 120 - 1,
            "zaman": 1_791_300_000, "durum": "REGULAR", "durum_etiket": "Piyasa açık",
            "gecikme": 0, "seans_disi": None}


def sahte_temel_veri(kod):
    """temel._veri_al yerine: AAPL için örnek bilanço, diğerleri için veri yok."""
    if kod != "AAPL":
        return {}, None, None, None, None
    ceyrekler = pd.to_datetime(["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31", "2026-06-30"])
    gelir = pd.DataFrame(
        [[94e9, 102e9, 124e9, 111e9, 109e9], [23e9, 27e9, 36e9, 29e9, 30e9], [1.57, 1.85, 2.40, 2.01, 2.02]],
        index=["Total Revenue", "Net Income", "Diluted EPS"], columns=ceyrekler)
    bilanco = pd.DataFrame([[350e9], [70e9]], index=["Total Assets", "Stockholders Equity"], columns=ceyrekler[-1:])
    bilgi = {"quoteType": "EQUITY", "currency": "USD", "financialCurrency": "USD", "currentPrice": 300.0,
             "marketCap": 4.9e12, "trailingPE": 38.17, "forwardPE": 34.7, "priceToBook": 45.2,
             "dividendYield": 0.32, "profitMargins": 0.276, "trailingEps": 8.72, "totalCash": 62e9,
             "totalDebt": 84e9, "debtToEquity": 78.4, "fiftyTwoWeekLow": 243.0, "fiftyTwoWeekHigh": 345.0,
             "targetMeanPrice": 330.0, "targetLowPrice": 215.0, "targetHighPrice": 405.0,
             "numberOfAnalystOpinions": 39, "recommendationKey": "buy", "heldPercentInstitutions": 0.66}
    return bilgi, gelir, bilanco, None, {"Earnings Date": [BUGUN + timedelta(days=20)], "Earnings Average": 1.98}


def sahte_hisse_haberleri(ticker, ad):
    from datetime import datetime
    if ticker != "NVDA":
        return []
    an = datetime.now(UTC)
    return [
        {"baslik": "NVIDIA yeni yapay zeka çipini tanıttı", "kaynak": "Anadolu Ajansı", "adres": "https://example.com/1",
         "zaman": an, "tarih": an.strftime("%Y-%m-%d"), "dil": "tr"},
        {"baslik": "NVIDIA hisseleri rekor kırdı", "orijinal": "Nvidia shares hit a record", "kaynak": "Reuters",
         "adres": "https://example.com/2", "zaman": an - timedelta(days=3), "tarih": an.strftime("%Y-%m-%d"), "dil": "en"},
    ]


def sahte_profil(ticker):
    if ticker != "AAPL":
        return None
    return {"ticker": "AAPL", "ozet": "Apple akıllı telefon ve bilgisayar üretir.", "ozet_en": "Apple makes phones.",
            "sektor": "Teknoloji", "endustri": "Tüketici elektroniği", "calisan": 150000,
            "merkez": "Cupertino, CA", "site": "https://www.apple.com", "kurulus": 1976, "guncelleme": "2026-01-01T00:00:00+00:00"}


@pytest.fixture(scope="session")
def veritabani_yolu(tmp_path_factory):
    yol = tmp_path_factory.mktemp("veri") / "test.db"
    eski = veritabani.DB_PATH
    veritabani.DB_PATH = yol
    veritabani.init_db()

    conn = veritabani.get_connection()
    for tablo, kayitlar in (("transactions", ornek_kayitlar()), ("holdings", ornek_fonlar())):
        for k in kayitlar:
            conn.execute(
                f"INSERT INTO {tablo} ({', '.join(k)}) VALUES ({', '.join('?' * len(k))})",
                list(k.values()),
            )
    ornek_emtia_verisi(conn)
    ornek_analiz_verisi(conn)
    conn.execute(
        "INSERT INTO sirket_profili (ticker, ozet, ozet_en, sektor, endustri, calisan, merkez, site, guncelleme) "
        "VALUES ('NVDA', 'NVIDIA yapay zeka ve grafik işlemcileri tasarlar.', 'NVIDIA designs GPUs.', 'Teknoloji', "
        "'Yarı iletkenler', 36000, 'Santa Clara, CA', 'https://www.nvidia.com', '2999-01-01T00:00:00+00:00')"
    )
    conn.commit()
    conn.close()

    from piyasa.analiz import cakisma, getiri, sinyaller
    getiri.main()
    cakisma.onbellegi_temizle()
    from piyasa import uyeler
    uyeler.onbellegi_temizle()
    sinyaller.basari.temizle()
    sinyaller.uclu_onay.temizle()

    yield yol
    veritabani.DB_PATH = eski


@pytest.fixture(scope="session")
def uygulama(veritabani_yolu):
    eski = (fiyat._indir, fiyat._anlik_indir, haberler._indir, sirket_profili._getir, temel._veri_al,
            hisse_haberleri._al)
    fiyat._indir = sahte_fiyat
    fiyat._anlik_indir = sahte_anlik
    haberler._indir = sahte_haberler
    sirket_profili._getir = sahte_profil
    temel._veri_al = sahte_temel_veri
    hisse_haberleri._al = sahte_hisse_haberleri
    hisse_haberleri._haberler.temizle()
    temel._temel.temizle()
    fiyat._bilgi.temizle()
    fiyat._anlik.temizle()
    serit.serit.temizle()
    haberler._secilmis.temizle()
    app = create_app()
    app.config["TESTING"] = True
    yield app
    (fiyat._indir, fiyat._anlik_indir, haberler._indir, sirket_profili._getir, temel._veri_al,
     hisse_haberleri._al) = eski


@pytest.fixture()
def istemci(uygulama):
    return uygulama.test_client()
