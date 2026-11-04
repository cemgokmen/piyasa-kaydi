"""
Göstergeler: saf formüller (seri döndürür) ve bir hissenin bütün göstergelerini tek tabloda
toplayan gostergeler(). Yorum ve puan burada yapılmaz.
"""

import numpy as np
import pandas as pd

from piyasa.analiz.destek_direnc import atr as atr_hesapla

YILLIK = 252


def sma(s, n):
    return s.rolling(n, min_periods=n).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def wilder(s, n):
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def rsi(kapanis, n=14):
    fark = kapanis.diff()
    kazanc = wilder(fark.clip(lower=0), n)
    kayip = wilder(-fark.clip(upper=0), n)
    rs = kazanc / kayip.replace(0, np.nan)
    sonuc = 100 - 100 / (1 + rs)
    return sonuc.where(kayip != 0, 100.0)


def macd(kapanis, hizli=12, yavas=26, sinyal=9):
    cizgi = ema(kapanis, hizli) - ema(kapanis, yavas)
    sinyal_c = cizgi.ewm(span=sinyal, adjust=False, min_periods=sinyal).mean()
    return cizgi, sinyal_c, cizgi - sinyal_c


def bollinger(kapanis, n=20, k=2.0):
    orta = sma(kapanis, n)
    sapma = kapanis.rolling(n, min_periods=n).std(ddof=0)
    ust, alt = orta + k * sapma, orta - k * sapma
    genislik = (ust - alt) / orta
    yuzde_b = (kapanis - alt) / (ust - alt)
    return orta, ust, alt, genislik, yuzde_b


def adx(df, n=14):
    yuksek, dusuk = df["High"], df["Low"]
    yukari = yuksek.diff()
    asagi = -dusuk.diff()
    arti_dm = yukari.where((yukari > asagi) & (yukari > 0), 0.0)
    eksi_dm = asagi.where((asagi > yukari) & (asagi > 0), 0.0)
    tr = atr_hesapla(df, 1)  # alfa=1 → ham gerçek aralık
    tr_n = wilder(tr, n)
    arti_di = 100 * wilder(arti_dm, n) / tr_n
    eksi_di = 100 * wilder(eksi_dm, n) / tr_n
    dx = 100 * (arti_di - eksi_di).abs() / (arti_di + eksi_di).replace(0, np.nan)
    return wilder(dx, n), arti_di, eksi_di


def stokastik(df, n=14, d=3, yavaslatma=1):
    """yavaslatma=3: yavaşlatılmış %K (hızlı %K'nin 3 günlük ortalaması) ve onun %D'si."""
    en_dusuk = df["Low"].rolling(n, min_periods=n).min()
    en_yuksek = df["High"].rolling(n, min_periods=n).max()
    k = 100 * (df["Close"] - en_dusuk) / (en_yuksek - en_dusuk).replace(0, np.nan)
    if yavaslatma > 1:
        k = k.rolling(yavaslatma).mean()
    return k, k.rolling(d).mean()


def williams_r(df, n=14):
    """%R = (EY − K) / (EY − ED) × −100. −20 üstü aşırı alım, −80 altı aşırı satım."""
    en_dusuk = df["Low"].rolling(n, min_periods=n).min()
    en_yuksek = df["High"].rolling(n, min_periods=n).max()
    return -100 * (en_yuksek - df["Close"]) / (en_yuksek - en_dusuk).replace(0, np.nan)


def momentum_orani(kapanis, n=10):
    """Momentum = K / K(n gün önce) × 100; 100 çizgisi denge."""
    return 100 * kapanis / kapanis.shift(n)


def cci(df, n=20):
    """CCI = (TP − SMA(TP)) / (0,015 × ortalama sapma); TP = (Y + D + K) / 3."""
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    ort = tp.rolling(n, min_periods=n).mean()
    # Ortalama sapma, her pencerenin kendi ortalamasına göre
    sapma = tp.rolling(n, min_periods=n).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - ort) / (0.015 * sapma.replace(0, np.nan))


def vhf(kapanis, n=28):
    """Dikey Yatay Filtre = |EY − ED| / Σ|ΔK| (kapanışlarla). Yüksek değer trend, düşük değer yatay."""
    ey = kapanis.rolling(n, min_periods=n).max()
    ed = kapanis.rolling(n, min_periods=n).min()
    yol = kapanis.diff().abs().rolling(n, min_periods=n).sum()
    return (ey - ed) / yol.replace(0, np.nan)


def obv(df):
    yon = np.sign(df["Close"].diff()).fillna(0)
    return (yon * df["Volume"]).cumsum()


