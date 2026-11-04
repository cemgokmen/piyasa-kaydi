"""
TSPAKB, "Analiz Yöntemleri", SPK Lisanslama Sınavları İleri Düzey Kılavuzu, Eylül 2011.
Notlar: analiz_ajani/notlar/tspakb-2011.md. Sayfa numaraları kılavuzun basılı numaralarıdır (PDF sayfası = basılı + 5).
"""

import numpy as np
import pandas as pd

from piyasa.analiz.ajan.kural import Kaynak, asagi_kesti, kural, sinyal, yukari_kesti
from piyasa.analiz.teknik.gostergeler import rsi, sma, stokastik

TSPAKB = Kaynak("tspakb2011", "TSPAKB 2011",
                "Türkiye Sermaye Piyasası Aracı Kuruluşları Birliği, Analiz Yöntemleri, İleri Düzey Lisans Kılavuzu, Eylül 2011",
                "analiz_ajani/notlar/tspakb-2011.md")

ADX_YATAY = 20


@kural("tspakb.fiyat_ho20", "Fiyat, 20 günlük ortalamayı kesti", TSPAKB, "69–70", "trend", 10,
       "Fiyat 20 günlük ortalamanın üstüne çıktı.", "Fiyat 20 günlük ortalamanın altına indi.", gecerlilik=2)
def fiyat_ho20(b):
    c, s = b.g["close"], b.g["sma20"]
    return sinyal(yukari_kesti(c, s), asagi_kesti(c, s))


@kural("tspakb.ho_5_20", "5 ve 20 günlük ortalama kesişimi", TSPAKB, "69–70", "trend", 10,
       "5 günlük ortalama 20 günlüğü yukarı kesti.", "5 günlük ortalama 20 günlüğü aşağı kesti.")
def ho_5_20(b):
    k, u = sma(b.g["close"], 5), b.g["sma20"]
    return sinyal(yukari_kesti(k, u), asagi_kesti(k, u))


@kural("tspakb.ho20_filtre", "20 günlük ortalama, %3 filtreli", TSPAKB, "70 (dipnot 9b)", "trend", 10,
       "Fiyat ortalamayı %3 aştı.", "Fiyat ortalamanın %3 altına indi.", gecerlilik=2)
def ho20_filtre(b):
    c, s = b.g["close"], b.g["sma20"]
    return sinyal(yukari_kesti(c, s * 1.03), asagi_kesti(c, s * 0.97))


@kural("tspakb.ho20_zaman", "20 günlük ortalama, 2 gün zaman filtreli", TSPAKB, "70 (dipnot 9c)", "trend", 10,
       "Fiyat ortalamayı aştı ve iki gün sonra hâlâ üstünde.", "Fiyat ortalamanın altına indi ve iki gün sonra hâlâ altında.", gecerlilik=2)
def ho20_zaman(b):
    c, s = b.g["close"], b.g["sma20"]
    ust, alt = c > s, c < s
    return sinyal(yukari_kesti(c, s).shift(2, fill_value=False) & ust & ust.shift(1, fill_value=False),
                  asagi_kesti(c, s).shift(2, fill_value=False) & alt & alt.shift(1, fill_value=False))


@kural("tspakb.ho20_zarf", "20 günlük ortalamanın %5'lik zarfı", TSPAKB, "70 (dipnot 9d)", "trend", 10,
       "Fiyat ortalamanın %5 üstündeki zarfı geçti.", "Fiyat ortalamanın %5 altındaki zarfı kırdı.", gecerlilik=2)
def ho20_zarf(b):
    c, s = b.g["close"], b.g["sma20"]
    return sinyal(yukari_kesti(c, s * 1.05), asagi_kesti(c, s * 0.95))


@kural("tspakb.zarf_yd", "En yüksek ve en düşük fiyat ortalaması bandı", TSPAKB, "70 (dipnot 9e), 71", "trend", 10,
       "Kapanış, en yükseklerin 20 günlük ortalamasını geçti.", "Kapanış, en düşüklerin 20 günlük ortalamasını kırdı.", gecerlilik=2)
