"""
Fon isimlerinden SEC kimlik numaralarını (CIK) bulur.
SEC'in tam metin arama servisini kullanır — borsada işlem görmeyen
hedge fonlar da bu servisle bulunabiliyor.
Sonucu data/fonlar.json dosyasına yazar.
"""

import json
import time
from pathlib import Path

import requests

from fon_listesi import FONLAR

USER_AGENT = "PiyasaKaydi cemgokmen101@gmail.com"
BASE_DIR = Path(__file__).parent


def cik_ara(ad):
    """SEC'in şirket arama servisinde isim arar, 13F veren ilk sonucu döndürür."""
    url = "https://www.sec.gov/cgi-bin/browse-edgar"
    parametreler = {
        "action": "getcompany",
        "company": ad,
        "type": "13F-HR",
        "dateb": "",
        "owner": "exclude",
        "count": "10",
        "output": "atom",
    }

    cevap = requests.get(
        url,
        params=parametreler,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )

    if cevap.status_code != 200:
        return None, None

    metin = cevap.text

    # Tek sonuç varsa doğrudan şirket sayfasına yönlendiriyor
    if "<CIK>" in metin:
        cik = metin.split("<CIK>")[1].split("</CIK>")[0].strip()
        bulunan_ad = ad
        if "<conformed-name>" in metin:
            bulunan_ad = metin.split("<conformed-name>")[1].split("</conformed-name>")[0].strip()
        return cik.zfill(10), bulunan_ad

    # Birden çok sonuç varsa ilkini al
    if "CIK=" in metin:
        parca = metin.split("CIK=")[1]
        cik = parca.split("&")[0].split("\"")[0].strip()
        if cik.isdigit():
            return cik.zfill(10), ad

    return None, None


def main():
        # Önceki sonuçları koru, üzerine ekle
    dosya = BASE_DIR / "data" / "fonlar.json"
    if dosya.exists():
        with open(dosya, encoding="utf-8") as f:
            bulunan = json.load(f)
    else:
        bulunan = {}
    bulunamayan = []

    for ad in FONLAR:
        try:
            cik, gercek_ad = cik_ara(ad)
        except Exception as hata:
            print(f"  ! {ad:42} hata: {hata}")
            bulunamayan.append(ad)
            time.sleep(0.3)
            continue

        if cik:
            bulunan[ad] = {"cik": cik, "sec_adi": gercek_ad}
            print(f"  ✓ {ad:42} {cik}  ({gercek_ad})")
        else:
            bulunamayan.append(ad)
            print(f"  · {ad:42} bulunamadı")

        time.sleep(0.3)

    with open(BASE_DIR / "data" / "fonlar.json", "w", encoding="utf-8") as f:
        json.dump(bulunan, f, ensure_ascii=False, indent=2)

    print(f"\nBulunan: {len(bulunan)}   Bulunamayan: {len(bulunamayan)}")
    if bulunamayan:
        print("\nBulunamayanlar:")
        for ad in bulunamayan:
            print("  -", ad)


if __name__ == "__main__":
    main()