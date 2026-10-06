"""
Hisse fiyatları ve dönemsel değişimler (Yahoo Finance, yfinance ile).

Sonuçlar 15 dakika bellekte tutulur; aynı hisse sayfası tekrar açıldığında
Yahoo'ya yeniden gidilmez.
"""

import re
import threading
import time

import pandas as pd
import yfinance as yf

ONBELLEK_SURESI = 15 * 60

# (anahtar, etiket, geriye gidilecek süre). 1 gün: bir önceki kapanışa göre.
DEGISIM_DONEMLERI = [
    ("1g", "1 gün", None),
    ("1h", "1 hafta", pd.DateOffset(weeks=1)),
    ("1a", "1 ay", pd.DateOffset(months=1)),
    ("1y", "1 yıl", pd.DateOffset(years=1)),
    ("5y", "5 yıl", pd.DateOffset(years=5)),
    ("10y", "10 yıl", pd.DateOffset(years=10)),
]

# Grafik aralıkları: (anahtar, süre, örnekleme). Uzun aralıklar haftalık
# örneklenir; tarayıcıya giden veri küçük kalır.
GRAFIK_ARALIKLARI = [
    ("1a", pd.DateOffset(months=1), None),
    ("1y", pd.DateOffset(years=1), None),
    ("5y", pd.DateOffset(years=5), "W-FRI"),
    ("10y", pd.DateOffset(years=10), "W-FRI"),
]

_onbellek = {}
_kilit = threading.Lock()


def yahoo_kodu(ticker):
    """
    Bildirimlerdeki kodu Yahoo biçimine çevirir.
    'BRK.B' -> 'BRK-B'; 'LEN, LEN.B' gibi çoklu kodlarda ilki alınır.
    """
    ilk = re.split(r"[,\s/]+", (ticker or "").strip())[0]
    return ilk.replace(".", "-").upper()


def _degisim(kapanis, geri):
    """Son kapanışın, 'geri' kadar önceki kapanışa göre oransal değişimi."""
    son = kapanis.iloc[-1]
    if geri is None:
        onceki = kapanis.iloc[-2] if len(kapanis) > 1 else None
    else:
        hedef = kapanis.index[-1] - geri
        # Geçmiş bu tarihe kadar uzanmıyorsa (yeni halka arz) değişim yok
        if kapanis.index[0] > hedef + pd.Timedelta(days=7):
            return None
        onceki = kapanis[:hedef].iloc[-1] if len(kapanis[:hedef]) else None
    if not onceki:
        return None
    return float(son / onceki - 1)


def _seri(kapanis, geri, ornekleme):
    parca = kapanis[kapanis.index >= kapanis.index[-1] - geri]
    if ornekleme:
        # Haftalık örneklemede son günü de koru ki grafik bugünle bitsin
        haftalik = parca.resample(ornekleme).last().dropna()
        parca = pd.concat([haftalik[haftalik.index < parca.index[-1]], parca.iloc[-1:]])
    return [[t.strftime("%Y-%m-%d"), round(float(v), 4)] for t, v in parca.items()]


def _indir(kod):
    # 10 yıllık değişim için 10 yıl öncesinin kapanışı da gerekli: iki hafta pay
    baslangic = (pd.Timestamp.today() - pd.DateOffset(years=10, weeks=2)).strftime("%Y-%m-%d")
    gecmis = yf.Ticker(kod).history(start=baslangic, interval="1d", auto_adjust=True)
    if gecmis.empty:
        return None

    kapanis = gecmis["Close"].dropna()
    kapanis.index = kapanis.index.tz_localize(None)
    if len(kapanis) < 2:
        return None

    return {
        "kod": kod,
        "fiyat": round(float(kapanis.iloc[-1]), 4),
        "tarih": kapanis.index[-1].strftime("%Y-%m-%d"),
        "degisimler": [
            {"anahtar": a, "etiket": e, "oran": _degisim(kapanis, g)}
            for a, e, g in DEGISIM_DONEMLERI
        ],
        "seriler": {a: _seri(kapanis, g, o) for a, g, o in GRAFIK_ARALIKLARI},
    }


def fiyat_bilgisi(ticker):
    """Fiyat, değişimler ve grafik serileri; veri yoksa None."""
    kod = yahoo_kodu(ticker)
    if not kod:
        return None

    simdi = time.time()
    with _kilit:
        kayit = _onbellek.get(kod)
        if kayit and simdi - kayit[0] < ONBELLEK_SURESI:
            return kayit[1]

    try:
        bilgi = _indir(kod)
    except Exception:
        bilgi = None

    with _kilit:
        _onbellek[kod] = (simdi, bilgi)
    return bilgi