def zarf_yd(b):
    c = b.g["close"]
    return sinyal(yukari_kesti(c, sma(b.df["High"], 20)), asagi_kesti(c, sma(b.df["Low"], 20)))


@kural("tspakb.bollinger_devam", "Bollinger dışına çıkış, bant açılırken", TSPAKB, "72", "trend", 10,
       "Fiyat üst bandın üstüne çıktı ve bant genişliyor: trendin devamı.",
       "Fiyat alt bandın altına indi ve bant genişliyor: trendin devamı.", gecerlilik=2)
def bollinger_devam(b):
    c, g = b.g["close"], b.g["bb_genislik"]
    aciliyor = g > g.shift(1)
    return sinyal(yukari_kesti(c, b.g["bb_ust"]) & aciliyor, asagi_kesti(c, b.g["bb_alt"]) & aciliyor)


@kural("tspakb.bollinger_sikisma", "Bollinger sıkışmasından kırılış", TSPAKB, "72", "trend", 20,
       "Bant son 6 ayın en dar %10'undayken üst bant kırıldı.", "Bant son 6 ayın en dar %10'undayken alt bant kırıldı.", gecerlilik=3)
def bollinger_sikisma(b):
    c, g = b.g["close"], b.g["bb_genislik"]
    dar = (g <= g.rolling(126, min_periods=60).quantile(0.10)).rolling(5).max().shift(1) == 1
    return sinyal(yukari_kesti(c, b.g["bb_ust"]) & dar, asagi_kesti(c, b.g["bb_alt"]) & dar)


@kural("tspakb.macd_adx", "MACD kesişimi, ADX trend gösterirken", TSPAKB, "73, 78", "trend", 20,
       "MACD sinyal çizgisini yukarı kesti ve ADX en az 20.", "MACD sinyal çizgisini aşağı kesti ve ADX en az 20.", gecerlilik=3)
def macd_adx(b):
    m, s, a = b.g["macd"], b.g["macd_sinyal"], b.g["adx"]
    return sinyal(yukari_kesti(m, s) & (a >= ADX_YATAY), asagi_kesti(m, s) & (a >= ADX_YATAY))


@kural("tspakb.macd_adx_yatay", "MACD kesişimi, ADX yatay derken", TSPAKB, "78", "trend", 20,
       "MACD yukarı kesti ama ADX 20'nin altında; kaynağa göre geçersiz, karşılaştırma için sınanır.",
       "MACD aşağı kesti ama ADX 20'nin altında; kaynağa göre geçersiz, karşılaştırma için sınanır.", gecerlilik=3)
def macd_adx_yatay(b):
    m, s, a = b.g["macd"], b.g["macd_sinyal"], b.g["adx"]
    return sinyal(yukari_kesti(m, s) & (a < ADX_YATAY), asagi_kesti(m, s) & (a < ADX_YATAY))


@kural("tspakb.macd_histogram", "MACD histogramının dönüşü", TSPAKB, "73", "trend", 10,
       "Histogram sıfırın altında dip yapıp yükselmeye başladı.", "Histogram sıfırın üstünde zirve yapıp düşmeye başladı.", gecerlilik=2)
def macd_histogram(b):
    h = b.g["macd_hist"]
    o = h.shift(1)
    return sinyal((o < 0) & (o < h) & (o < h.shift(2)), (o > 0) & (o > h) & (o > h.shift(2)))


def _stokastik5(df):
    k, _ = stokastik(df, n=5)
    return k, k.ewm(span=3, adjust=False, min_periods=3).mean()


@kural("tspakb.stokastik5_kesisim", "Stokastik(5) %K–%D kesişimi", TSPAKB, "76", "osilator", 10,
       "5 günlük %K, 3 günlük üssel %D'yi yukarı kesti.", "5 günlük %K, 3 günlük üssel %D'yi aşağı kesti.", gecerlilik=2)
