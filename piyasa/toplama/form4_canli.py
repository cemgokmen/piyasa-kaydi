"""
Gün içinde yayımlanan Form 4 bildirimleri (SEC "son bildirimler" akışı).

SEC'in günlük dizini ancak gün bitince yayımlanıyor; bu toplayıcı bildirimleri SEC'e
düştükten dakikalar sonra alır. Canlı güncelleme 15 dakikada bir çalıştırır.

Çalıştırmak için:  python -m piyasa form4-canli
"""

import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import requests

from piyasa.ayarlar import USER_AGENT
from piyasa.toplama.form4 import BEKLEME, bildirimi_coz, kaydet
from piyasa.veritabani import get_connection, init_db

AKIS = "https://www.sec.gov/cgi-bin/browse-edgar"
ATOM = {"a": "http://www.w3.org/2005/Atom"}
SAYFA = 100
EN_FAZLA_SAYFA = 4             # en yeni 400 kayıt (her bildirim akışta iki kez görünür)
ADRES = re.compile(r"/Archives/edgar/data/(\d+)/\d+/([\d-]+)-index\.htm")


def akis(baslangic=0):
    """[{numara, cik, sirket, tarih}] — yalnızca Form 4 (ve düzeltmesi 4/A), şirket ('Issuer') satırları."""
    cevap = requests.get(AKIS, params={"action": "getcurrent", "type": "4", "owner": "include",
                                       "start": baslangic, "count": SAYFA, "output": "atom"},
                         headers={"User-Agent": USER_AGENT}, timeout=30)
    cevap.raise_for_status()
    kayitlar = []
    for e in ET.fromstring(cevap.content).findall("a:entry", ATOM):
        baslik = e.findtext("a:title", default="", namespaces=ATOM)
        if not re.match(r"^4(/A)? - ", baslik) or "(Issuer)" not in baslik:
            continue
        m = ADRES.search(e.find("a:link", ATOM).get("href", ""))
        if not m:
            continue
        cik, numara = m.groups()
        sirket = re.sub(r"^4(/A)? - |\s*\(\d+\)\s*\(Issuer\)\s*$", "", baslik).strip()
        tarih = (e.findtext("a:updated", default="", namespaces=ATOM) or "")[:10]
        kayitlar.append({"numara": numara, "cik": cik, "sirket": sirket, "tarih": tarih})
    return kayitlar


def main():
    init_db()
    conn = get_connection()
    simdi = datetime.now(UTC).isoformat()
    gorulen, yeni = set(), []
    try:
        for sayfa in range(EN_FAZLA_SAYFA):
            liste = akis(sayfa * SAYFA)
            time.sleep(BEKLEME)
            for k in liste:
                if k["numara"] in gorulen:
                    continue
                gorulen.add(k["numara"])
                # Daha önce işlenmiş bildirim (günlük dizinden ya da önceki çalıştırmadan) atlanır
                if conn.execute("SELECT 1 FROM transactions WHERE source_id LIKE ? LIMIT 1",
                                (k["numara"] + "-%",)).fetchone() or \
                        conn.execute("SELECT 1 FROM form4_islenen WHERE numara = ?", (k["numara"],)).fetchone():
                    continue
                yeni.append(k)
            if not liste:
                break

        eklenen = 0
        for k in yeni:
            kayit = {"path": f"edgar/data/{k['cik']}/{k['numara']}.txt", "company": k["sirket"],
                     "filed_date": k["tarih"]}
            try:
                islemler = bildirimi_coz(kayit)
            except Exception as hata:
                print(f"  {k['numara']} alınamadı: {hata}", flush=True)
                time.sleep(BEKLEME)
                continue
            for islem in islemler:
                islem["fetched_at"] = simdi
                eklenen += kaydet(conn, islem)
            conn.execute("INSERT OR IGNORE INTO form4_islenen VALUES (?, ?)", (k["numara"], simdi))
            conn.commit()
            time.sleep(BEKLEME)
        print(f"  Gün içi Form 4: {len(yeni)} yeni bildirim, {eklenen} alım/satım işlemi eklendi", flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
