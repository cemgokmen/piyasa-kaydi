"""
Anormal büyük tutarlı kayıtları bulur ve kaynak belgedeki
ham adet/fiyat değerlerini gösterir.
"""

import xml.etree.ElementTree as ET

import requests

from database import get_connection

USER_AGENT = "PiyasaKaydi cemgokmen101@gmail.com"


def ham_dosya_url(index_url):
    """index.htm adresinden ham .txt adresini üretir."""
    parcalar = index_url.rstrip("/").split("/")
    dosya_no = parcalar[-1].replace("-index.htm", "")
    cik = parcalar[-3]
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{dosya_no}.txt"


def main():
    conn = get_connection()
    rows = conn.execute(
        "SELECT ticker, person, amount_max, transaction_date, source_url "
        "FROM transactions ORDER BY amount_max DESC LIMIT 5"
    ).fetchall()
    conn.close()

    for row in rows:
        print("=" * 60)
        print(f"{row['ticker']}  {row['person']}")
        print(f"Bizim hesapladığımız: {row['amount_max']:,}")

        url = ham_dosya_url(row["source_url"])
        metin = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30).text

        bas = metin.find("<ownershipDocument>")
        son = metin.find("</ownershipDocument>")
        kok = ET.fromstring(metin[bas:son + len("</ownershipDocument>")])

        for islem in kok.findall("nonDerivativeTable/nonDerivativeTransaction"):
            print("  ---")
            print("  Menkul :", islem.findtext("securityTitle/value"))
            print("  Kod    :", islem.findtext("transactionCoding/transactionCode"))
            print("  Adet   :", islem.findtext("transactionAmounts/transactionShares/value"))
            print("  Fiyat  :", islem.findtext("transactionAmounts/transactionPricePerShare/value"))


if __name__ == "__main__":
    main()