def stokastik5_kesisim(b):
    k, d = _stokastik5(b.df)
    return sinyal(yukari_kesti(k, d), asagi_kesti(k, d))


@kural("tspakb.stokastik5_bolge", "Stokastik(5) aşırı bölgeden çıkış", TSPAKB, "76", "osilator", 10,
       "5 günlük %K 20'nin üstüne çıktı.", "5 günlük %K 80'in altına indi.", gecerlilik=2)
def stokastik5_bolge(b):
    k, _ = _stokastik5(b.df)
    return sinyal(yukari_kesti(k, 20), asagi_kesti(k, 80))


@kural("tspakb.rsi9", "RSI(9) 30/70 dönüşü", TSPAKB, "77", "osilator", 10,
       "9 günlük RSI 30'un üstüne döndü.", "9 günlük RSI 70'in altına döndü.", gecerlilik=3)
def rsi9(b):
    r = rsi(b.g["close"], 9)
    return sinyal(yukari_kesti(r, 30), asagi_kesti(r, 70))


@kural("tspakb.rsi25", "RSI(25) 30/70 dönüşü", TSPAKB, "77", "osilator", 20,
       "25 günlük RSI 30'un üstüne döndü.", "25 günlük RSI 70'in altına döndü.")
def rsi25(b):
    r = rsi(b.g["close"], 25)
    return sinyal(yukari_kesti(r, 30), asagi_kesti(r, 70))


@kural("tspakb.rsi_uyumsuzluk", "RSI uyumsuzluğu", TSPAKB, "77", "osilator", 20,
       "Fiyat daha düşük dip yaptı, RSI daha yüksek dip yaptı.", "Fiyat daha yüksek tepe yaptı, RSI daha düşük tepe yaptı.")
def rsi_uyumsuzluk(b):
    r = b.g["rsi"].to_numpy()
    olay = np.zeros(len(r))
    son = {}
    for n in sorted(b.noktalar, key=lambda x: x[3]):
        onceki = son.get(n[2])
        son[n[2]] = n
        if onceki is None or np.isnan(r[n[0]]) or np.isnan(r[onceki[0]]) or n[0] - onceki[0] > 120:
            continue
        if n[2] == "dip" and n[1] < onceki[1] and r[n[0]] > r[onceki[0]]:
            olay[n[3]] = 1
        elif n[2] == "tepe" and n[1] > onceki[1] and r[n[0]] < r[onceki[0]]:
            olay[n[3]] = -1
    return pd.Series(olay, index=b.df.index)


@kural("tspakb.anahtar_gun", "Anahtar gün", TSPAKB, "67", "formasyon", 20,
       "Düşüşün sonunda uzun çubuk, yüksek hacim, tepeden kapanış.", "Yükselişin sonunda uzun çubuk, yüksek hacim, dipten kapanış.", gecerlilik=5)
def anahtar_gun(b):
    d, g = b.df, b.g
    aralik = d["High"] - d["Low"]
    uzun = (aralik >= 1.5 * g["atr"]) & (g["hacim"] >= 1.5 * g["hacim20"])
    konum = (d["Close"] - d["Low"]) / aralik.replace(0, np.nan)
    egim = g["sma50"] - g["sma50"].shift(20)
    al = uzun & (egim < 0) & (d["Low"] <= d["Low"].rolling(20).min()) & (konum >= 0.75) & (d["Close"] > d["Close"].shift(1))
    sat = uzun & (egim > 0) & (d["High"] >= d["High"].rolling(20).max()) & (konum <= 0.25) & (d["Close"] < d["Close"].shift(1))
    return sinyal(al, sat)


@kural("tspakb.kirilis_boslugu", "Kırılma boşluğu", TSPAKB, "68", "formasyon", 20,
       "Fiyat boşlukla açıldı, boşluk dolmadı, 20 günün zirvesi aşıldı.", "Fiyat boşlukla düştü, boşluk dolmadı, 20 günün dibi kırıldı.", gecerlilik=5)
