"""
Trend çizgileri ve klasik grafik formasyonları (Altay 1997, s. 79–109).

Hepsi teyit günü bilinen tepe-diplerden (yapi.zigzag_teyitli) kurulur, geleceği görmez: aynı kod hem
bugünkü durumu okur hem geçmişteki kırılımları sınamaya verir.

Teyit eşikleri kaynaktandır:
  trend çizgisi  kapanış çizginin %3 ötesinde ya da 3 gün üst üste çizginin dışında; %3'ten küçük
                 tek günlük delme çizgiyi bozmaz. Hacim artışı ayrıca belirtilir.
  OBO            boyun çizgisinin yaklaşık %5 ötesinde kapanış
  üçgen hedefi   ilk köşeden karşı kenara çizilen paralel (Altay s. 83–109; Gedik 2021 s. 33)
  bayrak, flama  en çok bir iki hafta sürer, hacim düşer, kırılışta artar; hedef sap boyu (Gedik 2021 s. 35–36)
  kama           alçalan kama yukarı, yükselen kama aşağı kırılır; hedef sap boyu (Altay; Gedik 2021 s. 37)
  yukarı kırılış formasyon ortalamasının en az 1,5 katı hacim; aşağı kırılışta hacim şartı yok
"""

import numpy as np

from piyasa.analiz.teknik.yapi import zigzag_teyitli

DELME = 0.03
OBO_TEYIT = 0.05
HACIM_KAT = 1.5
AYNI_SEVIYE = 0.03          # iki tepe/dip bu oran kadar yakınsa "aynı seviye" sayılır
OMUZ_FARKI = 0.10
EN_COK_BEKLEME = 60         # formasyon bu kadar günde kırılmazsa geçerliliğini yitirir
BAYRAK_DIREK_GUN = 15
BAYRAK_DIREK_ATR = 5.0
BAYRAK_GUN = 10
BAYRAK_GERI = 0.5


def _cizgi(n1, n2):
    """İki noktadan geçen doğru: gün → fiyat."""
    egim = (n2[1] - n1[1]) / max(1, n2[0] - n1[0])
    return lambda i: n1[1] + egim * (i - n1[0])


def _ort_hacim(hacim, bas, bit):
    parca = hacim[max(0, bas):bit]
    parca = parca[parca > 0]
    return float(parca.mean()) if len(parca) else None


# ---------------------------------------------------------------------------
# Trend çizgileri
# ---------------------------------------------------------------------------

def trend_cizgileri(df, noktalar=None):
    """
    Her teyitli çift için çizgi ve varsa kırılma günü. Yükselen dipler destek, alçalan tepeler direnç çizgisidir.
    Dönüş: [{tur, yon, n1, n2, kirilis, hacimli, gecerli}] (eskiden yeniye).
    yon: kırılınca beklenen hareket (destek çizgisi kırılırsa −1, direnç çizgisi kırılırsa +1).
    """
    if noktalar is None:
        from piyasa.analiz.destek_direnc import atr
        noktalar, _ = zigzag_teyitli(df, atr(df))
    kapanis, hacim = df["Close"].to_numpy(), df["Volume"].to_numpy(dtype=float)
    m = len(df)
    sonuc = []
    for tur in ("dip", "tepe"):
        secili = [n for n in noktalar if n[2] == tur]
        for i, (n1, n2) in enumerate(zip(secili, secili[1:], strict=False)):
            if (tur == "dip") != (n2[1] > n1[1]):
                continue
            bitis = secili[i + 2][3] if i + 2 < len(secili) else m     # sonraki pivot çizgiyi yeniler
            f = _cizgi(n1, n2)
            kirilis, dista = None, 0
            for g in range(n2[3] + 1, bitis):
                c = f(g)
                fark = (c - kapanis[g]) / c if tur == "dip" else (kapanis[g] - c) / c
                dista = dista + 1 if fark > 0 else 0
                if fark >= DELME or dista >= 3:
                    kirilis = g
                    break
            ort = _ort_hacim(hacim, kirilis - 20, kirilis) if kirilis else None
            # Kanal: çizginin paraleli, iki nokta arasındaki karşı uçtan geçer
            karsi = [p for p in noktalar if p[2] != tur and n1[0] < p[0] < n2[0]]
            kanal = None
            if karsi:
                uc = max(karsi, key=lambda p: p[1]) if tur == "dip" else min(karsi, key=lambda p: p[1])
                kanal = uc[1] - f(uc[0])
            sonuc.append({"tur": "destek" if tur == "dip" else "direnç", "yon": -1 if tur == "dip" else 1,
                          "n1": n1, "n2": n2, "kirilis": kirilis, "hacimli": bool(ort and hacim[kirilis] >= HACIM_KAT * ort),
                          "gecerli": kirilis is None and bitis == m, "cizgi": f, "bitis": bitis, "kanal": kanal})
    return sorted(sonuc, key=lambda s: s["n2"][3])


