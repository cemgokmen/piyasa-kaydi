"""
Hisse ve emtia fiyatları, dönemsel değişimler ve hacim (Yahoo Finance, yfinance ile).

Sonuçlar 15 dakika bellekte tutulur; aynı hisse sayfası tekrar açıldığında
Yahoo'ya yeniden gidilmez.
"""

import re

import pandas as pd
import yfinance as yf

from piyasa.onbellek import sureli

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


def _seri(tablo, geri, ornekleme):
    """
    Grafik serisi: [tarih, kapanış] ya da hacim varsa [tarih, kapanış, hacim].
    Haftalık örneklemede kapanış haftanın sonuncusu, hacim haftanın toplamıdır.
    """
    parca = tablo[tablo.index >= tablo.index[-1] - geri]
    if ornekleme:
        haftalik = parca.resample(ornekleme).agg({"Close": "last", "Volume": "sum"}).dropna()
        # Son günü de koru ki grafik bugünle bitsin
        parca = pd.concat([haftalik[haftalik.index < parca.index[-1]], parca.iloc[-1:]])
    hacimli = parca["Volume"].sum() > 0
    return [
        [t.strftime("%Y-%m-%d"), round(float(k), 4)] + ([int(h)] if hacimli else [])
        for t, k, h in zip(parca.index, parca["Close"], parca["Volume"], strict=True)
    ]


def _hacim_ozeti(tablo):
    """
    Son tamamlanmış işlem gününün hacmi ve 20 günlük ortalamaya oranı.
    Bugünün satırı gün içinde eksik hacim taşıyabileceği için atlanır.
    """
    hacim = tablo["Volume"]
    if hacim.sum() <= 0:
        return None
    if tablo.index[-1].date() >= pd.Timestamp.today().date() and len(hacim) > 21:
        hacim = hacim.iloc[:-1]
    son = int(hacim.iloc[-1])
    ortalama = float(hacim.iloc[-21:-1].mean())
    return {
        "son": son,
        "tarih": hacim.index[-1].strftime("%Y-%m-%d"),
        "ortalama": round(ortalama),
        "oran": round(son / ortalama, 3) if ortalama else None,
    }


def _indir(kod):
    # 10 yıllık değişim için 10 yıl öncesinin kapanışı da gerekli: iki hafta pay
    baslangic = (pd.Timestamp.today() - pd.DateOffset(years=10, weeks=2)).strftime("%Y-%m-%d")
    gecmis = yf.Ticker(kod).history(start=baslangic, interval="1d", auto_adjust=True)
    if gecmis.empty:
        return None

    tablo = gecmis[["Close", "Volume"]].dropna(subset=["Close"])
    tablo.index = tablo.index.tz_localize(None)
    if len(tablo) < 2:
        return None
    kapanis = tablo["Close"]

    return {
        "kod": kod,
        "fiyat": round(float(kapanis.iloc[-1]), 4),
        "tarih": kapanis.index[-1].strftime("%Y-%m-%d"),
        "degisimler": [
            {"anahtar": a, "etiket": e, "oran": _degisim(kapanis, g)}
            for a, e, g in DEGISIM_DONEMLERI
        ],
        "hacim": _hacim_ozeti(tablo),
        "seriler": {a: _seri(tablo, g, o) for a, g, o in GRAFIK_ARALIKLARI},
    }


@sureli(ONBELLEK_SURESI)
def _bilgi(kod):
    try:
        return _indir(kod)
    except Exception:
        return None


def fiyat_bilgisi(ticker, ham=False):
    """
    Fiyat, değişimler, hacim ve grafik serileri; veri yoksa None. 15 dk önbellekli.
    ham=True: kod olduğu gibi kullanılır (emtia ve endeks kodları: 'GC=F', 'DX-Y.NYB').
    """
    kod = ticker if ham else yahoo_kodu(ticker)
    return _bilgi(kod) if kod else None
