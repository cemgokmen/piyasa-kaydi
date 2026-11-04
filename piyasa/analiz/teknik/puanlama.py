"""
Puanlama: bileşen puanları, vade ağırlıkları ve puanın geçmiş isabeti.

Puanlama bütün geçmiş için vektörel hesaplanır. Böylece aynı kural, geçmişte verdiği puanlardan
sonra fiyatın ne yaptığıyla sınanabilir (gecmis_isabet) — kurallar kanıtla ayarlanır, sezgiyle değil.

Bileşenler ve dayandıkları bulgular:
  trend     fiyatın 50/200 günlük ortalamalara göre konumu, 200 günlüğün eğimi, Süpertrend
            (zaman serisi momentumu: Moskowitz, Ooi, Pedersen 2012; Faber 2007)
  momentum  12-1 ay getirisi, 6 ay getirisi, RSI rejimi, MACD histogramı
            (Jegadeesh & Titman 1993; son ay kısa vadeli dönüş nedeniyle dışarıda)
  relatif   endekse göre 3 ve 6 aylık fark (göreli güç)
  hacim     Chaikin para akışı, OBV eğimi, yükselen/düşen gün hacim oranı
  donus     kısa vadeli aşırı alım/satım: RSI(2), Bollinger %b (Connors; kısa vadeli dönüş
            etkisi, Lehmann 1990) — yalnızca kısa vadede ağırlıklı
  risk      endekse göre oynaklık ve 52 hafta zirvesinden uzaklık (George & Hwang 2004)
Her bileşen −1 (olumsuz) ile +1 (olumlu) arasındadır; teknik puan = 50 + 50 × ağırlıklı ortalama.
"""

import numpy as np
import pandas as pd

from piyasa.analiz.teknik.gostergeler import YILLIK, gostergeler

VADELER = {
    "kisa": {"ad": "Kısa vade", "aciklama": "Günler-haftalar", "gun": 10},
    "orta": {"ad": "Orta vade", "aciklama": "1-12 ay", "gun": 60},
    "uzun": {"ad": "Uzun vade", "aciklama": "1 yıl ve üstü", "gun": 250},
}

AGIRLIKLAR = {
    "kisa": {"trend": 0.20, "momentum": 0.15, "relatif": 0.10, "hacim": 0.20, "donus": 0.25, "risk": 0.10},
    "orta": {"trend": 0.25, "momentum": 0.30, "relatif": 0.20, "hacim": 0.15, "donus": 0.00, "risk": 0.10},
    "uzun": {"trend": 0.30, "momentum": 0.30, "relatif": 0.20, "hacim": 0.05, "donus": 0.00, "risk": 0.15},
}

BILESEN_ADLARI = {
    "trend": "Trend", "momentum": "Momentum", "relatif": "Endekse göre güç",
    "hacim": "Hacim / para akışı", "donus": "Aşırı alım-satım", "risk": "Risk",
}


def _kirp(s, olcek=1.0):
    return (s / olcek).clip(-1, 1)


def _ortalama(*seriler):
    return pd.concat(seriler, axis=1).mean(axis=1, skipna=True)


