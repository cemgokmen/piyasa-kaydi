"""
Erdinç Altay, "Portföy Yönetiminde Karar Alma Aracı Olarak Teknik Analizin Kullanımı",
İstanbul Üniversitesi SBE yüksek lisans tezi, 1997. Notlar: analiz_ajani/notlar/altay-1997.md
"""

import numpy as np
import pandas as pd

from piyasa.analiz.ajan.kural import Kaynak, asagi_kesti, kural, sinyal, yukari_kesti
from piyasa.analiz.teknik.cizgiler import formasyon_olaylari

ALTAY = Kaynak("altay1997", "Altay 1997",
               "Erdinç Altay, Portföy Yönetiminde Karar Alma Aracı Olarak Teknik Analizin Kullanımı, İÜ SBE YL tezi, 1997",
               "analiz_ajani/notlar/altay-1997.md")


@kural("altay.stokastik", "Stokastik 20/80", ALTAY, "110–140", "osilator", 10,
       "Yavaş %K 20'yi yukarı kesti: aşırı satımdan çıkış.", "Yavaş %K 80'i aşağı kesti: aşırı alımdan çıkış.")
def stokastik(b):
    k = b.g["yavas_k"]
    return sinyal(yukari_kesti(k, 20), asagi_kesti(k, 80))


@kural("altay.stokastik_kesisim", "Stokastik %K–%D kesişimi", ALTAY, "110–140", "osilator", 10,
       "%K, %D'yi yukarı kesti.", "%K, %D'yi aşağı kesti.", gecerlilik=2)
def stokastik_kesisim(b):
    k, d = b.g["yavas_k"], b.g["yavas_d"]
    return sinyal(yukari_kesti(k, d), asagi_kesti(k, d))


@kural("altay.macd_sifir", "MACD kesişiminin yeri", ALTAY, "110–140", "trend", 20,
       "MACD sıfırın altında sinyal çizgisini yukarı kesti: güçlü AL.",
       "MACD sıfırın üstünde sinyal çizgisini aşağı kesti: güçlü SAT.")
def macd_sifir(b):
    m, s = b.g["macd"], b.g["macd_sinyal"]
    return sinyal(yukari_kesti(m, s) & (m < 0), asagi_kesti(m, s) & (m > 0))


@kural("altay.williams_trend", "Williams %R, trend yönünde", ALTAY, "110–140", "osilator", 10,
       "%R −80 altından döndü ve MACD sıfırın üstünde: yalnızca trend yönünde alınan AL.",
       "%R −20 üstünden döndü ve MACD sıfırın altında: yalnızca trend yönünde alınan SAT.")
def williams_trend(b):
    r, m = b.g["williams"], b.g["macd"]
    return sinyal(yukari_kesti(r, -80) & (m > 0), asagi_kesti(r, -20) & (m < 0))


@kural("altay.stokastik_trend", "Stokastik, trend yönünde", ALTAY, "110–140", "osilator", 10,
       "Yavaş %K 20'yi yukarı kesti ve MACD sıfırın üstünde.", "Yavaş %K 80'i aşağı kesti ve MACD sıfırın altında.")
def stokastik_trend(b):
    k, m = b.g["yavas_k"], b.g["macd"]
    return sinyal(yukari_kesti(k, 20) & (m > 0), asagi_kesti(k, 80) & (m < 0))


@kural("altay.momentum_100", "Momentum 100 kesişimi", ALTAY, "110–140", "trend", 20,
       "10 günlük momentum 100'ün üstüne çıktı.", "10 günlük momentum 100'ün altına indi.", gecerlilik=3)
def momentum_100(b):
    m = b.g["momentum10"]
    return sinyal(yukari_kesti(m, 100), asagi_kesti(m, 100))


@kural("altay.momentum_donus", "Momentum dip/tepe dönüşü", ALTAY, "110–140", "osilator", 10,
       "Momentum 100'ün altında dip yapıp döndü.",
       "Momentum 100'ün üstünde tepe yapıp döndü (önceki tepelerin çok üstünde değilse).", gecerlilik=3)
def momentum_donus(b):
    m = b.g["momentum10"]
    dip = (m.shift(1) <= m.shift(1).rolling(10).min()) & (m.shift(1) < 100) & (m > m.shift(1))
    tepe = (m.shift(1) >= m.shift(1).rolling(10).max()) & (m.shift(1) > 100) & (m < m.shift(1))
    # Önceki tepelerin çok üstündeki momentum aşağı dönse de SAT sayılmaz
    asiri = m.shift(1) > m.shift(11).rolling(120, min_periods=60).max()
    return sinyal(dip, tepe & ~asiri)


@kural("altay.cci_sifir", "CCI(10) sıfır kesişimi", ALTAY, "110–140", "trend", 10,
       "CCI(10) sıfırın üstüne çıktı.", "CCI(10) sıfırın altına indi.", gecerlilik=2)
def cci_sifir(b):
    c = b.g["cci10"]
    return sinyal(yukari_kesti(c, 0), asagi_kesti(c, 0))


@kural("altay.cci_100", "CCI ±100 dönüşü", ALTAY, "110–140", "osilator", 10,
       "CCI −100 altından döndü: aşırı düşüş bitiyor.", "CCI +100 üstünden döndü: spekülatif yükseliş bitiyor.")
