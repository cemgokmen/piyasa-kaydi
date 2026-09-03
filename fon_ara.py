"""
Bir isimle SEC'te 13F veren kurumları arar ve son bildirim tarihlerini gösterir.
Kullanım:  python fon_ara.py vanguard
"""

import sys
import time

import requests

USER_AGENT = "PiyasaKaydi cemgokmen101@gmail.com"


def indir(url, params=None):
    cevap = requests.get(
        url, params=params, headers={"User-Agent": USER_AGENT}, timeout=60
    )
    cevap.raise_for_status()
    return cevap


def main():
    if len(sys.argv) < 2:
        print("Kullanım: python fon_ara.py <isim>")
        return

    aranan = " ".join(sys.argv[1:])

    cevap = indir(
        "https://www.sec.gov/cgi-bin/browse-edgar",
        {
            "action": "getcompany",
            "company": aranan,
            "type": "13F-HR",
            "dateb": "",
            "owner": "exclude",
            "count": "40",
        },
    )

    metin = cevap.text

    # Sonuç tablosundaki CIK ve isimleri ayıkla
    adaylar = []
    for parca in metin.split("CIK=")[1:]:
        cik = parca.split("&")[0].split('"')[0].strip()
        if not cik.isdigit():
            continue
        # İsim, bağlantıdan sonraki hücrede
        ad = ""
        if "</a></td><td scope=\"row\">" in parca:
            ad = parca.split("</a></td><td scope=\"row\">")[1].split("</td>")[0]
        adaylar.append((cik.zfill(10), ad.strip()))

    if not adaylar:
        print("Sonuç yok.")
        return

    print(f"'{aranan}' icin {len(adaylar)} sonuc:\n")

    for cik, ad in adaylar[:15]:
        try:
            veri = indir(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
            son = veri["filings"]["recent"]
            son_13f = None
            for i, form in enumerate(son["form"]):
                if form == "13F-HR":
                    son_13f = son["reportDate"][i]
                    break
            durum = son_13f or "13F yok"
        except Exception:
            durum = "okunamadi"

        print(f"  {cik}  son 13F: {durum:12}  {veri.get('name', ad)[:45]}")
        time.sleep(0.2)


if __name__ == "__main__":
    main()