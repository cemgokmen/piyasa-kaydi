"""
Bu hisse trend yapıyor mu? Etkinlik testleri (Altay 1997, 1. bölüm):
  seri korelasyon  k günlük örtüşmeyen log getirilerin bir önceki k günlükle korelasyonu
  run testi        aynı yöndeki ardışık getiri grupları. Gerçekleşen run sayısı beklenenden azsa seri
                   trendlidir: z = (R − μ) / σ; z < −1,96 trendli, z > +1,96 dönüşlü, arası rassal
"""

import numpy as np


def run_testi(getiri):
    x = np.asarray(getiri, dtype=float)
    x = x[np.isfinite(x) & (x != 0)]
    arti, eksi = int((x > 0).sum()), int((x < 0).sum())
    n = arti + eksi
    if arti < 10 or eksi < 10:
        return None
    r = 1 + int((np.sign(x[1:]) != np.sign(x[:-1])).sum())
    mu = 2 * arti * eksi / n + 1
    sigma = np.sqrt((mu - 1) * (mu - 2) / (n - 1))
    return {"run": r, "beklenen": float(mu), "z": float((r - mu) / sigma), "n": n}


def seri_korelasyon(kapanis, k):
    """k günlük örtüşmeyen getirilerin birinci gecikme korelasyonu; güven sınırı ≈ ±2/√n."""
    log = np.log(np.asarray(kapanis, dtype=float))
    log = log[np.isfinite(log)]
    # Son güne hizalı: bugünden geriye k'şar gün
    g = np.diff(log[::-1][::k])[::-1] * -1
    if len(g) < 20 or g.std() == 0:
        return None
    r = float(np.corrcoef(g[:-1], g[1:])[0, 1])
    return {"k": k, "r": r, "n": len(g), "anlamli": bool(abs(r) > 2 / np.sqrt(len(g)))}


def trend_egilimi(kapanis, gun=504):
    """Son ~2 yılın testleri ve tek cümlelik cevap."""
    c = kapanis.dropna().iloc[-gun:]
    if len(c) < 120:
        return None
    rt = run_testi(np.diff(np.log(c.to_numpy())))
    kor = {k: seri_korelasyon(c.to_numpy(), k) for k in (1, 5, 10)}
    if not rt:
        return None
    if rt["z"] < -1.96:
        kod = "trendli"
    elif rt["z"] > 1.96:
        kod = "donuslu"
    else:
        kod = "rassal"
    return {"kod": kod, "run": rt, "korelasyon": kor, "gun": len(c)}
