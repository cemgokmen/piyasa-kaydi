"""
Kuralların geçmiş sınaması: her sinyalden sonra hisse, aynı günkü BIST 100 hisselerinin eşit ağırlıklı
ortalamasına göre ne yaptı?

Yöntemin nedenleri:
  - Karşılaştırma endeksle değil aynı hisse grubuyladır: evren bugünkü BIST 100 olduğu için geçmişte
    kalanlar elenmiştir (sağkalım yanlılığı); endeksle kıyaslamak her kurala haksız bir artı yazar.
  - Aynı haftanın sinyalleri birbirinden bağımsız değildir: önce hafta ortalaması alınır, test haftalar üzerinden yapılır.
  - Çok kural birden sınanınca bazıları şansla iyi çıkar: Holm düzeltmesi.
  - Dönemin ilk ve ikinci yarısı aynı işareti vermelidir.
"""

import warnings

import pandas as pd

from piyasa.analiz.ajan import KURALLAR, Baglam
from piyasa.analiz.istatistik import holm, ozet
from piyasa.analiz.teknik.cizgiler import DELME
from piyasa.analiz.teknik.gostergeler import gostergeler

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


def _haftalik_ozet(satirlar):
    """satirlar: (tarih, fark) listesi. Hafta ortalamalarının özeti ve iki yarının işaretleri."""
    if not satirlar:
        return {"n": 0, "sinyal": 0}
    s = pd.Series([f for _, f in satirlar], index=pd.DatetimeIndex([t for t, _ in satirlar])).sort_index()
    h = s.resample("W-FRI").mean().dropna()
    sonuc = ozet(h.tolist())
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
    if s["ortalama"] > 0 and p < 0.05 and tutarli:
        return "calisiyor"
    if s["ortalama"] < 0 and p < 0.05 and tutarli:
        return "ters"
    if s["p"] < 0.05 and tutarli:
        return "zayif" if s["ortalama"] > 0 else "ters_zayif"
    return "sans"


def sina(fiyatlar, kurallar=None):
    """
    fiyatlar: {kod: OHLCV}. Dönüş: {kural: {'al': özet, 'sat': özet}}.
    Giriş sinyalin ertesi günü kapanışındadır. 'sat' için fark işareti çevrilmez: SAT'ın çalışması, hissenin
    grubun gerisinde kalması (ortalamanın eksi olması) demektir; karar buna göre verilir.
    """
    kurallar = kurallar or KURALLAR
    kapanis = pd.DataFrame({k: d["Close"] for k, d in fiyatlar.items()}).sort_index()
    sinyaller = olaylar(fiyatlar, kurallar)
    sonuc, testler = {}, []
    for kimlik, r in kurallar.items():
        ileri = kapanis.shift(-r.ufuk - 1) / kapanis.shift(-1) - 1
        fark = ileri.sub(ileri.mean(axis=1), axis=0)
        al, sat = [], []
        for kod, s in sinyaller[kimlik].items():
            f = fark[kod].reindex(s.index)
            for t in s.index[(s > 0) & f.notna()]:
                al.append((t, float(f.loc[t])))
            for t in s.index[(s < 0) & f.notna()]:
                sat.append((t, -float(f.loc[t])))    # SAT için olumlu = hisse grubun gerisinde kaldı
        sonuc[kimlik] = {"al": _haftalik_ozet(al), "sat": _haftalik_ozet(sat), "ufuk": r.ufuk}
        testler += [sonuc[kimlik]["al"], sonuc[kimlik]["sat"]]
    holm(testler)
    for v in sonuc.values():
        for yon in ("al", "sat"):
            v[yon]["kanit"] = _karar(v[yon])
            v[yon].pop("karar", None)
    return sonuc


def formasyon_sinama(fiyatlar, ufuk=60):
    """Her formasyon türünde teyitli kırılışların kaçı kaynağın hedefine ufuk gün içinde ulaştı?"""
    satirlar = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for df in fiyatlar.values():
            c = df["Close"].to_numpy()
            for f in Baglam(df, gostergeler(df)).formasyonlar:
                if f.get("durum") != "teyitli" or f["kirilis"] + ufuk >= len(c):
                    continue
                sonra = c[f["kirilis"] + 1:f["kirilis"] + 1 + ufuk]
                ulasti = (sonra >= f["hedef"]).any() if f["kirilis_yon"] > 0 else (sonra <= f["hedef"]).any()
                satirlar.setdefault(f["kod"], []).append(bool(ulasti))
    return {k: {"ad": FORMASYON_ADLARI.get(k, k), "n": len(v), "hedef": sum(v) / len(v)} for k, v in satirlar.items()}


def cizgi_sinama(fiyatlar, ufuk=60):
    """
    Trend çizgisinin eğimi ve uzunluğu dayanıklılığını belirliyor mu? Kaynaklar çelişir (Altay: dik çizgi kolay kırılır;
    Gedik: dik çizgi daha güvenilir). Her çizgi sabit tutulup ufuk gün izlenir. Eğim, çizginin günlük yüzde değişimidir.
    """
    egim, uzun, kirildi = [], [], []
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
                egim.append(abs(z["n2"][1] - z["n1"][1]) / z["n1"][1] / max(1, z["n2"][0] - z["n1"][0]) * 100)
                uzun.append(z["n2"][0] - z["n1"][0])
                kirildi.append(kir)
    if len(egim) < 30:
        return None
    tablo = pd.DataFrame({"egim": egim, "uzun": uzun, "kir": kirildi})
    kesit = [float(tablo["egim"].quantile(q)) for q in (1 / 3, 2 / 3)]
    grup = pd.cut(tablo["egim"], [-1, kesit[0], kesit[1], float("inf")], labels=False)
    return {"kesit": kesit, "kirilma": [float(tablo.loc[grup == i, "kir"].mean()) for i in range(3)], "n": len(tablo), "ufuk": ufuk}
