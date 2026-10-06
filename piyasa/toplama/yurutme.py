"""
Başkan ve Başkan Yardımcısının mali durum bildirimleri.

Yürütme organı Kongre'ye değil ABD Hükümet Etiği Ofisi'ne (OGE) bildirir.
Başkan'ın işlem bildirimleri (OGE 278-T) çoğunlukla taranmış belgedir ve
içerikleri büyük ölçüde belediye ve şirket tahvilleridir; bu yüzden tek tek
işlemleri tabloya aktarmıyoruz, her bildirimi tarih ve resmî belge
bağlantısıyla listeliyoruz.

Çalıştırmak için:  python -m piyasa yurutme
"""

import re

import requests

from piyasa.veritabani import get_connection, init_db

API = "https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest"

# (OGE'deki ad, sitedeki adres, görev unvanı OGE'de)
KISILER = [
    ("Trump, Donald J", "donald-j-trump", "President"),
    ("Vance, JD", "jd-vance", "Vice President"),
]

TURLER = [
    (re.compile(r"Transaction", re.I), "islem"),
    (re.compile(r"Annual", re.I), "yillik"),
    (re.compile(r"Termination", re.I), "ayrilis"),
    (re.compile(r"Nominee|New Entrant", re.I), "giris"),
]


def bildirimleri_al(oge_adi):
    cevap = requests.get(API, params={
        "draw": 1, "start": 0, "length": 200, "search[value]": oge_adi,
        "order[0][column]": 0, "order[0][dir]": "desc",
    }, headers={"User-Agent": "Mozilla/5.0 PiyasaKaydi"}, timeout=60)
    cevap.raise_for_status()
    return cevap.json()["data"]


def main():
    init_db()
    conn = get_connection()
    for oge_adi, kisi, unvan in KISILER:
        eklenen = 0
        for b in bildirimleri_al(oge_adi):
            if b["name"] != oge_adi or b["title"] != unvan:
                continue
            bag = re.search(r"href='([^']+\.pdf)'[^>]*>([^<]*)<", b["type"], re.I)
            if not bag:
                continue      # adaylık bildirimleri yalnızca talep formuyla alınabiliyor
            adres, baslik = bag.group(1), bag.group(2).strip()
            tur = next((t for desen, t in TURLER if desen.search(baslik)), "diger")
            conn.execute(
                "INSERT OR REPLACE INTO yurutme_bildirimi (adres, kisi, tur, baslik, tarih) VALUES (?, ?, ?, ?, ?)",
                (adres, kisi, tur, baslik, b["docDate"][:10]),
            )
            eklenen += 1
        conn.commit()
        print(f"  {oge_adi}: {eklenen} bildirim")
    conn.close()


if __name__ == "__main__":
    main()
