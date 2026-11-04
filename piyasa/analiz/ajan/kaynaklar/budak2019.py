"""
Cemile Budak, Teknik Analiz İndikatörlerinin Performans Karşılaştırması Üzerine Bir Araştırma, Marmara Üni. YL tezi, 2019.
Notlar: analiz_ajani/notlar/budak-2019.md. Periyodu tezde yazmayan göstergelerde TradingView varsayılanı kullanıldı (tez
grafiklerini orada çizmiştir); hepsi notlarda listelidir. Sayfalar PDF sayfasıdır.
"""

import numpy as np
import pandas as pd

from piyasa.analiz.ajan.kural import Kaynak, asagi_kesti, kural, sinyal, yukari_kesti
from piyasa.analiz.teknik.gostergeler import ema

BUDAK = Kaynak("budak2019", "Budak 2019",
               "Cemile Budak, Teknik Analiz İndikatörlerinin Performans Karşılaştırması Üzerine Bir Araştırma, Marmara Üni. YL tezi, 2019",
               "analiz_ajani/notlar/budak-2019.md")


def _kesisim(hizli, yavas):
    return sinyal(yukari_kesti(hizli, yavas), asagi_kesti(hizli, yavas))


def _sifir(s):
    return _kesisim(s, pd.Series(0.0, index=s.index))


def _donus(s, alt, ust):
    """Alt seviyeyi yukarı kesince AL, üst seviyeyi aşağı kesince SAT."""
    return sinyal(yukari_kesti(s, alt), asagi_kesti(s, ust))


def _clv_hacim(df):
    aralik = (df["High"] - df["Low"]).replace(0, np.nan)
    return ((df["Close"] - df["Low"] - (df["High"] - df["Close"])) / aralik).fillna(0.0) * df["Volume"]


@kural("budak.dema", "Fiyat, çift üssel ortalamayı kesti", BUDAK, "40, 85", "trend", 10,
       "Fiyat 9 günlük DEMA'nın üstüne çıktı.", "Fiyat 9 günlük DEMA'nın altına indi.", gecerlilik=2)
def dema(b):
    c = b.df["Close"]
    bir = ema(c, 9)
    return _kesisim(c, 2 * bir - ema(bir, 9))


@kural("budak.ma9", "Fiyat, 9 günlük ortalamayı kesti", BUDAK, "49, 90–91", "trend", 10,
       "Fiyat 9 günlük ortalamanın üstüne çıktı.", "Fiyat 9 günlük ortalamanın altına indi.", gecerlilik=2)
def ma9(b):
    return _kesisim(b.df["Close"], b.df["Close"].rolling(9).mean())


@kural("budak.williams", "Williams %R −80/−20", BUDAK, "57–58, 96", "osilator", 10,
       "%R −80'i yukarı kesti.", "%R −20'yi aşağı kesti.", gecerlilik=2)
def williams(b):
    return _donus(b.g["williams"], -80, -20)


@kural("budak.rsi_giris", "RSI aşırı bölgeye girdi", BUDAK, "93", "osilator", 10,
       "RSI 30'un altına indi: dönüş beklenmeden alınır.", "RSI 70'in üstüne çıktı: dönüş beklenmeden satılır.", gecerlilik=2)
def rsi_giris(b):
    return sinyal(asagi_kesti(b.g["rsi"], 30), yukari_kesti(b.g["rsi"], 70))


@kural("budak.bollinger", "Bollinger bandına değme", BUDAK, "33, 81", "osilator", 10,
       "Fiyat alt banda değdi.", "Fiyat üst banda değdi.", gecerlilik=2)
def bollinger(b):
    c = b.df["Close"]
    orta, sapma = c.rolling(20).mean(), c.rolling(20).std(ddof=0)
    alt = b.df["Low"] <= orta - 2 * sapma
    ust = b.df["High"] >= orta + 2 * sapma
    return sinyal(alt & ~alt.shift(1, fill_value=False), ust & ~ust.shift(1, fill_value=False))


@kural("budak.aroon", "Aroon kesişimi", BUDAK, "31, 80", "trend", 20,
       "Aroon yukarı, Aroon aşağıyı kesti.", "Aroon aşağı, Aroon yukarıyı kesti.", gecerlilik=3)
def aroon(b, n=14):
    yukari = b.df["High"].rolling(n + 1).apply(np.argmax, raw=True) / n * 100
    asagi = b.df["Low"].rolling(n + 1).apply(np.argmin, raw=True) / n * 100
    return _kesisim(yukari, asagi)


@kural("budak.chaikin", "Chaikin osilatörü sıfır kesişimi", BUDAK, "34–35, 82", "hacim", 20,
       "Chaikin osilatörü sıfırın üstüne çıktı.", "Chaikin osilatörü sıfırın altına indi.", gecerlilik=3)
def chaikin(b):
    adi = _clv_hacim(b.df).cumsum()
    return _sifir(ema(adi, 3) - ema(adi, 10))


@kural("budak.cmf", "Chaikin para akımı sıfır kesişimi", BUDAK, "35–36, 83", "hacim", 20,
       "21 günlük para akımı sıfırın üstüne çıktı.", "21 günlük para akımı sıfırın altına indi.", gecerlilik=3)
def cmf(b):
    hacim = b.df["Volume"].rolling(21).sum().replace(0, np.nan)
    return _sifir(_clv_hacim(b.df).rolling(21).sum() / hacim)


