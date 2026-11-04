"""Ana giriş: bir hissenin bütün teknik analizini tek sözlükte toplar."""

import numpy as np
import pandas as pd

from piyasa.analiz.teknik.cizgiler import (
    guncel_cizgiler,
    guncel_formasyonlar,
    klasik_formasyonlar,
    trend_cizgileri,
)
from piyasa.analiz.teknik.egilim import trend_egilimi
from piyasa.analiz.teknik.formasyon import grafik_formasyonlari, mum_formasyonlari
from piyasa.analiz.teknik.gostergeler import YILLIK
from piyasa.analiz.teknik.puanlama import BILESEN_ADLARI, VADELER, gecmis_isabet, puan_serileri
from piyasa.analiz.teknik.yapi import (
    dow_okumasi,
    fibonacci,
    uyumsuzluklar,
    weinstein_evresi,
    yapi,
    zigzag,
    zigzag_teyitli,
)


def _f(x, n=2):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) or pd.isna(x) else round(float(x), n)


def analiz(df, endeks=None, vade="orta"):
    """
    Bir hissenin teknik analizi. df günlük OHLCV; endeks aynı dönemin endeks kapanışları.
    Dönüş: gostergeler, bilesenler, puanlar, okuma, formasyonlar, yapi, evre, fibonacci, isabet.
    """
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    df = df[df["Close"] > 0]
    if len(df) < 60:
        raise ValueError("Teknik analiz için en az 60 günlük fiyat gerekli.")
    g, b = puan_serileri(df, endeks)
    son = g.iloc[-1]
    noktalar, son_uc = zigzag(df, g["atr"], 2.0)

    gosterge = {k: _f(son.get(k), 4) for k in (
        "close", "sma20", "sma50", "sma200", "ema20", "atr", "rsi", "rsi2", "macd", "macd_sinyal", "macd_hist",
        "bb_ust", "bb_alt", "bb_b", "bb_genislik", "adx", "arti_di", "eksi_di", "stok_k", "stok_d", "cmf", "mfi",
        "st_yon", "st_cizgi", "tenkan", "kijun", "span_a", "span_b", "hacim", "hacim20", "zirve252", "dip252",
        "oynaklik", "endeks_oynaklik", "beta", "donchian_ust", "donchian_alt",
        "williams", "momentum10", "cci20", "cci10", "vhf", "yavas_k", "yavas_d")}
    c = df["Close"]

    def getiri(n):
        return _f(c.iloc[-1] / c.iloc[-n - 1] - 1, 4) if len(c) > n else None

    gosterge["getiriler"] = {"1h": getiri(5), "1a": getiri(21), "3a": getiri(63), "6a": getiri(126), "1y": getiri(252)}
    if "endeks" in g:
        e = g["endeks"]
        gosterge["endeks_getiri"] = {k: (_f(e.iloc[-1] / e.iloc[-n - 1] - 1, 4) if len(e) > n else None)
                                     for k, n in (("1h", 5), ("1a", 21), ("3a", 63), ("6a", 126), ("1y", 252))}
    # En büyük düşüş (son 1 yıl)
    son_yil = c.iloc[-YILLIK:]
    gosterge["en_buyuk_dusus"] = _f((son_yil / son_yil.cummax() - 1).min(), 4)

    bilesen = {k: _f(b[k].iloc[-1], 3) for k in BILESEN_ADLARI}
    puanlar = {v: _f(b[f"puan_{v}"].iloc[-1], 1) for v in VADELER}

    mumlar = mum_formasyonlari(df, g)
    formasyon = grafik_formasyonlari(df, g, noktalar)
    uyumsuz = uyumsuzluklar(g, noktalar, len(df) - 1)
    yapi_ = yapi(noktalar, son_uc)
    evre = weinstein_evresi(df)
    fib = fibonacci(df)
    teyitli, _ = zigzag_teyitli(df, g["atr"], 2.0)

    return {
        "tarih": df.index[-1].date(),
        "gosterge": gosterge,
        "bilesen": bilesen,
        "puanlar": puanlar,
        "mumlar": mumlar,
        "formasyonlar": formasyon + uyumsuz,
        "yapi": yapi_,
        "evre": evre,
        "fibonacci": fib,
        "dow": dow_okumasi(df, g["atr"]),
        "egilim": trend_egilimi(c),
        "trend_cizgileri": guncel_cizgiler(trend_cizgileri(df, teyitli), df),
        "klasik": guncel_formasyonlar(klasik_formasyonlar(df, teyitli, g["atr"]), df),
        "noktalar": [{"tarih": df.index[i].strftime("%Y-%m-%d"), "fiyat": round(f, 4), "tur": t} for i, f, t in noktalar[-12:]],
        "isabet": {v: gecmis_isabet(g, b, v) for v in VADELER},
        "_g": g, "_b": b, "_df": df,
    }
