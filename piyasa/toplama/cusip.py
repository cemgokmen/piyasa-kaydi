"""
holdings tablosundaki CUSIP kodlarının hisse kodu (ticker) karşılığını
OpenFIGI'den bulur ve holdings tablosuna yazar.

OpenFIGI anahtarsız sınırı: dakikada 25 istek, istek başına 10 kod.

Çalıştırmak için:  python -m piyasa cusip
"""
import time
from datetime import UTC, datetime

import requests

from piyasa.veritabani import get_connection, init_db

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
GRUP_BOYUTU = 10   # istek başına en fazla 10 kod
BEKLEME = 2.6      # dakikada ~23 istek


def eslenmemis_cusipleri_al(conn):
    """Henuz ticker'i bulunmamis CUSIP kodlarini getirir."""
    sorgu = """
        SELECT DISTINCT h.cusip
        FROM holdings h
        LEFT JOIN cusip_ticker c ON h.cusip = c.cusip
        WHERE c.cusip IS NULL
    """
    return [satir["cusip"] for satir in conn.execute(sorgu)]


def openfigi_sor(cusipler):
    """Bir grup CUSIP'i OpenFIGI'ye sorar, sonuc listesi doner."""
    istek = [{"idType": "ID_CUSIP", "idValue": c} for c in cusipler]
    cevap = requests.post(
        OPENFIGI_URL,
        json=istek,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if cevap.status_code == 429:
        return "sinir"
    if cevap.status_code != 200:
        print(f"  HTTP {cevap.status_code}: {cevap.text[:200]}")
        return None
    return cevap.json()

# ABD borsalarının OpenFIGI kodları
US_KODLARI = {"US", "UN", "UW", "UQ", "UR", "UA", "UP", "UV"}


def us_ticker_sec(veri):
    """
    Sadece ABD borsalarındaki hisse kodunu döndürür.
    Yabancı borsa kodları (Frankfurt, Londra vb.) bize yaramaz —
    sitedeki hisse sayfaları ABD kodlarıyla çalışıyor.
    """
    for kayit in veri:
        if kayit.get("exchCode") in US_KODLARI:
            return kayit.get("ticker")
    return None


def kaydet(conn, cusip, ticker):
    """Bulunan eslemeyi tabloya yazar."""
    conn.execute(
        "INSERT OR REPLACE INTO cusip_ticker (cusip, ticker, kaynak, guncelleme) "
        "VALUES (?, ?, ?, ?)",
        (cusip, ticker, "openfigi", datetime.now(UTC).isoformat()),
    )


def hisse_kodlarini_yaz(conn):
    """Bulunan eşlemeleri fon pozisyonlarına işler."""
    guncellenen = conn.execute(
        """UPDATE holdings
           SET ticker = (SELECT c.ticker FROM cusip_ticker c WHERE c.cusip = holdings.cusip)
           WHERE ticker IS NULL
             AND cusip IN (SELECT cusip FROM cusip_ticker WHERE ticker IS NOT NULL)"""
    ).rowcount
    conn.commit()
    print(f"Hisse kodu yazılan fon pozisyonu: {guncellenen}")


def main():
    init_db()
    conn = get_connection()
    hisse_kodlarini_yaz(conn)
    cusipler = eslenmemis_cusipleri_al(conn)
    toplam = len(cusipler)
    print(f"Eslenmemis CUSIP sayisi: {toplam}")

    if toplam == 0:
        print("Yapilacak is yok.")
        return

    bulunan = 0
    bulunamayan = 0

    for i in range(0, toplam, GRUP_BOYUTU):
        grup = cusipler[i:i + GRUP_BOYUTU]
        sonuc = openfigi_sor(grup)

        if sonuc == "sinir" or sonuc is None:
            print("  Hız sınırı ya da hata: 60 sn beklenip aynı grup yeniden denenecek.")
            time.sleep(60)
            sonuc = openfigi_sor(grup)
            if sonuc == "sinir" or sonuc is None:
                continue

        for cusip, kayit in zip(grup, sonuc, strict=True):
            veri = kayit.get("data")
            if veri:
                kaydet(conn, cusip, us_ticker_sec(veri))
                bulunan += 1
            else:
                kaydet(conn, cusip, None)
                bulunamayan += 1

        conn.commit()
        ilerleme = min(i + GRUP_BOYUTU, toplam)
        print(f"{ilerleme}/{toplam}  bulunan: {bulunan}  bulunamayan: {bulunamayan}")
        time.sleep(BEKLEME)

    hisse_kodlarini_yaz(conn)
    conn.close()
    print(f"\nBitti. Bulunan: {bulunan}  Bulunamayan: {bulunamayan}")


if __name__ == "__main__":
    main()
