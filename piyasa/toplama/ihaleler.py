"""
Devlet sözleşmeleri: ABD federal hükümetinin şirketlere bağladığı paralar
(USAspending.gov, ücretsiz ve anahtarsız API).

Sözleşmenin toplam değeri değil, tek tek "yükümlülük işlemleri" alınır: bir
kurumun belirli bir gün şirkete bağladığı yeni para (yeni sözleşme ya da
mevcut sözleşmeye ek). Böylece "siyasetçi hisseyi aldı, birkaç hafta sonra
şirkete şu kadar milyon dolarlık sözleşme verildi" sorusu cevaplanabilir.

Hangi şirketler: siyasetçilerin 2024'ten beri işlem yaptığı hisseler. Şirket
adıyla aranır; alıcı adı şirket adıyla başlamayan sonuçlar (adı benzeyen başka
şirketler) elenir. Her şirket için son yılların en büyük işlemleri (en az
1 milyon dolar) saklanır.

Çalıştırmak için:  python -m piyasa ihaleler [--hepsi]
  Varsayılan: hiç taranmamış şirketler + en eski taranan 50 şirket.
  --hepsi: bütün şirketler yeniden taranır.
"""

import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, date, datetime

import requests

from piyasa.bicim import sirket_gorunen_ad
from piyasa.kurallar import GECERLI_KOD, IHALE_BASLANGIC, TEMIZ
from piyasa.veritabani import get_connection, init_db

API = "https://api.usaspending.gov/api/v2/search/spending_by_transaction/"
BASLANGIC = IHALE_BASLANGIC
ASGARI_TUTAR = 1_000_000
ADET = 60                     # şirket başına en büyük işlem sayısı
PARALEL = 3
GUNLUK_YENILEME = 50
SOZLESME_TURLERI = ["A", "B", "C", "D"]     # sözleşme ve sipariş türleri (hibe ve kredi değil)

# Arama için anlamsız ya da çok genel ad parçaları
GENEL_ILK_KELIMELER = {"THE", "FIRST", "GENERAL", "AMERICAN", "UNITED", "INTERNATIONAL", "NATIONAL",
                       "GLOBAL", "APPLIED", "ADVANCED", "DIGITAL", "NEW", "UNIVERSAL", "CENTRAL"}


def normal(ad):
    return re.sub(r"[^A-Z0-9 ]", " ", (ad or "").upper()).split()


SIRKET_EKLERI = {"INC", "CORP", "CORPORATION", "CO", "COMPANY", "LLC", "LTD", "LP", "PLC", "INCORPORATED",
                 "HOLDINGS", "GROUP", "USA", "US", "THE"}


def ad_uyuyor_mu(alici, arama_adi):
    """
    Alıcı adı şirket adıyla başlıyor mu? 'PALANTIR USG INC' ~ 'Palantir Technologies'.
    Genel ilk kelimeli adlarda ilk iki kelime aranır ('GENERAL DYNAMICS').
    Tek kelimelik adlarda devamı yalnızca şirket eki olabilir: 'APPLE INC' evet,
    'APPLE HOSPITALITY' hayır.
    """
    a, s = normal(alici), normal(arama_adi)
    if not a or not s:
        return False
    gerek = s[:2] if s[0] in GENEL_ILK_KELIMELER or len(s[0]) < 4 else s[:1]
    if a[:len(gerek)] != gerek:
        return False
    if len(s) == 1:
        return all(k in SIRKET_EKLERI for k in a[1:])
    return True


