"""
holdings tablosundaki CUSIP kodlarinin ticker karsiligini OpenFIGI'den bulur.
Calistirmak icin:  python cusip_ticker_bul.py
"""
import time
from datetime import datetime, timezone

import requests

from database import get_connection

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
GRUP_BOYUTU = 5
BEKLEME = 10


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
        (cusip, ticker, "openfigi", datetime.now(timezone.utc).isoformat()),
    )


def main():
    conn = get_connection()
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

        if sonuc is None:
            print("  Istek basarisiz, 60 saniye beklenip devam edilecek.")
            time.sleep(60)
            continue

        for cusip, kayit in zip(grup, sonuc):
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

    conn.close()
    print(f"\nBitti. Bulunan: {bulunan}  Bulunamayan: {bulunamayan}")


if __name__ == "__main__":
    main()
