"""
Takip listesindeki fonların 13F bildirimlerini çekip veritabanına yazar.

Çalıştırmak için:  python fon_toplayici.py
"""

import json
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from database import get_connection, init_db
from slug import slugify

USER_AGENT = "PiyasaKaydi cemgokmen101@gmail.com"
BASE_DIR = Path(__file__).parent

# Her fon için kaç çeyrek geriye gidilsin
CEYREK_SAYISI = 4

BEKLEME = 0.2


def indir(url, deneme=3):
    son_hata = None
    for sira in range(deneme):
        try:
            cevap = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
            cevap.raise_for_status()
            return cevap
        except requests.HTTPError:
            raise
        except requests.RequestException as hata:
            son_hata = hata
            time.sleep(3 * (sira + 1))
    raise son_hata


def temiz(etiket):
    """XML etiketindeki namespace önekini atar."""
    return etiket.split("}")[-1]


def bildirimleri_bul(cik):
    """Bir fonun son 13F-HR bildirimlerini listeler."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    veri = indir(url).json()
    son = veri["filings"]["recent"]

    sonuc = []
    for i, form in enumerate(son["form"]):
        if form != "13F-HR":
            continue
        sonuc.append({
            "dosya_no": son["accessionNumber"][i],
            "donem": son["reportDate"][i],
            "bildirim_tarihi": son["filingDate"][i],
        })
        if len(sonuc) >= CEYREK_SAYISI:
            break

    return sonuc, veri.get("name", "")


def portfoy_oku(cik, dosya_no):
    """Bildirimin portföy tablosunu indirip kalemleri döndürür."""
    no_tiresiz = dosya_no.replace("-", "")
    klasor = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{no_tiresiz}"

    icerik = indir(f"{klasor}/index.json").json()

    tablo_adi = None
    for item in icerik["directory"]["item"]:
        ad = item["name"]
        if ad.endswith(".xml") and "primary_doc" not in ad:
            tablo_adi = ad
            break

    if not tablo_adi:
        return [], klasor

    metin = indir(f"{klasor}/{tablo_adi}").text
    kok = ET.fromstring(metin)

    kalemler = []
    for kalem in kok.iter():
        if temiz(kalem.tag) != "infoTable":
            continue

        alanlar = {}
        for alt in kalem.iter():
            if alt is kalem:
                continue
            if alt.text and alt.text.strip():
                alanlar[temiz(alt.tag)] = alt.text.strip()

        cusip = alanlar.get("cusip")
        if not cusip:
            continue

        try:
            deger = int(float(alanlar.get("value", 0)))
            adet = float(alanlar.get("sshPrnamt", 0))
        except ValueError:
            continue

        kalemler.append({
            "cusip": cusip.upper(),
            "sirket_adi": alanlar.get("nameOfIssuer", ""),
            "deger": deger,
            "adet": adet,
        })

    return kalemler, klasor


def kalemleri_birlestir(kalemler):
    """
    Aynı CUSIP birden çok satırda geçebiliyor (farklı alt yöneticiler).
    Hepsini tek pozisyonda topluyoruz.
    """
    toplam = defaultdict(lambda: {"deger": 0, "adet": 0.0, "sirket_adi": ""})

    for k in kalemler:
        hedef = toplam[k["cusip"]]
        hedef["deger"] += k["deger"]
        hedef["adet"] += k["adet"]
        if not hedef["sirket_adi"]:
            hedef["sirket_adi"] = k["sirket_adi"]

    return toplam


COLUMNS = [
    "source_id", "fon_adi", "fon_slug", "cik", "donem", "bildirim_tarihi",
    "sirket_adi", "cusip", "ticker", "deger", "adet", "source_url", "fetched_at",
]


def kaydet(conn, kayit):
    degerler = [kayit.get(s) for s in COLUMNS]
    yer = ", ".join("?" for _ in COLUMNS)
    imlec = conn.execute(
        f"INSERT OR IGNORE INTO holdings ({', '.join(COLUMNS)}) VALUES ({yer})",
        degerler,
    )
    return imlec.rowcount


def main():
    init_db()

    with open(BASE_DIR / "data" / "fonlar.json", encoding="utf-8") as f:
        fonlar = json.load(f)

    print(f"{len(fonlar)} fon işlenecek.\n")

    conn = get_connection()
    simdi = datetime.now(timezone.utc).isoformat()

    toplam_eklenen = 0

    for ad, bilgi in fonlar.items():
        cik = bilgi["cik"] if isinstance(bilgi, dict) else bilgi

        try:
            bildirimler, sec_adi = bildirimleri_bul(cik)
        except Exception as hata:
            print(f"  ! {ad}: {hata}")
            continue

        if not bildirimler:
            print(f"  · {ad}: 13F bulunamadı")
            continue

        fon_slug = slugify(ad)
        eklenen = 0

        for bildirim in bildirimler:
            try:
                kalemler, klasor = portfoy_oku(cik, bildirim["dosya_no"])
            except Exception as hata:
                print(f"    ! {bildirim['donem']}: {hata}")
                time.sleep(BEKLEME)
                continue

            birlesik = kalemleri_birlestir(kalemler)

            for cusip, veri in birlesik.items():
                eklenen += kaydet(conn, {
                    "source_id": f"{cik}-{bildirim['donem']}-{cusip}",
                    "fon_adi": ad,
                    "fon_slug": fon_slug,
                    "cik": cik,
                    "donem": bildirim["donem"],
                    "bildirim_tarihi": bildirim["bildirim_tarihi"],
                    "sirket_adi": veri["sirket_adi"],
                    "cusip": cusip,
                    "ticker": None,
                    "deger": veri["deger"],
                    "adet": veri["adet"],
                    "source_url": klasor,
                    "fetched_at": simdi,
                })

            conn.commit()
            time.sleep(BEKLEME)

        toplam_eklenen += eklenen
        print(f"  ✓ {ad:42} {len(bildirimler)} çeyrek, {eklenen} pozisyon")

    toplam = conn.execute("SELECT COUNT(*) FROM holdings").fetchone()[0]
    conn.close()

    print(f"\nYeni eklenen: {toplam_eklenen}")
    print(f"Tablodaki toplam pozisyon: {toplam}")


if __name__ == "__main__":
    main()