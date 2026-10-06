"""
Testler gerçek veritabanına ve internete dokunmaz: her oturumda geçici bir
SQLite dosyası örnek kayıtlarla doldurulur, fiyat servisi sahte veriyle
değiştirilir.
"""

from datetime import date, timedelta

import pandas as pd
import pytest

from piyasa import veritabani
from piyasa.web import create_app, fiyat

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
    conn.commit()
    conn.close()

    yield yol
    veritabani.DB_PATH = eski


@pytest.fixture(scope="session")
def uygulama(veritabani_yolu):
    eski = fiyat._indir
    fiyat._indir = sahte_fiyat
    fiyat._onbellek.clear()
    app = create_app()
    app.config["TESTING"] = True
    yield app
    fiyat._indir = eski


@pytest.fixture()
def istemci(uygulama):
    return uygulama.test_client()