def cci_100(b):
    c = b.g["cci20"]
    return sinyal(yukari_kesti(c, -100), asagi_kesti(c, 100))


@kural("altay.rsi_30_70", "RSI 30/70 dönüşü", ALTAY, "110–140", "osilator", 10,
       "RSI 30'un altından döndü.", "RSI 70'in üstünden döndü.")
def rsi_30_70(b):
    r = b.g["rsi"]
    return sinyal(yukari_kesti(r, 30), asagi_kesti(r, 70))


@kural("altay.obv_uyumsuzluk", "OBV uyumsuzluğu", ALTAY, "110–140", "hacim", 20,
       "Fiyat 20 günde düştü ama OBV yükseldi: OBV fiyattan önce döner.",
       "Fiyat 20 günde yükseldi ama OBV düştü: yükselişi hacim desteklemiyor.")
def obv_uyumsuzluk(b):
    c, o = b.g["close"], b.g["obv"]
    dc, do = c - c.shift(20), o - o.shift(20)
    al, sat = (dc < 0) & (do > 0), (dc > 0) & (do < 0)
    return sinyal(al & ~al.shift(1, fill_value=False), sat & ~sat.shift(1, fill_value=False))


@kural("altay.dow_cizgi", "Dow çizgisinin kırılması", ALTAY, "15–27", "trend", 60,
       "Fiyat en az 15 gündür ±%5 içinde yataydı ve üste kırdı.", "Fiyat en az 15 gündür ±%5 içinde yataydı ve alta kırdı.")
def dow_cizgi(b):
    c = b.g["close"]
    ort = c.shift(1).rolling(15).mean()
    yatay = (c.shift(1).rolling(15).max() <= ort * 1.05) & (c.shift(1).rolling(15).min() >= ort * 0.95)
    return sinyal(yatay & (c > ort * 1.05), yatay & (c < ort * 0.95))


@kural("altay.dow_yapi", "Dow: tepe-dip dizisinin teyidi", ALTAY, "15–27", "trend", 60,
       "Dipler yükselirken fiyat son tepenin üstünde kapattı: yükseliş teyit edildi.",
       "Tepeler alçalırken fiyat son dibin altında kapattı: düşüş teyit edildi.")
def dow_yapi(b):
    c = b.df["Close"].to_numpy()
    olay = np.zeros(len(c))
    tepeler, dipler = [], []
    sira = sorted(b.noktalar, key=lambda n: n[3])
    sinir = [n[3] for n in sira] + [len(c)]
    for j, n in enumerate(sira):
        (tepeler if n[2] == "tepe" else dipler).append(n)
        if len(tepeler) < 2 or len(dipler) < 2:
            continue
        yukselen = dipler[-1][1] > dipler[-2][1]
        alcalan = tepeler[-1][1] < tepeler[-2][1]
        for g in range(n[3] + 1, sinir[j + 1]):
            if yukselen and c[g] > tepeler[-1][1] and c[g - 1] <= tepeler[-1][1]:
                olay[g] = 1
            elif alcalan and c[g] < dipler[-1][1] and c[g - 1] >= dipler[-1][1]:
                olay[g] = -1
    return pd.Series(olay, index=b.df.index)


@kural("altay.trend_cizgisi", "Trend çizgisi kırılması", ALTAY, "79–83", "trend", 60,
       "Alçalan direnç çizgisi %3 ya da 3 kapanışla aşıldı.", "Yükselen destek çizgisi %3 ya da 3 kapanışla kırıldı.")
def trend_cizgisi(b):
    olay = np.zeros(len(b.df))
    for c in b.cizgiler:
        if c["kirilis"] is not None:
            olay[c["kirilis"]] = c["yon"]
    return pd.Series(olay, index=b.df.index)


@kural("altay.kanal", "Kanal sınırları", ALTAY, "79–83", "trend", 20,
       "Fiyat kanalın alt sınırına geldi.", "Fiyat kanalın üst sınırına geldi.")
def kanal(b):
    c = b.df["Close"].to_numpy()
    olay = np.zeros(len(c))
    for z in b.cizgiler:
        if z["kanal"] is None or not z["kanal"]:
            continue
        son = z["kirilis"] if z["kirilis"] is not None else z["bitis"]
        onceki = None
        for g in range(z["n2"][3] + 1, son):
            a, u = sorted((z["cizgi"](g), z["cizgi"](g) + z["kanal"]))
            konum = (c[g] - a) / (u - a)
            if onceki is not None:
                if konum <= 0.15 < onceki:
                    olay[g] = 1
                elif konum >= 0.85 > onceki:
                    olay[g] = -1
            onceki = konum
    return pd.Series(olay, index=b.df.index)


@kural("altay.formasyon", "Teyitli klasik formasyon", ALTAY, "83–109", "formasyon", 60,
       "OBO, üçgen, dikdörtgen, kama ya da bayrak hacim teyidiyle yukarı kırıldı.",
       "OBO, üçgen, dikdörtgen, kama ya da bayrak aşağı kırıldı.", gecerlilik=10)
def formasyon(b):
    return pd.Series(formasyon_olaylari(b.formasyonlar, len(b.df)), index=b.df.index)
