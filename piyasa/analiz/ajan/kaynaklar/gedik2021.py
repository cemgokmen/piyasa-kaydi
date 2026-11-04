"""Gedik Yatırım, Teknik Analiz Eğitim Sunumu, Şubat 2021. Notlar: analiz_ajani/notlar/gedik-2021.md"""

import numpy as np
import pandas as pd

from piyasa.analiz.ajan.kural import Kaynak, asagi_kesti, kural, sinyal, yukari_kesti

GEDIK = Kaynak("gedik2021", "Gedik 2021", "Gedik Yatırım, Teknik Analiz Eğitim Sunumu, Şubat 2021",
               "analiz_ajani/notlar/gedik-2021.md")
TUZAK_GUN = 10


def _kesisim(hizli, yavas):
    return sinyal(yukari_kesti(hizli, yavas), asagi_kesti(hizli, yavas))


@kural("gedik.fiyat_ho50", "Fiyat, 50 günlük ortalamayı kesti", GEDIK, "22–23", "trend", 20,
       "Fiyat 50 günlük ortalamanın üstüne çıktı.", "Fiyat 50 günlük ortalamanın altına indi.", gecerlilik=3)
def fiyat_ho50(b):
    return _kesisim(b.g["close"], b.g["sma50"])


@kural("gedik.fiyat_ho200", "Fiyat, 200 günlük ortalamayı kesti", GEDIK, "22–23", "trend", 60,
       "Fiyat 200 günlük ortalamanın üstüne çıktı.", "Fiyat 200 günlük ortalamanın altına indi.")
def fiyat_ho200(b):
    return _kesisim(b.g["close"], b.g["sma200"])


@kural("gedik.ho_20_50", "20 ve 50 günlük ortalama kesişimi", GEDIK, "22–23", "trend", 20,
       "20 günlük ortalama 50 günlüğün üstüne çıktı.", "20 günlük ortalama 50 günlüğün altına indi.")
def ho_20_50(b):
    return _kesisim(b.g["sma20"], b.g["sma50"])


@kural("gedik.ho_50_200", "50 ve 200 günlük ortalama kesişimi", GEDIK, "22–23", "trend", 60,
       "50 günlük ortalama 200 günlüğün üstüne çıktı.", "50 günlük ortalama 200 günlüğün altına indi.", gecerlilik=10)
def ho_50_200(b):
    return _kesisim(b.g["sma50"], b.g["sma200"])


@kural("gedik.basit_ussel", "Basit ve üssel ortalama kesişimi", GEDIK, "23", "trend", 10,
       "20 günlük üssel ortalama basit ortalamanın üstüne çıktı.", "20 günlük üssel ortalama basit ortalamanın altına indi.", gecerlilik=3)
def basit_ussel(b):
    return _kesisim(b.g["ema20"], b.g["sma20"])


@kural("gedik.hacimli_kirilis", "Hacimli trend çizgisi kırılışı", GEDIK, "21", "trend", 20,
       "Direnç çizgisi artan hacimle kırıldı.", "Destek çizgisi artan hacimle kırıldı.")
def hacimli_kirilis(b):
    olay = np.zeros(len(b.df))
    for c in b.cizgiler:
        if c["kirilis"] is not None and c["hacimli"]:
            olay[c["kirilis"]] = c["yon"]
    return pd.Series(olay, index=b.df.index)


@kural("gedik.tuzak", "Boğa ve ayı tuzağı", GEDIK, "21", "trend", 20,
       "Destek çizgisi kırıldı ama fiyat çizginin içine döndü: ayı tuzağı.",
       "Direnç çizgisi kırıldı ama fiyat çizginin içine döndü: boğa tuzağı.")
def tuzak(b):
    k = b.df["Close"].to_numpy()
    olay = np.zeros(len(k))
    for c in b.cizgiler:
        if c["kirilis"] is None:
            continue
        for g in range(c["kirilis"] + 1, min(len(k), c["kirilis"] + 1 + TUZAK_GUN)):
            if (k[g] - c["cizgi"](g)) * c["yon"] < 0:
                olay[g] = -c["yon"]
                break
    return pd.Series(olay, index=b.df.index)


@kural("gedik.fibonacci", "Fibonacci düzeltmesinden dönüş", GEDIK, "25–28", "trend", 20,
       "Yükseliş salınımının %38,2–61,8 düzeltmesinden yukarı dönüldü.",
       "Düşüş salınımının %38,2–61,8 tepkisinden aşağı dönüldü.")
def fibonacci(b, pencere=126):
    yuksek, dusuk, c = b.df["High"], b.df["Low"], b.df["Close"]
    ust, alt = yuksek.rolling(pencere).max(), dusuk.rolling(pencere).min()
    yukari = yuksek.rolling(pencere).apply(np.argmax, raw=True) > dusuk.rolling(pencere).apply(np.argmin, raw=True)
    aralik = (ust - alt).replace(0, np.nan)
    duzeltme = ((ust - c) / aralik).where(yukari, (c - alt) / aralik)
    # Bölgeye girmiş fiyatın %38,2 sınırından geri çıkması (düzeltme oranı 0,382'nin altına iner)
    bolgede = duzeltme.shift(1).between(0.382, 0.618)
    donus = bolgede & (duzeltme < 0.382)
    return sinyal(donus & yukari & yukari.shift(1, fill_value=False), donus & ~yukari & ~yukari.shift(1, fill_value=True))