def kirilis_boslugu(b):
    d = b.df
    y, a = d["High"].shift(1), d["Low"].shift(1)
    return sinyal((d["Low"] > y) & (d["Close"] > d["High"].shift(1).rolling(20).max()),
                  (d["High"] < a) & (d["Close"] < d["Low"].shift(1).rolling(20).min()))


@kural("tspakb.bosluk_dolumu", "Boşluk dolduktan sonra ters hareket", TSPAKB, "68", "formasyon", 10,
       "Yukarı boşluk 10 gün içinde aşağı doğru doldu: dolum hareketi tersine döner.",
       "Aşağı boşluk 10 gün içinde yukarı doğru doldu: dolum hareketi tersine döner.")
def bosluk_dolumu(b):
    h, lo = b.df["High"].to_numpy(), b.df["Low"].to_numpy()
    a = b.g["atr"].to_numpy()
    m = len(h)
    olay = np.zeros(m)
    for i in range(1, m):
        if np.isnan(a[i]):
            continue
        if lo[i] - h[i - 1] >= 0.5 * a[i]:
            for j in range(i + 1, min(i + 11, m)):
                if lo[j] <= h[i - 1]:
                    olay[j] = 1
                    break
        elif lo[i - 1] - h[i] >= 0.5 * a[i]:
            for j in range(i + 1, min(i + 11, m)):
                if h[j] >= lo[i - 1]:
                    olay[j] = -1
                    break
    return pd.Series(olay, index=b.df.index)


@kural("tspakb.ikili_tepe", "İkili tepe ve dip", TSPAKB, "67", "formasyon", 20,
       "İki dip aynı seviyede, aradaki tepe aşıldı.", "İki tepe aynı seviyede, aradaki dip kırıldı.", gecerlilik=5)
def ikili_tepe(b):
    c = b.df["Close"].to_numpy()
    h, lo = b.df["High"].to_numpy(), b.df["Low"].to_numpy()
    a = b.g["atr"].to_numpy()
    olay = np.zeros(len(c))
    son = {}
    for n in sorted(b.noktalar, key=lambda x: x[3]):
        onceki = son.get(n[2])
        son[n[2]] = n
        if onceki is None or np.isnan(a[n[3]]) or abs(n[1] - onceki[1]) > 0.6 * a[n[3]]:
            continue
        tepe = n[2] == "tepe"
        arada = lo[onceki[0]:n[0] + 1].min() if tepe else h[onceki[0]:n[0] + 1].max()
        if abs(onceki[1] - arada) < 2 * a[n[3]]:
            continue
        for g in range(n[3] + 1, min(n[3] + 41, len(c))):
            if (tepe and c[g] < arada) or (not tepe and c[g] > arada):
                olay[g] = -1 if tepe else 1
                break
    return pd.Series(olay, index=b.df.index)


@kural("tspakb.geri_cekilme", "Trend çizgisi kırılışından geri çekilme", TSPAKB, "62", "trend", 20,
       "Direnç çizgisi kırıldı, fiyat çizgiye geri çekildi ve kırılış kapanışını yeniden aştı.",
       "Destek çizgisi kırıldı, fiyat çizgiye geri çekildi ve kırılış kapanışının altına yeniden indi.", gecerlilik=5)
def geri_cekilme(b):
    c = b.df["Close"].to_numpy()
    olay = np.zeros(len(c))
    for z in b.cizgiler:
        g0 = z["kirilis"]
        if g0 is None:
            continue
        cekildi = False
        for g in range(g0 + 1, min(g0 + 21, len(c))):
            d = z["cizgi"](g)
            if d <= 0:
                break
            fark = z["yon"] * (c[g] - d) / d     # kırılış yönünde çizgiden uzaklık
            if fark < -0.03:
                break
            if fark <= 0.01:
                cekildi = True
            elif cekildi and z["yon"] * (c[g] - c[g0]) > 0:
                olay[g] = z["yon"]
                break
    return pd.Series(olay, index=b.df.index)