def cmf(df, n=20):
    aralik = (df["High"] - df["Low"]).replace(0, np.nan)
    carpan = ((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / aralik
    akis = (carpan.fillna(0) * df["Volume"])
    hacim = df["Volume"].rolling(n, min_periods=n).sum().replace(0, np.nan)
    return akis.rolling(n, min_periods=n).sum() / hacim


def mfi(df, n=14):
    tipik = (df["High"] + df["Low"] + df["Close"]) / 3
    akis = tipik * df["Volume"]
    arti = akis.where(tipik > tipik.shift(1), 0.0).rolling(n, min_periods=n).sum()
    eksi = akis.where(tipik < tipik.shift(1), 0.0).rolling(n, min_periods=n).sum()
    return 100 - 100 / (1 + arti / eksi.replace(0, np.nan))


def supertrend(df, n=10, k=3.0):
    """+1 yükseliş, −1 düşüş ve çizgi (stop seviyesi gibi okunur)."""
    a = atr_hesapla(df, n).to_numpy()
    orta = ((df["High"] + df["Low"]) / 2).to_numpy()
    kapanis = df["Close"].to_numpy()
    ust_ham, alt_ham = orta + k * a, orta - k * a
    m = len(df)
    ust, alt = ust_ham.copy(), alt_ham.copy()
    yon = np.ones(m)
    cizgi = np.full(m, np.nan)
    for i in range(1, m):
        if np.isnan(a[i]):
            continue
        if not np.isnan(ust[i - 1]) and (ust_ham[i] > ust[i - 1]) and kapanis[i - 1] <= ust[i - 1]:
            ust[i] = ust[i - 1]
        if not np.isnan(alt[i - 1]) and (alt_ham[i] < alt[i - 1]) and kapanis[i - 1] >= alt[i - 1]:
            alt[i] = alt[i - 1]
        if kapanis[i] > ust[i - 1] if not np.isnan(ust[i - 1]) else False:
            yon[i] = 1
        elif kapanis[i] < alt[i - 1] if not np.isnan(alt[i - 1]) else False:
            yon[i] = -1
        else:
            yon[i] = yon[i - 1]
        cizgi[i] = alt[i] if yon[i] > 0 else ust[i]
    return pd.Series(yon, index=df.index), pd.Series(cizgi, index=df.index)


def ichimoku(df):
    def orta(n):
        return (df["High"].rolling(n).max() + df["Low"].rolling(n).min()) / 2
    tenkan, kijun = orta(9), orta(26)
    # Bulut bugünün fiyatıyla karşılaştırılırken 26 gün önce hesaplanan değerler kullanılır
    span_a = ((tenkan + kijun) / 2).shift(26)
    span_b = orta(52).shift(26)
    return tenkan, kijun, span_a, span_b

def gostergeler(df, endeks=None):
    """Bütün göstergeleri tek tabloda hesaplar (her satır bir gün)."""
    c = df["Close"]
    g = pd.DataFrame(index=df.index)
    g["close"] = c
    g["sma20"], g["sma50"], g["sma200"] = sma(c, 20), sma(c, 50), sma(c, 200)
    g["ema20"] = ema(c, 20)
    g["atr"] = atr_hesapla(df)
    g["rsi"] = rsi(c, 14)
    g["rsi2"] = rsi(c, 2)
    g["macd"], g["macd_sinyal"], g["macd_hist"] = macd(c)
    g["bb_orta"], g["bb_ust"], g["bb_alt"], g["bb_genislik"], g["bb_b"] = bollinger(c)
    g["adx"], g["arti_di"], g["eksi_di"] = adx(df)
    g["stok_k"], g["stok_d"] = stokastik(df)
    g["yavas_k"], g["yavas_d"] = stokastik(df, yavaslatma=3)
    g["williams"] = williams_r(df)
    g["momentum10"] = momentum_orani(c)
    g["cci20"], g["cci10"] = cci(df), cci(df, 10)
    g["vhf"] = vhf(c)
    g["obv"] = obv(df)
    g["cmf"] = cmf(df)
    g["mfi"] = mfi(df)
    g["st_yon"], g["st_cizgi"] = supertrend(df)
    g["tenkan"], g["kijun"], g["span_a"], g["span_b"] = ichimoku(df)
    g["hacim"] = df["Volume"]
    g["hacim20"] = sma(df["Volume"], 20)
    g["donchian_ust"] = df["High"].rolling(55).max().shift(1)
    g["donchian_alt"] = df["Low"].rolling(55).min().shift(1)
    g["zirve252"] = df["High"].rolling(YILLIK, min_periods=60).max()
    g["dip252"] = df["Low"].rolling(YILLIK, min_periods=60).min()
    getiri = c.pct_change()
    g["oynaklik"] = getiri.rolling(60, min_periods=40).std() * np.sqrt(YILLIK)
    if endeks is not None:
        e = endeks.reindex(df.index).ffill()
        g["endeks"] = e
        g["endeks_oynaklik"] = e.pct_change().rolling(60, min_periods=40).std() * np.sqrt(YILLIK)
        # Beta: son bir yılın günlük getirileriyle
        eg = e.pct_change()
        g["beta"] = getiri.rolling(YILLIK, min_periods=120).cov(eg) / eg.rolling(YILLIK, min_periods=120).var()
    return g
