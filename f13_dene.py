"""
13F verisinin nasıl geldiğine bakıyoruz.
"""

import xml.etree.ElementTree as ET

import requests

USER_AGENT = "PiyasaKaydi cemgokmen101@gmail.com"

# Berkshire Hathaway'in SEC kimlik numarası
CIK = "0001067983"


def indir(url):
    cevap = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    cevap.raise_for_status()
    return cevap


def temiz(etiket):
    """XML etiketindeki namespace önekini atar."""
    return etiket.split("}")[-1]


def main():
    url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
    veri = indir(url).json()

    print("Şirket:", veri.get("name"))

    son = veri["filings"]["recent"]

    # En son 13F-HR bildirimini bul
    sira = None
    for i, form in enumerate(son["form"]):
        if form == "13F-HR":
            sira = i
            break

    if sira is None:
        print("13F-HR bulunamadı.")
        return

    print("Dönem:", son["reportDate"][sira])
    print("Bildirim tarihi:", son["filingDate"][sira])

    dosya_no = son["accessionNumber"][sira].replace("-", "")
    klasor = f"https://www.sec.gov/Archives/edgar/data/{int(CIK)}/{dosya_no}"

    icerik = indir(f"{klasor}/index.json").json()

    tablo_adi = None
    for item in icerik["directory"]["item"]:
        ad = item["name"]
        if ad.endswith(".xml") and "primary_doc" not in ad:
            tablo_adi = ad
            break

    if not tablo_adi:
        print("Portföy dosyası bulunamadı.")
        return

    print("Portföy dosyası:", tablo_adi)

    metin = indir(f"{klasor}/{tablo_adi}").text
    kok = ET.fromstring(metin)

    kalemler = [e for e in kok.iter() if temiz(e.tag) == "infoTable"]
    print(f"\nToplam kalem: {len(kalemler)}")

    print("\n--- İLK 3 KALEM ---")
    for kalem in kalemler[:3]:
        print("  ---")
        for alt in kalem.iter():
            if alt is kalem:
                continue
            if alt.text and alt.text.strip():
                print(f"  {temiz(alt.tag):22} {alt.text.strip()}")


if __name__ == "__main__":
    main()