# ---------------------------------------------------------------------------
# Formasyonlar
# ---------------------------------------------------------------------------

def _obo(p, ters, onceki, hacim, kapanis):
    """
    p: ardışık beş nokta (sol omuz, dip, baş, dip, sağ omuz). ters=True: ters OBO.
    onceki: formasyondan önceki nokta. Asgari hedef, baştan boyna mesafe ile önceki hareketin küçüğüdür.
    """
    sol, d1, bas, d2, sag = p
    isaret = -1 if ters else 1          # ters formasyonda bütün karşılaştırmalar aynalanır
    if not (isaret * bas[1] > isaret * sol[1] and isaret * bas[1] > isaret * sag[1]):
        return None
    if abs(sol[1] - sag[1]) / bas[1] > OMUZ_FARKI:
        return None
    boyun = _cizgi(d1, d2)
    baslangic, teyit = sol[0], sag[3]
    if isaret * (boyun(teyit) - kapanis[teyit]) >= 0:   # sağ omuz biterken boyun çoktan kırılmışsa
        return None
    v_sol, v_bas, v_sag = _ort_hacim(hacim, sol[0] - 3, sol[0] + 4), _ort_hacim(hacim, bas[0] - 3, bas[0] + 4), _ort_hacim(hacim, sag[0] - 3, sag[0] + 4)
    hacim_uygun = None if not (v_sol and v_bas and v_sag) else v_sag < max(v_sol, v_bas)
    yukseklik = abs(bas[1] - boyun(bas[0]))
    if onceki:
        yukseklik = min(yukseklik, abs(bas[1] - onceki[1]))
    return {"ad": "Ters omuz-baş-omuz" if ters else "Omuz-baş-omuz", "kod": "tobo" if ters else "obo",
            "yon": 1 if ters else -1, "bas": baslangic, "son": teyit, "ust": boyun, "alt": boyun, "esik": OBO_TEYIT,
            "yukseklik": yukseklik, "hacim_uygun": hacim_uygun, "egim": d2[1] - d1[1]}


def _kutu(p):
    """p: ardışık dört nokta. Üçgen, dikdörtgen, kama ya da genişleme sınıfı ve çizgileri."""
    tepeler = [n for n in p if n[2] == "tepe"]
    dipler = [n for n in p if n[2] == "dip"]
    if len(tepeler) != 2 or len(dipler) != 2:
        return None
    t = (tepeler[1][1] - tepeler[0][1]) / tepeler[0][1]
    d = (dipler[1][1] - dipler[0][1]) / dipler[0][1]
    t_yatay, d_yatay = abs(t) <= AYNI_SEVIYE, abs(d) <= AYNI_SEVIYE
    ust, alt = _cizgi(*tepeler), _cizgi(*dipler)
    daraliyor = ust(p[-1][0]) - alt(p[-1][0]) < 0.8 * (ust(p[0][0]) - alt(p[0][0]))
    if t_yatay and d_yatay:
        return "Dikdörtgen", "dikdortgen", tepeler, dipler
    if t_yatay and d > 0:
        return "Yükselen üçgen", "yukselen_ucgen", tepeler, dipler
    if d_yatay and t < 0:
        return "Alçalan üçgen", "alcalan_ucgen", tepeler, dipler
    if t < 0 < d:
        return "Simetrik üçgen", "simetrik_ucgen", tepeler, dipler
    if t < 0 and d < 0 and daraliyor:
        return "Alçalan kama", "alcalan_kama", tepeler, dipler
    if t > 0 and d > 0 and daraliyor:
        return "Yükselen kama", "yukselen_kama", tepeler, dipler
    if t > 0 > d:
        return "Genişleme", "genisleme", tepeler, dipler
    return None


def _egim(n1, n2):
    return (n2[1] - n1[1]) / max(1, n2[0] - n1[0])


def _paralel_hedef(ilk_tepe, ilk_dip, alt_egim, ust_egim):
    """İlk köşeden karşı kenarın paraleli: hedef, bu doğrunun kırılış günündeki değeridir."""
    def hedef(g, yon):
        if yon > 0:
            return ilk_tepe[1] + alt_egim * (g - ilk_tepe[0])
        return ilk_dip[1] + ust_egim * (g - ilk_dip[0])
    return hedef


