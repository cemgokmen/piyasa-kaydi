"""
Kuralların geçmiş sınaması: her sinyalden sonra hisse, aynı günkü BIST 100 hisselerinin eşit ağırlıklı
ortalamasına göre ne yaptı?

Yöntemin nedenleri:
  - Karşılaştırma endeksle değil aynı hisse grubuyladır: evren bugünkü BIST 100 olduğu için geçmişte
    kalanlar elenmiştir (sağkalım yanlılığı); endeksle kıyaslamak her kurala haksız bir artı yazar.
  - Aynı haftanın sinyalleri birbirinden bağımsız değildir: önce hafta ortalaması alınır, test haftalar üzerinden yapılır.
  - İzleme süresi haftadan uzunsa ardışık haftaların getirileri çakışır; p değeri bunu hesaba katar (Newey-West).
  - Çok kural birden sınanınca bazıları şansla iyi çıkar: Holm düzeltmesi.
  - Dönemin ilk ve ikinci yarısı aynı işareti vermelidir.
  - Sinyal, işlem maliyetini (MALIYET) karşılamıyorsa kanıt sayılmaz; hisse grubu al-tut, kural ise al-sat yapar.
  - Dönem verilirse göstergeler yine bütün veriyle hesaplanır, yalnızca o dönemdeki sinyaller sayılır (donemler.py).
"""

import math
import warnings

import numpy as np
import pandas as pd
from scipy import stats

from piyasa.analiz.ajan import KURALLAR, Baglam
from piyasa.analiz.istatistik import holm, ozet
from piyasa.analiz.teknik.cizgiler import DELME
from piyasa.analiz.teknik.gostergeler import gostergeler

MALIYET = 0.004     # gidiş-dönüş: işlem başına binde 2 (deney.KOMISYON_BUGUN), fiyat kayması hariç

FORMASYON_ADLARI = {
    "obo": "Omuz-baş-omuz", "tobo": "Ters omuz-baş-omuz", "dikdortgen": "Dikdörtgen", "yukselen_ucgen": "Yükselen üçgen",
    "alcalan_ucgen": "Alçalan üçgen", "simetrik_ucgen": "Simetrik üçgen", "alcalan_kama": "Alçalan kama",
    "yukselen_kama": "Yükselen kama", "genisleme": "Genişleme", "bayrak": "Bayrak / flama",
}


def olaylar(fiyatlar, kurallar=None):
    """fiyatlar: {kod: OHLCV}. Dönüş: {kural kimliği: {kod: sinyal serisi}}."""
    kurallar = kurallar or KURALLAR
    sonuc = {k: {} for k in kurallar}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for kod, df in fiyatlar.items():
            b = Baglam(df, gostergeler(df))
            for k, r in kurallar.items():
                sonuc[k][kod] = r.fonksiyon(b)
    return sonuc


