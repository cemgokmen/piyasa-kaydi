"""
Başkan ve Başkan Yardımcısının yıllık mali durum bildiriminden (OGE 278e)
hisse portföyü ve işlemleri.

Yıllık bildirim yüzlerce sayfadır ve her şeyi içerir: hisse, tahvil, şirket
payı, gayrimenkul, nakit. Buradan yalnızca borsada işlem gören hisse ve
fonlar ayıklanır:

  1. Varlıklar (Bölüm 2, 5, 6) ve işlemler (Bölüm 7) satır satır okunur.
  2. Çoğunluğu tahvil olan hesaplar bütünüyle dışarıda bırakılır.
  3. Tahvil, mevduat, LLC gibi kalemler ve şirket adı güvenle bir borsa
     koduyla eşlenemeyenler elenir (piyasa/eslestirme.py).

Elenen kalemler de kaydedilir ki sayfada ne kadarının dışarıda kaldığı
gösterilebilsin.

Çalıştırmak için:  python -m piyasa yurutme-portfoy [--yeniden]
"""

import io
import re
import sys
from collections import Counter
from datetime import UTC, datetime

import pdfplumber
import requests

from piyasa.eslestirme import HISSE_DEGIL, Eslestirici
from piyasa.veritabani import get_connection, init_db

DEGER = r"(None \(or less than \$1,001\)|Over \$[\d,]+|\$[\d,]+\s*-\s*\$[\d,]+)"
NUMARA = r"[\dIl]+(?:\s?\.\s?[\dIl]+)*\.?"

VARLIK = re.compile(rf"^\s*{NUMARA}\s+(?P<ad>.+?)\s+(?:Yes|No|N\s?/?\s?I?A)\s+{DEGER}")
ISLEM = re.compile(
    rf"^\s*{NUMARA}\s+(?P<ad>.+?)\s+(?P<tur>purchase|sale|exchange)(?:\s*\(partial\))?\s+"
    r"(?P<tarih>\d{1,2}\s?/\s?\d{1,2}\s?/\s?\d{4})\s+(?P<tutar>Over \$[\d,]+|\$[\d,]+\s*-\s*\$[\d,]+)",
    re.IGNORECASE,
)
# Hesap başlıkları: "INVESTMENT ACCOUNT #7" ya da değeri olmayan üst kalem
# ("4. Charles Schwab Brokerage Account #1 No")
HESAP = re.compile(r"^\s*(INVESTMENT ACCOUNT ?#\s?\d+)\s*$", re.IGNORECASE)
UST_KALEM = re.compile(r"^\s*[\dIl]+\.\s+(?P<ad>.+?)\s+(?:No|Yes|N/A|NIA)\s*$")
BOLUM = re.compile(r"Part (\d+):")

# Bu oranın üzerinde tahvil / hisse dışı kalem içeren hesap tahvil hesabıdır
TAHVIL_HESABI_ORANI = 0.35


def tutar(metin):
    """'$15,001 - $50,000' -> (15001, 50000); 'Over $50,000,000' -> (50000001, 50000001)"""
    sayilar = [int(s.replace(",", "")) for s in re.findall(r"\$([\d,]+)", metin)]
    if not sayilar:
        return None, None
    if metin.lower().startswith("over"):
        return sayilar[0] + 1, sayilar[0] + 1
    return sayilar[0], sayilar[-1]


def metni_cikar(pdf_icerigi):
    with pdfplumber.open(io.BytesIO(pdf_icerigi)) as pdf:
        return [sayfa.extract_text() or "" for sayfa in pdf.pages]


def ayristir(sayfalar):
    """Varlık ve işlem satırları (hesaplarıyla birlikte)."""
    varliklar, islemler = [], []
    bolum, hesap = None, "Genel"
    for metin in sayfalar:
        for satir in metin.splitlines():
            m = BOLUM.search(satir)
            if m:
                bolum = int(m.group(1))
                continue
            m = HESAP.match(satir)
            if m:
                hesap = re.sub(r"\s+", " ", m.group(1).upper().replace("#", " #")).replace("# ", "#")
                continue
            if bolum in (2, 5, 6):
                m = VARLIK.match(satir)
                if m:
                    alt, ust = (None, None) if m.group(2).startswith("None") else tutar(m.group(2))
                    if alt:                       # 'None (or less than $1,001)': değeri yok, atlanır
                        varliklar.append({"hesap": hesap, "ad": m.group("ad").strip(),
                                          "alt": alt, "ust": ust, "bolum": bolum})
                    continue
                m = UST_KALEM.match(satir)
                if m and bolum in (2, 5):
                    hesap = m.group("ad").strip()[:80]
            elif bolum == 7:
                m = ISLEM.match(satir)
                if m and m.group("tur").lower() != "exchange":
                    ay, gun, yil = re.sub(r"\s", "", m.group("tarih")).split("/")
                    alt, ust = tutar(m.group("tutar"))
                    islemler.append({
                        "hesap": hesap, "ad": m.group("ad").strip(),
                        "islem": "buy" if m.group("tur").lower() == "purchase" else "sell",
                        "tarih": f"{yil}-{int(ay):02d}-{int(gun):02d}", "alt": alt, "ust": ust,
                    })
    return varliklar, islemler