def _kutu_formasyonu(p, kapanis, onceki=None):
    k = _kutu(p)
    if not k:
        return None
    ad, kod, tepeler, dipler = k
    ust, alt = _cizgi(*tepeler), _cizgi(*dipler)
    bas, son = p[0][0], p[-1][3]
    if not alt(son) < kapanis[son] < ust(son):
        return None
    yukseklik = abs(ust(bas) - alt(bas))
    hedef_f = None
    if kod.endswith("ucgen"):
        hedef_f = _paralel_hedef(tepeler[0], dipler[0], _egim(*dipler), _egim(*tepeler))
    elif kod.endswith("kama"):
        yukseklik = abs(p[0][1] - onceki[1]) if onceki else yukseklik      # hedef sapın boyudur
    elif kod == "genisleme":
        yukseklik = abs(ust(p[-1][0]) - alt(p[-1][0]))
    # Üçgene kırılmadan yön verilmez: kaynaklar düz kenardan kırılır der, BIST 100'de kırılışların çoğu eğimli kenardandır
    # (notlar/tspakb-2011.md). Kamalarda kaynağın yönü iki dönemde de tutar.
    yon = {"alcalan_kama": 1, "yukselen_kama": -1, "genisleme": -1}.get(kod, 0)
    return {"ad": ad, "kod": kod, "yon": yon, "bas": bas, "son": son, "ust": ust, "alt": alt, "hedef_f": hedef_f,
            "esik": 0.0 if kod != "dikdortgen" else DELME, "yukseklik": yukseklik, "hacim_uygun": None, "egim": None}


def _bayrak(direk_bas, direk_son, atr_d):
    """Dik hareket (direk) sonrası kısa, hacmi düşen sıkışma."""
    yukari = direk_son[1] > direk_bas[1]
    boy = abs(direk_son[1] - direk_bas[1])
    if direk_son[0] - direk_bas[0] > BAYRAK_DIREK_GUN or boy < BAYRAK_DIREK_ATR * atr_d[direk_son[0]]:
        return None
    ad = "Yükseliş bayrağı/flaması" if yukari else "Düşüş bayrağı/flaması"
    return {"ad": ad, "kod": "bayrak", "yon": 1 if yukari else -1, "bas": direk_bas[0], "son": direk_son[3],
            "direk_son": direk_son[0], "yukseklik": boy, "hacim_uygun": None, "egim": None, "esik": 0.0, "bayrak": True,
            "ust": None, "alt": None, "uc": direk_son[1], "dip": direk_son[1] - (1 if yukari else -1) * BAYRAK_GERI * boy}


def _ilerlet(f, df, kapanis, hacim, en_son):
    """
    Formasyonu teyitten sonra gün gün izler: kırılış, hacim teyidi, hedef.
    f['durum']: 'olusuyor' | 'teyitli' | 'hacimsiz' | 'bozuldu'.
    """
    bayrak = f.get("bayrak")
    bekleme = BAYRAK_GUN if bayrak else EN_COK_BEKLEME
    ort = _ort_hacim(hacim, f["bas"], f["son"] + 1)
    for g in range(f["son"] + 1, min(en_son + 1, f["son"] + 1 + bekleme)):
        c = kapanis[g]
        if bayrak:
            yukari = f["yon"] > 0
            if (yukari and c < f["dip"]) or (not yukari and c > f["dip"]):
                f.update(durum="bozuldu", kirilis=g)
                return f
            aralik = df["High"].to_numpy()[f["direk_son"] + 1:g] if yukari else df["Low"].to_numpy()[f["direk_son"] + 1:g]
            if not len(aralik):
                continue
            sinir = aralik.max() if yukari else aralik.min()
            kirdi_yukari, kirdi_asagi = yukari and c > sinir, (not yukari) and c < sinir
            ust_esik = alt_esik = sinir
        else:
            ust_esik = f["ust"](g) * (1 + f["esik"])
            alt_esik = f["alt"](g) * (1 - f["esik"])
            if f["kod"] in ("obo", "tobo"):
                kirdi_yukari, kirdi_asagi = f["kod"] == "tobo" and c >= ust_esik, f["kod"] == "obo" and c <= alt_esik
            else:
                kirdi_yukari, kirdi_asagi = c > ust_esik, c < alt_esik
        if not (kirdi_yukari or kirdi_asagi):
            continue
        yon = 1 if kirdi_yukari else -1
        if bayrak:
            # Oluşurken hacim düşmeli; kırılış bayrağın kendi ortalamasıyla ölçülür (sapın yüksek hacmi şişirmesin)
            ort = _ort_hacim(hacim, f["direk_son"] + 1, g)
            sap = _ort_hacim(hacim, f["bas"], f["direk_son"] + 1)
            if ort and sap and ort >= sap:
                f.update(durum="bozuldu", kirilis=g)
                return f
        hacimli = bool(ort and hacim[g] >= HACIM_KAT * ort)
        if yon == 1:
            f["durum"] = "teyitli" if hacimli else "hacimsiz"
        else:
            f["durum"] = "teyitli"              # aşağı kırılışta hacim şartı yok
        f.update(kirilis=g, kirilis_yon=yon, hacimli=hacimli, kirilis_fiyat=float(c),
                 hedef=float(f["hedef_f"](g, yon) if f.get("hedef_f") else c + yon * f["yukseklik"]), yon=yon)
        return f
    f["durum"] = "olusuyor" if en_son < f["son"] + 1 + bekleme else "bozuldu"
    return f