def _cakisma_p(x, gecikme):
    """Ortalama = 0 testi; gecikme haftaya kadar çakışan gözlemlere dayanıklı (Newey-West) standart hatayla."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    e = x - x.mean()
    varyans = float(e @ e) / n
    for k in range(1, min(gecikme, n - 1) + 1):
        varyans += 2 * (1 - k / (gecikme + 1)) * float(e[k:] @ e[:-k]) / n
    if varyans <= 0:
        return 1.0
    return float(2 * stats.t.sf(abs(x.mean()) / math.sqrt(varyans / n), n - 1))


def _haftalik_ozet(satirlar, ufuk=5):
    """satirlar: (tarih, fark) listesi. Hafta ortalamalarının özeti ve iki yarının işaretleri."""
    if not satirlar:
        return {"n": 0, "sinyal": 0}
    s = pd.Series([f for _, f in satirlar], index=pd.DatetimeIndex([t for t, _ in satirlar])).sort_index()
    h = s.resample("W-FRI").mean().dropna()
    sonuc = ozet(h.tolist())
    if "p" in sonuc:
        sonuc["p"] = _cakisma_p(h.to_numpy(), math.ceil(ufuk / 5))
    sonuc["sinyal"] = len(s)
    yari = len(h) // 2
    sonuc["ilk_yari"] = float(h.iloc[:yari].mean()) if yari else None
    sonuc["ikinci_yari"] = float(h.iloc[yari:].mean()) if yari else None
    return sonuc


def _karar(s):
    if s.get("n", 0) < 20 or "p" not in s:
        return "yetersiz"
    p = s.get("p_duzeltilmis", s["p"])
    tutarli = s["ilk_yari"] is not None and s["ilk_yari"] * s["ikinci_yari"] > 0
    if 0 < s["ortalama"] <= MALIYET and s["p"] < 0.05 and tutarli:
        return "maliyet"
    if s["ortalama"] > 0 and p < 0.05 and tutarli:
        return "calisiyor"
    if s["ortalama"] < 0 and p < 0.05 and tutarli:
        return "ters"
    if s["p"] < 0.05 and tutarli:
        return "zayif" if s["ortalama"] > 0 else "ters_zayif"
    return "sans"


def sina(fiyatlar, kurallar=None, donem=None, sinyaller=None):
    """
    fiyatlar: {kod: OHLCV}. Dönüş: {kural: {'al': özet, 'sat': özet}}.
    Giriş sinyalin ertesi günü kapanışındadır. 'sat' için fark işareti çevrilir: SAT'ın çalışması, hissenin
    grubun gerisinde kalması demektir; olumlu ortalama çalıştığını gösterir.
    """
    kurallar = kurallar or KURALLAR
    kapanis = pd.DataFrame({k: d["Close"] for k, d in fiyatlar.items()}).sort_index()
    sinyaller = sinyaller or olaylar(fiyatlar, kurallar)
    sonuc, testler = {}, []
    for kimlik, r in kurallar.items():
        ileri = kapanis.shift(-r.ufuk - 1) / kapanis.shift(-1) - 1
        fark = ileri.sub(ileri.mean(axis=1), axis=0)
        cikis = pd.Series(kapanis.index, index=kapanis.index).shift(-r.ufuk - 1)
        al, sat = [], []
        for kod, s in sinyaller[kimlik].items():
            f = fark[kod].reindex(s.index)
            for t in s.index[(s != 0) & f.notna()]:
                if donem is not None and not donem.icerir(t, cikis.loc[t]):
                    continue
                if s.loc[t] > 0:
                    al.append((t, float(f.loc[t])))
                else:
                    sat.append((t, -float(f.loc[t])))
        sonuc[kimlik] = {"al": _haftalik_ozet(al, r.ufuk), "sat": _haftalik_ozet(sat, r.ufuk), "ufuk": r.ufuk}
        testler += [sonuc[kimlik]["al"], sonuc[kimlik]["sat"]]
    holm(testler)
    for v in sonuc.values():
        for yon in ("al", "sat"):
            v[yon]["kanit"] = _karar(v[yon])
            v[yon].pop("karar", None)
    return sonuc


def formasyon_kayitlari(fiyatlar, ufuk=60):
    """Her teyitli kırılış için: tür, kırılış ve izleme bitiş günü, hedefe ulaştı mı?"""
    satirlar = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for df in fiyatlar.values():
            c = df["Close"].to_numpy()
            for f in Baglam(df, gostergeler(df)).formasyonlar:
                if f.get("durum") != "teyitli" or f["kirilis"] + ufuk >= len(c):
                    continue
                sonra = c[f["kirilis"] + 1:f["kirilis"] + 1 + ufuk]
                ulasti = (sonra >= f["hedef"]).any() if f["kirilis_yon"] > 0 else (sonra <= f["hedef"]).any()
                satirlar.append((f["kod"], df.index[f["kirilis"]], df.index[f["kirilis"] + ufuk], bool(ulasti)))
    return satirlar


def formasyon_ozeti(kayitlar, donem=None):
    gruplar = {}
    for kod, giris, cikis, ulasti in kayitlar:
        if donem is None or donem.icerir(giris, cikis):
            gruplar.setdefault(kod, []).append(ulasti)
    return {k: {"ad": FORMASYON_ADLARI.get(k, k), "n": len(v), "hedef": sum(v) / len(v)} for k, v in gruplar.items()}


def formasyon_sinama(fiyatlar, ufuk=60, donem=None):
    """Her formasyon türünde teyitli kırılışların kaçı kaynağın hedefine ufuk gün içinde ulaştı?"""
    return formasyon_ozeti(formasyon_kayitlari(fiyatlar, ufuk), donem)


def cizgi_kayitlari(fiyatlar, ufuk=60):
    """Her trend çizgisi sabit tutulup ufuk gün izlenir: başlangıç, bitiş, eğim, uzunluk, kırıldı mı?"""
    satirlar = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for df in fiyatlar.values():
            c = df["Close"].to_numpy()
            for z in Baglam(df, gostergeler(df)).cizgiler:
                bas = z["n2"][3]
                if bas + ufuk >= len(c):
                    continue
                dista, kir = 0, False
                for g in range(bas + 1, bas + 1 + ufuk):
                    d = z["cizgi"](g)
                    fark = (d - c[g]) / d if z["tur"] == "destek" else (c[g] - d) / d
                    dista = dista + 1 if fark > 0 else 0
                    if fark >= DELME or dista >= 3:
                        kir = True
                        break
                egim = abs(z["n2"][1] - z["n1"][1]) / z["n1"][1] / max(1, z["n2"][0] - z["n1"][0]) * 100
                satirlar.append((df.index[bas], df.index[bas + ufuk], egim, z["n2"][0] - z["n1"][0], kir))
    return satirlar


def cizgi_ozeti(kayitlar, donem=None, ufuk=60):
    """
    Trend çizgisinin eğimi dayanıklılığını belirliyor mu? Kaynaklar çelişir (Altay: dik çizgi kolay kırılır;
    Gedik: dik çizgi daha güvenilir). Eğim, çizginin günlük yüzde değişimidir.
    """
    secili = [k for k in kayitlar if donem is None or donem.icerir(k[0], k[1])]
    if len(secili) < 30:
        return None
    tablo = pd.DataFrame(secili, columns=["giris", "cikis", "egim", "uzun", "kir"])
    kesit = [float(tablo["egim"].quantile(q)) for q in (1 / 3, 2 / 3)]
    grup = pd.cut(tablo["egim"], [-1, kesit[0], kesit[1], float("inf")], labels=False)
    return {"kesit": kesit, "kirilma": [float(tablo.loc[grup == i, "kir"].mean()) for i in range(3)], "n": len(tablo), "ufuk": ufuk}


def cizgi_sinama(fiyatlar, ufuk=60, donem=None):
    return cizgi_ozeti(cizgi_kayitlari(fiyatlar, ufuk), donem, ufuk)