def sirketler(conn, hepsi=False):
    """[(ticker, arama adı)] — taranacak şirketler, önce hiç taranmamışlar."""
    adlar = {}
    for s in conn.execute(
        f"""SELECT ticker, MAX(COALESCE(company, asset_name)) AS ad FROM transactions
            WHERE chamber IS NOT NULL AND transaction_date >= ? AND {TEMIZ} AND {GECERLI_KOD}
            GROUP BY ticker""",
        (BASLANGIC,),
    ):
        ad = sirket_gorunen_ad(s["ad"])
        if ad and len(ad) >= 3:
            adlar[s["ticker"]] = ad
    taranan = {s["ticker"]: s["guncelleme"] for s in conn.execute("SELECT ticker, guncelleme FROM ihale_tarama")}
    if hepsi:
        return list(adlar.items())
    yeni = [(t, a) for t, a in adlar.items() if t not in taranan]
    eski = sorted((t for t in adlar if t in taranan), key=lambda t: taranan[t])[:GUNLUK_YENILEME]
    return yeni + [(t, adlar[t]) for t in eski]


def ara(arama_adi):
    cevap = requests.post(API, timeout=120, json={
        "filters": {
            "recipient_search_text": [arama_adi],
            "award_type_codes": SOZLESME_TURLERI,
            "time_period": [{"start_date": BASLANGIC, "end_date": date.today().isoformat()}],
        },
        "fields": ["Award ID", "Recipient Name", "Action Date", "Transaction Amount", "Awarding Agency",
                   "Awarding Sub Agency", "Transaction Description", "generated_internal_id", "Mod"],
        "sort": "Transaction Amount", "order": "desc", "limit": ADET, "page": 1,
    })
    cevap.raise_for_status()
    return cevap.json().get("results", [])


def ayikla(ticker, arama_adi, sonuclar):
    kayitlar = []
    for r in sonuclar:
        tutar = r.get("Transaction Amount") or 0
        if tutar < ASGARI_TUTAR or not ad_uyuyor_mu(r.get("Recipient Name"), arama_adi):
            continue
        kimlik = f'{r.get("generated_internal_id")}|{r.get("Mod") or "0"}|{r.get("Action Date")}'
        kayitlar.append((
            kimlik, ticker, r.get("Recipient Name"), r.get("Awarding Agency"), r.get("Awarding Sub Agency"),
            tutar, r.get("Action Date"), (r.get("Transaction Description") or "").strip()[:300] or None,
            f'https://www.usaspending.gov/award/{r.get("generated_internal_id")}',
        ))
    return kayitlar


def tara(ticker, arama_adi):
    for deneme in range(3):
        try:
            return ticker, arama_adi, ayikla(ticker, arama_adi, ara(arama_adi))
        except Exception:
            time.sleep(5 * (deneme + 1))
    return ticker, arama_adi, None


def main():
    init_db()
    with closing(get_connection()) as conn:
        liste = sirketler(conn, hepsi="--hepsi" in sys.argv[1:])
        print(f"Taranacak şirket: {len(liste)}", flush=True)
        toplam = 0
        with ThreadPoolExecutor(PARALEL) as havuz:
            for n, (ticker, ad, kayitlar) in enumerate(havuz.map(lambda x: tara(*x), liste), 1):
                if kayitlar is None:
                    continue                  # ağ hatası: sonraki çalıştırmada yeniden denenir
                conn.execute("DELETE FROM ihale WHERE ticker = ?", (ticker,))
                conn.executemany("INSERT OR REPLACE INTO ihale VALUES (?,?,?,?,?,?,?,?,?)", kayitlar)
                conn.execute("INSERT OR REPLACE INTO ihale_tarama VALUES (?, ?, ?, ?)",
                             (ticker, ad, len(kayitlar), datetime.now(UTC).isoformat()))
                conn.commit()
                toplam += len(kayitlar)
                if n % 50 == 0:
                    print(f"  {n}/{len(liste)}  sözleşme işlemi: {toplam}", flush=True)
        sirket = conn.execute("SELECT COUNT(DISTINCT ticker) FROM ihale").fetchone()[0]
    print(f"Bitti. Bu turda {toplam} sözleşme işlemi; sözleşmesi olan şirket: {sirket}")


if __name__ == "__main__":
    main()