def tahvil_hesaplari(varliklar):
    """Kalemlerinin çoğu tahvil, mevduat ya da şirket payı olan hesaplar."""
    toplam, hisse_disi = Counter(), Counter()
    for v in varliklar:
        toplam[v["hesap"]] += 1
        if v["ad"].lstrip().startswith("***") or HISSE_DEGIL.search(v["ad"]):
            hisse_disi[v["hesap"]] += 1
    return {h for h in toplam if toplam[h] >= 10 and hisse_disi[h] / toplam[h] > TAHVIL_HESABI_ORANI}


def isle(conn, kisi, adres, eslestirici):
    pdf = requests.get(adres, headers={"User-Agent": "Mozilla/5.0 PiyasaKaydi"}, timeout=300).content
    sayfalar = metni_cikar(pdf)
    varliklar, islemler = ayristir(sayfalar)
    tahvil = tahvil_hesaplari(varliklar)

    for liste in (varliklar, islemler):
        for k in liste:
            if k["hesap"] in tahvil:
                k["ticker"], k["eslesme"] = None, "tahvil_hesabi"
            else:
                k["ticker"], k["eslesme"] = eslestirici.bul(k["ad"])
                k["eslesme"] = k["eslesme"] or "elendi"
            k["sirket"] = eslestirici.resmi_ad(k["ticker"], k["ad"]) if k["ticker"] else None

    conn.execute("DELETE FROM yurutme_varlik WHERE kisi = ?", (kisi,))
    conn.execute("DELETE FROM yurutme_islem WHERE kisi = ?", (kisi,))
    conn.executemany(
        "INSERT INTO yurutme_varlik (kisi, hesap, ad, ticker, alt, ust, eslesme, rapor, sirket) VALUES (?,?,?,?,?,?,?,?,?)",
        [(kisi, v["hesap"], v["ad"], v["ticker"], v["alt"], v["ust"], v["eslesme"], adres, v["sirket"])
         for v in varliklar],
    )
    conn.executemany(
        "INSERT INTO yurutme_islem (kisi, hesap, ad, ticker, islem, tarih, alt, ust, eslesme, rapor, sirket) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [(kisi, i["hesap"], i["ad"], i["ticker"], i["islem"], i["tarih"], i["alt"], i["ust"],
          i["eslesme"], adres, i["sirket"]) for i in islemler],
    )
    conn.execute(
        "INSERT OR REPLACE INTO yurutme_rapor (adres, kisi, sayfa, islenme) VALUES (?, ?, ?, ?)",
        (adres, kisi, len(sayfalar), datetime.now(UTC).isoformat()),
    )
    conn.commit()

    eslenen = sum(1 for v in varliklar if v["ticker"])
    print(f"  {kisi}: {len(sayfalar)} sayfa, {len(varliklar)} değerli varlık ({eslenen} hisse/fon), "
          f"{len(islemler)} işlem ({sum(1 for i in islemler if i['ticker'])} hisse/fon); "
          f"tahvil hesabı: {', '.join(sorted(tahvil)) or 'yok'}", flush=True)


def main():
    yeniden = "--yeniden" in sys.argv[1:]
    init_db()
    conn = get_connection()

    raporlar = conn.execute(
        """SELECT kisi, adres FROM yurutme_bildirimi b
           WHERE tur = 'yillik' AND tarih = (SELECT MAX(tarih) FROM yurutme_bildirimi
                                              WHERE kisi = b.kisi AND tur = 'yillik')"""
    ).fetchall()
    islenmis = {s["adres"] for s in conn.execute("SELECT adres FROM yurutme_rapor")}

    bekleyen = [r for r in raporlar if yeniden or r["adres"] not in islenmis]
    if not bekleyen:
        print("Yeni yıllık bildirim yok.")
        return

    eslestirici = Eslestirici()
    for r in bekleyen:
        isle(conn, r["kisi"], r["adres"], eslestirici)
    conn.close()


if __name__ == "__main__":
    main()

