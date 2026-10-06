"""
Hisse ve emtia fiyatları, dönemsel değişimler ve hacim (Yahoo Finance, yfinance ile).

İki katman vardır:
  fiyat_bilgisi  günlük kapanış geçmişi, değişimler, grafik (15 dk önbellek)
  anlik_fiyat    son işlem fiyatı ve seans durumu (1 dk önbellek). Ücretsizdir;
                 ABD hisselerinde gerçek zamanlı ya da birkaç dakika, bazı
                 borsa ve vadelilerde en çok 15-20 dakika gecikmelidir.
"""

import re

import pandas as pd
import yfinance as yf

from piyasa.ayarlar import VERI_DIZINI
from piyasa.onbellek import sureli

# yfinance saat dilimi önbelleğini proje klasöründe tut: arka planda
# (launchd) çalışırken kullanıcı önbellek klasörüne erişim sorun çıkarabiliyor
_YF_ONBELLEK = VERI_DIZINI / "yfinance_onbellek"
_YF_ONBELLEK.mkdir(parents=True, exist_ok=True)
yf.set_tz_cache_location(str(_YF_ONBELLEK))

ONBELLEK_SURESI = 15 * 60
ANLIK_SURESI = 60

# Yahoo seans durumu → sitede gösterilen ad
SEANS = {
    "REGULAR": "Piyasa açık",
    "PRE": "Seans öncesi", "PREPRE": "Piyasa kapalı",
    "POST": "Seans sonrası", "POSTPOST": "Piyasa kapalı",
    "CLOSED": "Piyasa kapalı",
}

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


def _oran(fiyat, onceki):
    return float(fiyat / onceki - 1) if fiyat and onceki else None


def _anlik_indir(kod):
    bilgi = yf.Ticker(kod).info or {}
    fiyat = bilgi.get("regularMarketPrice") or bilgi.get("currentPrice")
    onceki = bilgi.get("regularMarketPreviousClose") or bilgi.get("previousClose")
    zaman = bilgi.get("regularMarketTime")
    if not fiyat:
        hizli = yf.Ticker(kod).fast_info
        fiyat, onceki, zaman = hizli.last_price, hizli.previous_close, None
    if not fiyat:
        return None

    durum = bilgi.get("marketState")
    seans_disi = None
    for alan, etiket, durumlar in (("preMarketPrice", "Seans öncesi", ("PRE", "PREPRE")),
                                   ("postMarketPrice", "Seans sonrası", ("POST", "POSTPOST", "CLOSED"))):
        deger = bilgi.get(alan)
        if deger and durum in durumlar:
            seans_disi = {"etiket": etiket, "fiyat": round(float(deger), 4), "degisim": _oran(deger, fiyat)}
    return {
        "kod": kod,
        "fiyat": round(float(fiyat), 4),
        "onceki_kapanis": round(float(onceki), 4) if onceki else None,
        "degisim": _oran(fiyat, onceki),
        "zaman": zaman,                                  # Unix saniyesi (UTC)
        "durum": durum,
        "durum_etiket": SEANS.get(durum),
        "gecikme": bilgi.get("exchangeDataDelayedBy"),   # dakika; 0 gerçek zamanlı
        "seans_disi": seans_disi,
    }


@sureli(ANLIK_SURESI)
def _anlik(kod):
    try:
        return _anlik_indir(kod)
    except Exception:
        return None


def anlik_fiyat(ticker, ham=False):
    """Son işlem fiyatı, önceki kapanışa göre değişim ve seans durumu; 1 dk önbellekli."""
    kod = ticker if ham else yahoo_kodu(ticker)
    return _anlik(kod) if kod else None
