"""
Getiri örneklemlerinin özet istatistikleri: ortalama, medyan, endeksi yenme
oranı, %95 güven aralığı ve "şans olabilir mi?" testi.
"""

import numpy as np
from scipy import stats

ASGARI_ORNEK = 20      # bundan az olayla sonuç yorumlanmaz
ANLAMLILIK = 0.05


def ozet(farklar, tohum=7):
    """
    farklar: hisse getirisi − endeks getirisi listesi.
    Güven aralığı bootstrap ile; p değeri tek örneklem t testi (fark = 0).
    """
    x = np.asarray([f for f in farklar if f is not None and np.isfinite(f)], dtype=float)
    n = len(x)
    if n == 0:
        return {"n": 0}

    sonuc = {
        "n": n,
        "ortalama": float(x.mean()),
        "medyan": float(np.median(x)),
        "yenme": float((x > 0).mean()),
    }
    if n >= 3:
        rng = np.random.default_rng(tohum)
        ornekler = rng.choice(x, size=(2000, n), replace=True).mean(axis=1)
        sonuc["alt"], sonuc["ust"] = (float(v) for v in np.percentile(ornekler, [2.5, 97.5]))
        sonuc["p"] = float(stats.ttest_1samp(x, 0).pvalue) if x.std() > 0 else 1.0
    sonuc["karar"] = karar(sonuc)
    return sonuc


def karar(s):
    if s["n"] < ASGARI_ORNEK or "p" not in s:
        return {"kod": "yetersiz", "metin": "Yetersiz örnek"}
    if s["p"] < ANLAMLILIK:
        if s["ortalama"] > 0:
            return {"kod": "iyi", "metin": "Endeksi anlamlı ölçüde yendi"}
        return {"kod": "kotu", "metin": "Endeksin anlamlı ölçüde gerisinde"}
    return {"kod": "sans", "metin": "Şanstan ayırt edilemiyor"}


def holm(ozetler):
    """
    Çoklu karşılaştırma düzeltmesi (Holm-Bonferroni). Aynı anda çok sayıda
    test yapıldığında, yalnızca şansla 'anlamlı' görünen sonuçları eler.
    Her özete 'p_duzeltilmis' ekler ve kararı ona göre yeniden verir.
    """
    testler = sorted((s for s in ozetler if s.get("n", 0) >= ASGARI_ORNEK and "p" in s),
                     key=lambda s: s["p"])
    m = len(testler)
    enbuyuk = 0.0
    for i, s in enumerate(testler):
        enbuyuk = max(enbuyuk, min(1.0, (m - i) * s["p"]))
        s["p_duzeltilmis"] = enbuyuk
    for s in ozetler:
        if "p_duzeltilmis" in s:
            s["karar"] = karar({**s, "p": s["p_duzeltilmis"]})
    return ozetler