def bilesenler(df, g):
    """Her gün için −1..+1 arası bileşen puanları."""
    c, a = g["close"], g["atr"]
    b = pd.DataFrame(index=g.index)

    egim200 = g["sma200"] / g["sma200"].shift(20) - 1
    b["trend"] = _ortalama(
        _kirp((c - g["sma200"]) / (5 * a)),
        np.sign(g["sma50"] - g["sma200"]) * ((g["sma50"] / g["sma200"] - 1).abs() / 0.05).clip(upper=1),
        _kirp(egim200, 0.03),
        _kirp((c - g["sma50"]) / (3 * a)),
        g["st_yon"].where(g["atr"].notna()),
    )

    getiri_12_1 = c.shift(21) / c.shift(YILLIK) - 1
    getiri_6 = c / c.shift(126) - 1
    b["momentum"] = _ortalama(
        np.tanh(getiri_12_1 / 0.40),
        np.tanh(getiri_6 / 0.25),
        _kirp((g["rsi"] - 50) / 20),
        _kirp(g["macd_hist"] / (0.5 * a)),
    )

    if "endeks" in g:
        e = g["endeks"]
        fark3 = (c / c.shift(63)) - (e / e.shift(63))
        fark6 = (c / c.shift(126)) - (e / e.shift(126))
        b["relatif"] = _ortalama(np.tanh(fark3 / 0.15), np.tanh(fark6 / 0.25))
    else:
        b["relatif"] = np.nan

    hacim_var = df["Volume"].rolling(20).sum() > 0
    obv_egim = (g["obv"] - g["obv"].shift(20)) / (g["hacim20"] * 20).replace(0, np.nan)
    yukselen = df["Volume"].where(c.diff() > 0, 0).rolling(50, min_periods=30).sum()
    dusen = df["Volume"].where(c.diff() < 0, 0).rolling(50, min_periods=30).sum()
    hacim_orani = np.log((yukselen + 1) / (dusen + 1)) / np.log(2)
    b["hacim"] = _ortalama(_kirp(g["cmf"], 0.20), _kirp(obv_egim, 0.5), _kirp(hacim_orani)).where(hacim_var)

    rsi2_puani = _kirp((50 - g["rsi2"]) / 40)
    b_puani = _kirp((0.5 - g["bb_b"]) / 0.5)
    donus = _ortalama(rsi2_puani, b_puani)
    trend_ustu = c > g["sma200"]
    # Düşen trendde aşırı satım "düşen bıçak" olabilir: etkisi azaltılır. Yükselen trendde aşırı alım da öyle.
    donus = donus.where(~((donus > 0) & ~trend_ustu), donus * 0.3)
    donus = donus.where(~((donus < 0) & trend_ustu), donus * 0.5)
    b["donus"] = donus

    if "endeks_oynaklik" in g:
        oran = g["oynaklik"] / g["endeks_oynaklik"].replace(0, np.nan)
        oynaklik_p = _kirp(1.5 - oran)
    else:
        oynaklik_p = _kirp((0.45 - g["oynaklik"]) / 0.25)
    zirveden = c / g["zirve252"] - 1
    b["risk"] = _ortalama(oynaklik_p, _kirp(1 + zirveden * 4))
    return b


def vade_puani(b, vade):
    agirlik = AGIRLIKLAR[vade]
    toplam = pd.Series(0.0, index=b.index)
    w_toplam = pd.Series(0.0, index=b.index)
    for ad, w in agirlik.items():
        if w <= 0:
            continue
        s = b[ad]
        var = s.notna()
        toplam = toplam + (s.fillna(0) * w)
        w_toplam = w_toplam + var * w
    puan = 50 + 50 * toplam / w_toplam.replace(0, np.nan)
    return puan.where(w_toplam >= 0.5)


def puan_serileri(df, endeks=None):
    g = gostergeler(df, endeks)
    b = bilesenler(df, g)
    for v in VADELER:
        b[f"puan_{v}"] = vade_puani(b, v)
    return g, b


# ---------------------------------------------------------------------------
# 4. GEÇMİŞ İSABET (bu hissede kural geçmişte ne yaptı?)
# ---------------------------------------------------------------------------

def gecmis_isabet(g, b, vade):
    """
    Puanın olumlu (≥60), nötr ve olumsuz (≤40) olduğu günlerden sonraki vade kadar günün
    getirisi (endeks varsa endekse göre fark). Örtüşen pencereler aynı bilgiyi tekrar saydığı
    için örnekler vade aralığıyla seyreltilir (bağımsıza yakın gözlem).
    """
    from piyasa.analiz.istatistik import ozet

    h = VADELER[vade]["gun"]
    c = g["close"]
    ileri = c.shift(-h) / c - 1
    if "endeks" in g:
        ileri = ileri - (g["endeks"].shift(-h) / g["endeks"] - 1)
    puan = b[f"puan_{vade}"]
    tablo = pd.DataFrame({"puan": puan, "ileri": ileri}).dropna()
    if len(tablo) < h * 3:
        return None
    seyrek = tablo.iloc[::max(1, h // 2)]
    gruplar = []
    for ad, kosul in (("Olumlu (≥60)", seyrek["puan"] >= 60), ("Nötr (40-60)", seyrek["puan"].between(40, 60, inclusive="neither")),
                      ("Olumsuz (≤40)", seyrek["puan"] <= 40)):
        ornek = seyrek.loc[kosul, "ileri"]
        s = ozet(ornek.tolist()) if len(ornek) else {"n": 0}
        gruplar.append({"ad": ad, **s})
    korelasyon = float(seyrek["puan"].corr(seyrek["ileri"], method="spearman")) if len(seyrek) > 10 else None
    return {"gun": h, "gruplar": gruplar, "korelasyon": korelasyon, "endekse_gore": "endeks" in g,
            "baslangic": tablo.index[0].date(), "n": len(seyrek)}