@kural("budak.cmo", "Chande momentum sıfır kesişimi", BUDAK, "36–37, 83–84", "trend", 10,
       "CMO sıfırın üstüne çıktı.", "CMO sıfırın altına indi.", gecerlilik=2)
def cmo(b, n=14):
    fark = b.df["Close"].diff()
    artis, azalis = fark.clip(lower=0).rolling(n).sum(), (-fark.clip(upper=0)).rolling(n).sum()
    return _sifir((artis - azalis) / (artis + azalis).replace(0, np.nan) * 100)


@kural("budak.dmi", "+DI ve −DI kesişimi", BUDAK, "41–42, 86–87", "trend", 20,
       "+DI, −DI'yı yukarı kesti.", "+DI, −DI'yı aşağı kesti.", gecerlilik=3)
def dmi(b, n=14):
    y, d, c = b.df["High"], b.df["Low"], b.df["Close"]
    artis, azalis = y.diff(), -d.diff()
    arti = artis.where((artis > azalis) & (artis > 0), 0.0)
    eksi = azalis.where((azalis > artis) & (azalis > 0), 0.0)
    tr = pd.concat([y - d, (y - c.shift(1)).abs(), (d - c.shift(1)).abs()], axis=1).max(axis=1)
    pay = tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean().replace(0, np.nan)
    return _kesisim(arti.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / pay,
                    eksi.ewm(alpha=1 / n, adjust=False, min_periods=n).mean() / pay)


@kural("budak.eom", "Kolay fiyat hareketi sıfır kesişimi", BUDAK, "42–43, 87", "hacim", 10,
       "14 günlük EOM sıfırın üstüne çıktı.", "14 günlük EOM sıfırın altına indi.", gecerlilik=2)
def eom(b):
    y, d = b.df["High"], b.df["Low"]
    orta = ((y + d) / 2).diff()
    kutu = b.df["Volume"].replace(0, np.nan) / (y - d).replace(0, np.nan)
    return _sifir((orta / kutu).fillna(0.0).rolling(14).mean())


@kural("budak.imi", "Gün içi momentum 30/70", BUDAK, "44–45, 87–88", "osilator", 10,
       "IMI 30'u yukarı kesti.", "IMI 70'i aşağı kesti.", gecerlilik=2)
def imi(b, n=14):
    fark = b.df["Close"] - b.df["Open"]
    artis, azalis = fark.clip(lower=0).rolling(n).sum(), (-fark.clip(upper=0)).rolling(n).sum()
    return _donus(artis / (artis + azalis).replace(0, np.nan) * 100, 30, 70)


@kural("budak.mfi", "Para akım endeksi 20/80", BUDAK, "47–48, 90", "hacim", 10,
       "MFI 20'yi yukarı kesti.", "MFI 80'i aşağı kesti.", gecerlilik=2)
def mfi(b, n=14):
    tipik = (b.df["High"] + b.df["Low"] + b.df["Close"]) / 3
    akim = tipik * b.df["Volume"]
    yon = tipik.diff()
    arti, eksi = akim.where(yon > 0, 0.0).rolling(n).sum(), akim.where(yon < 0, 0.0).rolling(n).sum()
    return _donus(100 - 100 / (1 + arti / eksi.replace(0, np.nan)), 20, 80)


@kural("budak.fiyat_osilatoru", "Fiyat osilatörü sıfır kesişimi", BUDAK, "49–50, 91–92", "trend", 20,
       "10 günlük ortalama 21 günlüğün üstüne çıktı.", "10 günlük ortalama 21 günlüğün altına indi.", gecerlilik=3)
def fiyat_osilatoru(b):
    return _kesisim(b.df["Close"].rolling(10).mean(), b.df["Close"].rolling(21).mean())


@kural("budak.smi", "Stokastik momentum ±50", BUDAK, "53–54, 94", "osilator", 10,
       "SMI −50'yi yukarı kesti.", "SMI +50'yi aşağı kesti.", gecerlilik=2)
def smi(b, n=10):
    ust, alt = b.df["High"].rolling(n).max(), b.df["Low"].rolling(n).min()
    fark = ema(ema(b.df["Close"] - (ust + alt) / 2, 3), 3)
    aralik = ema(ema(ust - alt, 3), 3).replace(0, np.nan)
    return _donus(fark / (aralik / 2) * 100, -50, 50)


@kural("budak.trix", "TRIX ve ortalaması kesişimi", BUDAK, "55–56, 95–96", "trend", 20,
       "TRIX kendi 9 günlük ortalamasının üstüne çıktı.", "TRIX kendi 9 günlük ortalamasının altına indi.", gecerlilik=3)
def trix(b, n=18):
    uc = ema(ema(ema(b.df["Close"], n), n), n)
    t = uc.pct_change() * 100
    return _kesisim(t, t.rolling(9).mean())


@kural("budak.lrs", "Doğrusal regresyon eğimi sıfır kesişimi", BUDAK, "59, 97–98", "trend", 10,
       "14 günlük regresyon eğimi artıya döndü.", "14 günlük regresyon eğimi eksiye döndü.", gecerlilik=2)
def lrs(b, n=14):
    x = np.arange(n) - (n - 1) / 2
    agirlik = x / (x @ x)
    return _sifir(b.df["Close"].rolling(n).apply(lambda v: v @ agirlik, raw=True))
