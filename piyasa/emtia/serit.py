"""
Sayfanın üstündeki piyasa şeridi: Türk yatırımcının ilk baktığı göstergeler.
Fiyatlar anlıktır (1 dakikalık önbellek); sayfa açıkken dakikada bir yenilenir.
"""

from concurrent.futures import ThreadPoolExecutor

from piyasa import fiyat
from piyasa.emtia.tanimlar import ONS_GRAM
from piyasa.onbellek import sureli

# (ad, Yahoo kodu, birim, sitede bağlantı, ondalık basamak)
GOSTERGELER = [
    ("BIST 100", "XU100.IS", "", None, 0),
    ("S&P 500", "^GSPC", "", None, 0),
    ("Nasdaq", "^IXIC", "", None, 0),
    ("Dolar/TL", "TRY=X", "₺", None, 2),
    ("Euro/TL", "EURTRY=X", "₺", None, 2),
    ("Ons altın", "GC=F", "$", "/emtia/altin", 0),
    ("Brent", "BZ=F", "$", "/emtia/brent", 2),
    ("Bitcoin", "BTC-USD", "$", None, 0),
]


def _gunluk(bilgi):
    return bilgi["degisim"]


@sureli(fiyat.ANLIK_SURESI)
def serit():
    kodlar = [k for _, k, *_ in GOSTERGELER]
    with ThreadPoolExecutor(len(kodlar)) as havuz:
        bilgiler = dict(zip(kodlar, havuz.map(lambda k: fiyat.anlik_fiyat(k, ham=True), kodlar), strict=True))

    ogeler = []
    for ad, kod, birim, adres, basamak in GOSTERGELER:
        b = bilgiler.get(kod)
        if b:
            ogeler.append({"ad": ad, "kod": kod, "deger": b["fiyat"], "birim": birim, "adres": adres,
                           "basamak": basamak, "degisim": _gunluk(b)})

    # Gram altın: ons altın × dolar/TL ÷ 31,10
    altin, kur = bilgiler.get("GC=F"), bilgiler.get("TRY=X")
    if altin and kur:
        a, k = _gunluk(altin), _gunluk(kur)
        ogeler.insert(5, {
            "ad": "Gram altın", "kod": "GRAM", "deger": altin["fiyat"] * kur["fiyat"] / ONS_GRAM, "birim": "₺",
            "adres": "/emtia/altin", "basamak": 2,
            "degisim": None if a is None or k is None else (1 + a) * (1 + k) - 1,
        })
    return ogeler
