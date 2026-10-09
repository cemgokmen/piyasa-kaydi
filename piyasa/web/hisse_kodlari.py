"""
Metinde (haber başlıkları) geçen hisse kodlarını tanır: 'THYAO, TUPRS ve ASELS zirvede'
-> [('THYAO', '/bist/THYAO'), ...]. Başlığın kendisi dış bağlantı olduğu için kodlar
başlığın altında ayrı etiketler olarak gösterilir.

  - Borsa İstanbul: büyük harfle yazılmış 4-5 harflik BIST kodları
  - ABD: parantez içinde ya da $ ile yazılmış kodlar ('(NVDA)', '$AAPL'), sitede sayfası olanlar
"""

import re
from contextlib import closing

from piyasa.kurallar import TEMIZ
from piyasa.onbellek import sureli
from piyasa.veritabani import get_connection

# Haberlerde büyük harfle sık geçen, hisse kodu sanılmaması gereken kelimeler
KARISANLAR = {"BIST", "SPK", "KAP", "TCMB", "ABD", "FED", "OPEC", "NATO", "IMF", "TÜİK", "TUIK", "BDDK", "MSCI",
              "CEO", "CFO", "ETF", "HALKA", "ARZ", "YENİ", "SON", "DOLAR", "EURO", "ALTIN", "BORSA", "HİSSE",
              "GÜNÜN", "NOT", "TEMETTÜ", "BEDELSİZ", "BEDELLİ", "GOLD", "USD", "EUR", "TL", "TRY", "AI", "GPU",
              "NYSE", "SEC", "USA", "UK", "AB", "BM", "AKP", "CHP", "MHP", "IYI", "DEM", "THY"}
BIST_DESEN = re.compile(r"(?<![\w$])([A-ZÇĞİÖŞÜ0-9]{4,5})(?![\w])")
ABD_DESEN = re.compile(r"(?:\(|\$)([A-Z]{1,5}(?:[.-][A-Z])?)(?:\)|\b)")


@sureli(3600)
def _kodlar():
    with closing(get_connection()) as conn:
        bist = {r[0] for r in conn.execute("SELECT kod FROM bist_sirket WHERE ana_sektor IS NOT NULL OR xu100 = 1")}
        abd = {r[0] for r in conn.execute(f"SELECT DISTINCT ticker FROM transactions WHERE {TEMIZ}")}
    return bist, abd


def hisse_kodlari(metin, en_fazla=5):
    if not metin:
        return []
    try:
        bist, abd = _kodlar()
    except Exception:
        return []
    bulunan = []
    for kod in BIST_DESEN.findall(metin):
        if kod in bist and kod not in KARISANLAR:
            bulunan.append((kod, f"/bist/{kod}"))
    for kod in ABD_DESEN.findall(metin):
        kod = kod.replace(".", "-")
        if kod in abd and kod not in KARISANLAR and kod not in dict(bulunan):
            bulunan.append((kod, f"/hisse/{kod}"))
    return list(dict(bulunan).items())[:en_fazla]