def klasik_formasyonlar(df, noktalar, atr_seri):
    """Bütün geçmişteki formasyonlar, eskiden yeniye. Geleceği görmez: her biri ancak 'son' gününde bilinir."""
    kapanis, hacim = df["Close"].to_numpy(), df["Volume"].to_numpy(dtype=float)
    atr_d = atr_seri.to_numpy()
    en_son = len(df) - 1
    sonuc = []
    for i in range(len(noktalar)):
        n = noktalar[i]
        adaylar = []
        if i >= 4:
            p = noktalar[i - 4:i + 1]
            adaylar.append(_obo(p, n[2] == "dip", noktalar[i - 5] if i >= 5 else None, hacim, kapanis))
        if i >= 3:
            adaylar.append(_kutu_formasyonu(noktalar[i - 3:i + 1], kapanis, noktalar[i - 4] if i >= 4 else None))
        if i >= 1:
            adaylar.append(_bayrak(noktalar[i - 1], n, atr_d))
        for f in adaylar:
            if f and f["son"] <= en_son:
                sonuc.append(_ilerlet(f, df, kapanis, hacim, en_son))
    return sonuc


def guncel_cizgiler(cizgiler, df):
    """Hâlâ geçerli son destek ve direnç çizgisi ile son 20 günde kırılan çizgiler (sunuma hazır)."""
    son = len(df) - 1
    sonuc = []
    for tur in ("destek", "direnç"):
        secili = [c for c in cizgiler if c["tur"] == tur]
        gecerli = [c for c in secili if c["gecerli"]]
        # Yeni bir çizgi kırılanın yerini aldıysa eskisi gösterilmez
        kirilan = [c for c in secili if c["kirilis"] is not None and son - c["kirilis"] <= 20 and not gecerli]
        for c, durum in ((gecerli[-1] if gecerli else None, "gecerli"), (kirilan[-1] if kirilan else None, "kirildi")):
            if c:
                sonuc.append({"tur": tur, "durum": durum, "yon": c["yon"], "hacimli": c["hacimli"],
                              "t1": df.index[c["n1"][0]].strftime("%Y-%m-%d"), "f1": round(c["n1"][1], 4),
                              "t2": df.index[c["n2"][0]].strftime("%Y-%m-%d"), "f2": round(c["n2"][1], 4),
                              "t3": df.index[-1].strftime("%Y-%m-%d"), "f3": round(float(c["cizgi"](son)), 4),
                              "uzun": c["n2"][0] - c["n1"][0],
                              "egim": abs(c["n2"][1] - c["n1"][1]) / c["n1"][1] / max(1, c["n2"][0] - c["n1"][0]) * 100,
                              "kanal_f1": round(c["n1"][1] + c["kanal"], 4) if c["kanal"] is not None else None,
                              "kanal_f3": round(float(c["cizgi"](son)) + c["kanal"], 4) if c["kanal"] is not None else None,
                              "kirilis_tarih": df.index[c["kirilis"]].date() if c["kirilis"] is not None else None})
    return sonuc


def guncel_formasyonlar(formasyonlar, df, pencere=20):
    """Oluşmakta olan ya da son günlerde kırılan formasyonlar; aynı türden yalnızca en yenisi."""
    son = len(df) - 1
    secili = {}
    # Oluşmakta olanlardan yalnızca son tepe-dibe dayananlar: öncekiler yeni noktayla geçersizleşmiştir
    en_yeni = max((f["son"] for f in formasyonlar), default=None)
    for f in formasyonlar:
        kirilis = f.get("kirilis")
        guncel = (f["durum"] == "olusuyor" and f["son"] == en_yeni) or (f["durum"] in ("teyitli", "hacimsiz") and son - kirilis <= pencere)
        if guncel:
            secili[f["kod"] if f["kod"] != "bayrak" else f["ad"]] = f
    return sorted(secili.values(), key=lambda f: f["son"], reverse=True)


def formasyon_olaylari(formasyonlar, m):
    """Geçmiş sınaması için: teyitli kırılış günlerinde yön (+1/−1), öteki günler 0."""
    olay = np.zeros(m)
    for f in formasyonlar:
        if f.get("durum") == "teyitli":
            olay[f["kirilis"]] = f["kirilis_yon"]
    return olay
