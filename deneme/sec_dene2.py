"""
Tek bir Form 4 bildirimini indirip içindeki verileri ayrıştırmayı dener.
"""

import xml.etree.ElementTree as ET

import requests

USER_AGENT = "PiyasaKaydi cemgokmen101@gmail.com"

# 8.1'de gördüğümüz ilk kayıt
YOL = "edgar/data/910638/0001628280-26-058429.txt"


def indir(yol):
    url = f"https://www.sec.gov/Archives/{yol}"
    cevap = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    cevap.raise_for_status()
    return cevap.text


def xml_bolumunu_ayikla(metin):
    """Dosyanın içindeki asıl XML bloğunu bulup çıkarır."""
    bas = metin.find("<ownershipDocument>")
    son = metin.find("</ownershipDocument>")
    if bas == -1 or son == -1:
        return None
    return metin[bas:son + len("</ownershipDocument>")]


def main():
    metin = indir(YOL)
    print(f"Dosya boyutu: {len(metin)} karakter")

    xml_metni = xml_bolumunu_ayikla(metin)
    if xml_metni is None:
        print("XML bloğu bulunamadı. İlk 1000 karakter:")
        print(metin[:1000])
        return

    print(f"XML boyutu: {len(xml_metni)} karakter\n")

    kok = ET.fromstring(xml_metni)

    print("--- TEMEL BİLGİLER ---")
    print("Şirket   :", kok.findtext("issuer/issuerName"))
    print("Sembol   :", kok.findtext("issuer/issuerTradingSymbol"))
    print("Kişi     :", kok.findtext("reportingOwner/reportingOwnerId/rptOwnerName"))
    print("Yön. kur.:", kok.findtext("reportingOwner/reportingOwnerRelationship/isDirector"))
    print("Yönetici :", kok.findtext("reportingOwner/reportingOwnerRelationship/isOfficer"))
    print("Unvan    :", kok.findtext("reportingOwner/reportingOwnerRelationship/officerTitle"))
    print("Dönem    :", kok.findtext("periodOfReport"))

    islemler = kok.findall("nonDerivativeTable/nonDerivativeTransaction")
    print(f"\n--- İŞLEM SAYISI: {len(islemler)} ---")

    for i, islem in enumerate(islemler, start=1):
        print(f"\nİşlem {i}:")
        print("  Menkul  :", islem.findtext("securityTitle/value"))
        print("  Tarih   :", islem.findtext("transactionDate/value"))
        print("  Kod     :", islem.findtext("transactionCoding/transactionCode"))
        print("  Adet    :", islem.findtext("transactionAmounts/transactionShares/value"))
        print("  Fiyat   :", islem.findtext("transactionAmounts/transactionPricePerShare/value"))
        print("  A/D     :", islem.findtext("transactionAmounts/transactionAcquiredDisposedCode/value"))


if __name__ == "__main__":
    main()