"""Matriks, Teknik Analiz Modülleri (KHN) Eğitim Dokümanı, 2020. Notlar: analiz_ajani/notlar/matriks-2020.md"""

import pandas as pd

from piyasa.analiz.ajan.kural import Kaynak, asagi_kesti, kural, sinyal, yukari_kesti

MATRIKS = Kaynak("matriks2020", "Matriks 2020", "Matriks, Teknik Analiz Modülleri (KHN Menüleri) Eğitim Dokümanı, 2020",
                 "analiz_ajani/notlar/matriks-2020.md")


def _kesisim(hizli, yavas):
    return sinyal(yukari_kesti(hizli, yavas), asagi_kesti(hizli, yavas))


def _ort(b, n):
    return b.df["Close"].rolling(n).mean()


def _ema(b, n):
    return b.df["Close"].ewm(span=n, adjust=False, min_periods=n).mean()


def _fiyat_osilatoru(b):
    # Doküman periyot vermez: 10/20 üssel ortalama ve 9 günlük ortalaması varsayımdır
    p = (_ema(b, 10) - _ema(b, 20)) / _ema(b, 20)
    return p, p.rolling(9).mean()


@kural("matriks.mov_5_22", "5 ve 22 günlük ortalama kesişimi", MATRIKS, "37", "trend", 20,
       "5 günlük ortalama 22 günlüğün üstüne çıktı.", "5 günlük ortalama 22 günlüğün altına indi.", gecerlilik=3)
def mov_5_22(b):
    return _kesisim(_ort(b, 5), _ort(b, 22))


@kural("matriks.mov_3_10", "3 ve 10 günlük ortalama kesişimi", MATRIKS, "58–59", "trend", 10,
       "3 günlük ortalama 10 günlüğün üstüne çıktı.", "3 günlük ortalama 10 günlüğün altına indi.", gecerlilik=2)
def mov_3_10(b):
    return _kesisim(_ort(b, 3), _ort(b, 10))


@kural("matriks.ema_5_14", "5 ve 14 günlük üssel ortalama kesişimi", MATRIKS, "34", "trend", 10,
       "5 günlük üssel ortalama 14 günlüğün üstüne çıktı.", "5 günlük üssel ortalama 14 günlüğün altına indi.", gecerlilik=2)
def ema_5_14(b):
    return _kesisim(_ema(b, 5), _ema(b, 14))


@kural("matriks.ema_5_14_gecikmeli", "5/14 kesişimi, 2 gün beklenerek", MATRIKS, "34–35", "trend", 10,
       "5/14 kesişimi 2 gün önce yukarı oldu: sinyalin kalıcılığı beklendi.",
       "5/14 kesişimi 2 gün önce aşağı oldu: sinyalin kalıcılığı beklendi.", gecerlilik=2)
def ema_5_14_gecikmeli(b):
    return _kesisim(_ema(b, 5), _ema(b, 14)).shift(2).fillna(0.0)


@kural("matriks.fiyat_ho5", "Fiyat, 5 günlük ortalamayı kesti", MATRIKS, "83", "trend", 10,
       "Kapanış 5 günlük ortalamanın üstüne çıktı.", "Kapanış 5 günlük ortalamanın altına indi.", gecerlilik=1)
def fiyat_ho5(b):
    return _kesisim(b.df["Close"], _ort(b, 5))


@kural("matriks.macd", "MACD ve sinyal çizgisi kesişimi", MATRIKS, "37", "trend", 20,
       "MACD sinyal çizgisinin üstüne çıktı.", "MACD sinyal çizgisinin altına indi.", gecerlilik=2)
def macd(b):
    return _kesisim(b.g["macd"], b.g["macd_sinyal"])


@kural("matriks.fiyat_osilatoru", "Fiyat osilatörü kesişimi", MATRIKS, "37", "trend", 10,
       "Fiyat osilatörü kendi ortalamasının üstüne çıktı.", "Fiyat osilatörü kendi ortalamasının altına indi.", gecerlilik=2)
def fiyat_osilatoru(b):
    return _kesisim(*_fiyat_osilatoru(b))


@kural("matriks.bes_gosterge", "Beş gösterge aynı yönde", MATRIKS, "37, 47", "trend", 20,
       "5/22 ortalama, RSI, yavaş stokastik, fiyat osilatörü ve MACD ilk kez birlikte AL durumunda.",
       "5/22 ortalama, RSI, yavaş stokastik, fiyat osilatörü ve MACD ilk kez birlikte SAT durumunda.")
def bes_gosterge(b):
    p, ps = _fiyat_osilatoru(b)
    rsi = b.g["rsi"]
    # RSI: 30'u yukarı kesince AL, 70'i aşağı kesince SAT durumu; sonraki sinyale kadar sürer
    rsi_olay = sinyal(yukari_kesti(rsi, 30), asagi_kesti(rsi, 70))
    rsi_durum = rsi_olay.where(rsi_olay != 0).ffill().fillna(0.0)
    durumlar = [
        (_ort(b, 5) > _ort(b, 22), _ort(b, 5) < _ort(b, 22)),
        (rsi_durum > 0, rsi_durum < 0),
        (b.g["yavas_k"] > b.g["yavas_d"], b.g["yavas_k"] < b.g["yavas_d"]),
        (p > ps, p < ps),
        (b.g["macd"] > b.g["macd_sinyal"], b.g["macd"] < b.g["macd_sinyal"]),
    ]
    hepsi_al = pd.concat([a for a, _ in durumlar], axis=1).all(axis=1)
    hepsi_sat = pd.concat([s for _, s in durumlar], axis=1).all(axis=1)
    return sinyal(hepsi_al & ~hepsi_al.shift(1, fill_value=False), hepsi_sat & ~hepsi_sat.shift(1, fill_value=False))
