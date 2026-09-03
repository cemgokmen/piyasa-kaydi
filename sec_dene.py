"""
SEC EDGAR'a bağlanıp günlük bildirim listesini indirir.
Şu an sadece deniyoruz: veriyi ekrana basıp nasıl geldiğine bakacağız.
"""

from datetime import date, timedelta

import requests

# SEC kendisine istek atan herkesin kim olduğunu bildirmesini istiyor.
# Buraya kendi e-posta adresini yaz.
USER_AGENT = "PiyasaKaydi cemgokmen101@gmail.com"


def daily_index_url(gun):
    """Belirli bir günün bildirim listesinin adresini üretir."""
    ceyrek = (gun.month - 1) // 3 + 1
    return (
        f"https://www.sec.gov/Archives/edgar/daily-index/"
        f"{gun.year}/QTR{ceyrek}/form.{gun:%Y%m%d}.idx"
    )


def son_is_gununu_bul():
    """Bugünden geriye giderek dosyası olan ilk günü bulur."""
    gun = date.today()

    for _ in range(7):
        url = daily_index_url(gun)
        cevap = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        print(f"{gun}  ->  HTTP {cevap.status_code}")

        if cevap.status_code == 200:
            return gun, cevap.text

        gun -= timedelta(days=1)

    return None, None


def main():
    gun, icerik = son_is_gununu_bul()

    if icerik is None:
        print("Hiçbir gün için dosya bulunamadı.")
        return

    satirlar = icerik.splitlines()
    print(f"\nToplam satır: {len(satirlar)}")

    print("\n--- DOSYANIN İLK 12 SATIRI ---")
    for satir in satirlar[:12]:
        print(repr(satir))

    form4 = [s for s in satirlar if s.startswith("4 ")]
    print(f"\n--- FORM 4 SAYISI: {len(form4)} ---")

    print("\n--- İLK 5 FORM 4 SATIRI ---")
    for satir in form4[:5]:
        print(repr(satir))


if __name__ == "__main__":
    main()