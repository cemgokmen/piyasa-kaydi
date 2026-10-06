"""
Destek / direnç modeli.

Girdi : OHLCV tablosu (Open, High, Low, Close, Volume), tarih indeksli.
        Günlük, haftalık ya da aylık mum olabilir; mum aralığı tarih
        indeksinden anlaşılır ve gün cinsinden ayarlar ona göre çevrilir.
Çıktı : fiyat bölgeleri, her biri 0-100 arası güç puanıyla.

Tüm mesafeler ATR cinsinden ölçülür. Böylece 10 TL'lik bir hisseyle
500 dolarlık bir hisse aynı ölçekte değerlendirilir.
"""

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# AYARLAR
# ---------------------------------------------------------------------------

ATR_PERIYOT = 14
PIVOT_OLCEKLERI = (3, 5, 10, 20)   # dönüş noktası pencereleri (gün)
MIN_BELIRGINLIK = 0.75             # dönüş noktası çevresinden en az kaç ATR sivri olmalı
KDE_BANT = 0.35                    # kümeleme bant genişliği (ATR)
BOLGE_YARI = 0.30                  # bölgenin yarı genişliği (ATR)
YARILANMA_GUN = 120                # eski olayların ağırlığı bu kadar işlem gününde yarıya iner
TEPKI_PENCERE = 10                 # dokunuştan sonra tepkinin ölçüldüğü gün sayısı
KIRILMA_ESIGI = 0.75               # kapanış bölgenin bu kadar ATR ötesine geçerse kırılma
SEKME_ESIGI = 1.0                  # fiyat bölgeden bu kadar ATR geri dönerse sekme
TARAMA_ARALIGI = 8.0               # güncel fiyatın ±kaç ATR'si içindeki bölgeler raporlanır
TABAN_ORNEK = 60                   # şans oranını ölçmek için çekilen rastgele seviye sayısı

# Güç puanı ağırlıkları (toplam 1). Başlangıç değerleri — geriye dönük
# testle ayarlanacak, şimdilik makul varsayımlar.
AGIRLIK = {
    "anlamlilik":  0.40,
    "tepki":       0.15,
    "donus_yogun": 0.15,
    "hacim":       0.15,
    "cakisma":     0.10,
    "yuvarlak":    0.05,
}


# ---------------------------------------------------------------------------
# 0. MUM ARALIĞI
# ---------------------------------------------------------------------------

def mum_basina_gun(df):
    """
    Bir mumun kaç işlem gününe karşılık geldiğini tahmin eder:
    günlük 1, haftalık 5, aylık 21.

    Gün cinsinden verilen ayarlar (YARILANMA_GUN) mum sayısına bu oranla
    çevrilir. Yoksa haftalık veride 120 "gün" fiilen 120 hafta olur.
    """
    if len(df) < 3:
        return 1.0
    aralik = np.median(np.diff(df.index.values).astype("timedelta64[D]").astype(float))
    if aralik >= 25:
        return 21.0
    if aralik >= 5:
        return 5.0
    return 1.0


# ---------------------------------------------------------------------------
# 1. OYNAKLIK: ATR
# ---------------------------------------------------------------------------

def atr(df, n=ATR_PERIYOT):
    """Ortalama gerçek aralık (Wilder yumuşatması)."""
    onceki = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - onceki).abs(),
        (df["Low"] - onceki).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


# ---------------------------------------------------------------------------
# 2. DÖNÜŞ NOKTALARI (çok ölçekli)
# ---------------------------------------------------------------------------

def donus_noktalari(df, atr_seri):
    """
    Yerel tepe ve dipleri bulur.

    Bir gün, sağındaki ve solundaki k günün hepsinden yüksekse tepedir.
    Aynı nokta birden çok k değerinde tepe çıkıyorsa, en büyük k'yı alır —
    büyük pencerede tepe olan nokta daha önemlidir.

    Ayrıca "belirginlik" şartı var: tepe, iki yanındaki en düşük noktadan
    en az MIN_BELIRGINLIK × ATR yüksekte olmalı. Küçük kıpırtılar elenir.
    """
    yuksek = df["High"].to_numpy()
    dusuk = df["Low"].to_numpy()
    hacim = df["Volume"].to_numpy(dtype=float)
    atr_d = atr_seri.to_numpy()
    n = len(df)

    olcek_tepe = np.zeros(n, dtype=int)
    olcek_dip = np.zeros(n, dtype=int)

    for k in PIVOT_OLCEKLERI:
        pencere = 2 * k + 1
        mx = pd.Series(yuksek).rolling(pencere, center=True).max().to_numpy()
        mn = pd.Series(dusuk).rolling(pencere, center=True).min().to_numpy()
        olcek_tepe[(yuksek == mx)] = k
        olcek_dip[(dusuk == mn)] = k

    hacim_orta = pd.Series(hacim).rolling(50, min_periods=10).median().to_numpy()

    kayitlar = []
    for i in range(n):
        for tur, olcek_dizi in (("tepe", olcek_tepe), ("dip", olcek_dip)):
            k = olcek_dizi[i]
            if k == 0 or np.isnan(atr_d[i]) or atr_d[i] <= 0:
                continue

            sol = max(0, i - k)
            sag = min(n, i + k + 1)

            if tur == "tepe":
                fiyat = yuksek[i]
                cukur = max(dusuk[sol:i + 1].min(), dusuk[i:sag].min())
                belirginlik = (fiyat - cukur) / atr_d[i]
            else:
                fiyat = dusuk[i]
                zirve = min(yuksek[sol:i + 1].max(), yuksek[i:sag].max())
                belirginlik = (zirve - fiyat) / atr_d[i]

            if belirginlik < MIN_BELIRGINLIK:
                continue

            h_oran = 1.0
            if hacim_orta[i] and not np.isnan(hacim_orta[i]) and hacim_orta[i] > 0:
                h_oran = np.clip(hacim[i] / hacim_orta[i], 0.5, 3.0)

            kayitlar.append({
                "indeks": i,
                "tur": tur,
                "fiyat": fiyat,
                "olcek": k,
                "belirginlik": belirginlik,
                "hacim_oran": h_oran,
                "atr": atr_d[i],
            })

    return pd.DataFrame(kayitlar)


def donus_agirligi(noktalar, son_indeks, yarilanma=YARILANMA_GUN):
    """
    Her dönüş noktasının kümelemeye katkısı:
      ölçek (büyük pencere → daha önemli)
      × belirginlik
      × hacim
      × yakınlık (eski noktalar üstel olarak söner)
    """
    if noktalar.empty:
        return np.array([])

    olcek_w = np.sqrt(noktalar["olcek"] / max(PIVOT_OLCEKLERI))
    belirg_w = np.clip(noktalar["belirginlik"] / 2.0, 0.25, 2.0)
    hacim_w = np.sqrt(noktalar["hacim_oran"])
    yas = son_indeks - noktalar["indeks"]
    yakinlik_w = 0.5 ** (yas / yarilanma)

    return (olcek_w * belirg_w * hacim_w * yakinlik_w).to_numpy()


# ---------------------------------------------------------------------------
# 3. KÜMELEME: ağırlıklı çekirdek yoğunluğu
# ---------------------------------------------------------------------------

def yogunluk_egrisi(noktalar, agirliklar, izgara):
    """
    Her dönüş noktasının üstüne küçük bir çan eğrisi koyar, hepsini toplar.
    Çanlar üst üste bindikçe yoğunluk yükselir; tepe noktaları bölge
    merkezleridir. Çanın genişliği o günkü ATR'ye göre ayarlanır.
    """
    yogunluk = np.zeros_like(izgara)
    for fiyat, a, w in zip(noktalar["fiyat"], noktalar["atr"], agirliklar, strict=True):
        h = KDE_BANT * a
        yogunluk += w * np.exp(-0.5 * ((izgara - fiyat) / h) ** 2)
    return yogunluk


# ---------------------------------------------------------------------------
# 4. HACİM PROFİLİ
# ---------------------------------------------------------------------------

def hacim_profili(df, izgara, son_indeks, yarilanma=YARILANMA_GUN):
    """
    Her günün hacmini o günün en düşük–en yüksek aralığına eşit dağıtır
    (gün içi veri olmadığı için standart yaklaşım). Eski günler söner.
    """
    profil = np.zeros_like(izgara)

    for i, (dusuk, h, v) in enumerate(zip(df["Low"], df["High"], df["Volume"], strict=True)):
        if v <= 0 or h <= dusuk:
            continue
        a = np.searchsorted(izgara, dusuk)
        b = np.searchsorted(izgara, h)
        if b <= a:
            b = a + 1
        yakinlik = 0.5 ** ((son_indeks - i) / yarilanma)
        profil[a:b] += v * yakinlik / (b - a)

    # Hafif yumuşatma: tek bir kutucuktaki gürültü tepe sayılmasın
    cekirdek = np.exp(-0.5 * (np.arange(-5, 6) / 2.0) ** 2)
    cekirdek /= cekirdek.sum()
    return np.convolve(profil, cekirdek, mode="same")


# ---------------------------------------------------------------------------
# 5. KLASİK PİVOT SEVİYELERİ
# ---------------------------------------------------------------------------

def pivot_seviyeleri(df):
    """
    Önceki tamamlanmış hafta ve ayın yüksek/düşük/kapanışından
    klasik pivot seviyeleri:
        P  = (Y + D + K) / 3
        R1 = 2P − D        S1 = 2P − Y
        R2 = P + (Y − D)   S2 = P − (Y − D)
    """
    seviyeler = []
    for kural, ad in (("W-FRI", "haftalık"), ("ME", "aylık")):
        ozet = df.resample(kural).agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
        if len(ozet) < 2:
            continue
        onceki = ozet.iloc[-2]
        y, d, k = onceki["High"], onceki["Low"], onceki["Close"]
        p = (y + d + k) / 3
        for etiket, deger in (
            ("P", p),
            ("R1", 2 * p - d), ("S1", 2 * p - y),
            ("R2", p + (y - d)), ("S2", p - (y - d)),
        ):
            seviyeler.append({"fiyat": deger, "etiket": f"{ad} {etiket}"})
    return seviyeler


# ---------------------------------------------------------------------------
# 6. ADAYLARI TOPLA VE BİRLEŞTİR
# ---------------------------------------------------------------------------

def tepe_bul(egri, min_aralik, min_belirginlik=0.15):
    """
    Bir eğrideki belirgin yerel maksimumları bulur.
    Belirginlik: tepenin, iki yanındaki en yüksek çukurdan ne kadar
    yükseldiği (eğrinin maksimumuna oranla). Düz bölgelerdeki küçük
    kıpırtılar böylece tepe sayılmaz.
    """
    from scipy.signal import find_peaks
    if egri.max() <= 0:
        return np.array([], dtype=int)
    tepeler, _ = find_peaks(
        egri,
        distance=max(1, min_aralik),
        prominence=egri.max() * min_belirginlik,
    )
    return tepeler


def adaylari_birlestir(adaylar, tolerans):
    """Birbirine tolerans kadar yakın aday seviyeleri tek bölgede toplar."""
    adaylar = sorted(adaylar, key=lambda a: a["fiyat"])
    gruplar = []
    for a in adaylar:
        if gruplar and a["fiyat"] - gruplar[-1]["fiyatlar"][-1] <= tolerans:
            gruplar[-1]["fiyatlar"].append(a["fiyat"])
            gruplar[-1]["kaynaklar"].add(a["kaynak"])
            gruplar[-1]["etiketler"].extend(a.get("etiketler", []))
        else:
            gruplar.append({
                "fiyatlar": [a["fiyat"]],
                "kaynaklar": {a["kaynak"]},
                "etiketler": list(a.get("etiketler", [])),
            })
    for g in gruplar:
        g["merkez"] = float(np.median(g["fiyatlar"]))
    return gruplar


# ---------------------------------------------------------------------------
# 7. SINAMA: fiyat bölgeye kaç kez geldi, ne oldu
# ---------------------------------------------------------------------------

def bolgeyi_sina(df, atr_seri, merkez, yari_genislik, son_indeks,
                 yarilanma=YARILANMA_GUN):
    """
    Fiyatın bölgeye her gelişini bir "test" sayar (art arda günler tek test).

    Her test için sonraki TEPKI_PENCERE güne gün gün bakılır ve hangisinin
    ÖNCE olduğu sorulur:
      - sekme  : fiyat bölgeden SEKME_ESIGI × ATR geri döndü   → tutundu
      - kırılma: kapanış bölgenin KIRILMA_ESIGI × ATR ötesinde → kırıldı
    İkisi de olmadıysa test belirsizdir ve hesaba katılmaz — fiyatın
    bölgenin yanında yatay oyalanması "tutunma" sayılmaz.
    Aynı gün ikisi birden olursa temkinli davranıp kırılma sayılır.
    """
    yuksek = df["High"].to_numpy()
    dusuk = df["Low"].to_numpy()
    kapanis = df["Close"].to_numpy()
    atr_d = atr_seri.to_numpy()

    alt = merkez - yari_genislik
    ust = merkez + yari_genislik
    temas = (dusuk <= ust) & (yuksek >= alt)

    testler = []
    i = 1
    n = len(df)
    while i < n:
        if not temas[i]:
            i += 1
            continue

        bas = i
        while i < n and temas[i]:
            i += 1
        bit = i - 1

        yon = "ustten" if kapanis[bas - 1] > merkez else "alttan"

        son = min(n, bit + 1 + TEPKI_PENCERE)
        if son <= bit + 1:
            continue

        a = atr_d[bit] if atr_d[bit] > 0 else np.nanmean(atr_d)

        sonuc = None
        for j in range(bit + 1, son):
            if yon == "ustten":        # destek testi
                kirildi = kapanis[j] < alt - KIRILMA_ESIGI * a
                sekti = yuksek[j] - ust >= SEKME_ESIGI * a
            else:                      # direnç testi
                kirildi = kapanis[j] > ust + KIRILMA_ESIGI * a
                sekti = alt - dusuk[j] >= SEKME_ESIGI * a
            if kirildi:
                sonuc = False
                break
            if sekti:
                sonuc = True
                break

        if sonuc is None:
            continue  # belirsiz: ne sekti ne kırıldı

        if yon == "ustten":
            tepki = (yuksek[bit + 1:son].max() - merkez) / a
        else:
            tepki = (merkez - dusuk[bit + 1:son].min()) / a

        testler.append({
            "indeks": bit,
            "tutundu": sonuc,
            "tepki": max(0.0, float(tepki)),
            "agirlik": 0.5 ** ((son_indeks - bit) / yarilanma),
        })

    return testler


# ---------------------------------------------------------------------------
# 8. ŞANS ORANI (boş hipotez)
# ---------------------------------------------------------------------------

def taban_oranlari(df, atr_seri, yari, son_indeks, rng, yarilanma=YARILANMA_GUN):
    """
    Aynı fiyat serisinde rastgele çizgiler çeker ve onların tutunma
    oranını ölçer. Bu, "hiçbir özelliği olmayan bir seviye ne sıklıkla
    tutunuyor gibi görünür" sorusunun cevabı — yani şans oranı.

    Gerçek bir destek/direnç bu oranın anlamlı ölçüde üstünde olmalı.
    """
    alt = float(df["Low"].quantile(0.05))
    ust = float(df["High"].quantile(0.95))
    seviyeler = rng.uniform(alt, ust, TABAN_ORNEK)

    toplam = tutunan = 0.0
    tepkiler = []
    for sev in seviyeler:
        for t in bolgeyi_sina(df, atr_seri, sev, yari, son_indeks, yarilanma):
            toplam += t["agirlik"]
            if t["tutundu"]:
                tutunan += t["agirlik"]
                tepkiler.append(t["tepki"])

    p = tutunan / toplam if toplam > 0 else 0.5
    p = float(np.clip(p, 0.05, 0.95))
    tepki = float(np.mean(tepkiler)) if tepkiler else 1.0
    return p, tepki


# ---------------------------------------------------------------------------
# 9. PUANLAMA
# ---------------------------------------------------------------------------

def yuvarlak_sayi_puani(fiyat, tolerans):
    """Psikolojik seviyelere (100, 150, 42.5 gibi) yakınlık."""
    if fiyat <= 0:
        return 0.0
    basamak = 10 ** np.floor(np.log10(fiyat))
    for adim in (basamak, basamak / 2, basamak / 4):
        if abs(fiyat - round(fiyat / adim) * adim) <= tolerans:
            return {basamak: 1.0, basamak / 2: 0.7, basamak / 4: 0.4}[adim]
    return 0.0


def bolgeleri_hesapla(df, bitis=None):
    """
    Ana fonksiyon.

    bitis verilirse yalnızca o tarihe kadarki veri kullanılır — geriye
    dönük testte geleceği görmeden hesap yapabilmek için.
    """
    if bitis is not None:
        df = df.loc[:bitis]

    df = df.dropna(subset=["Open", "High", "Low", "Close"]).copy()
    if len(df) < 60:
        raise ValueError("En az 60 mumluk veri gerekli.")

    # Gün cinsinden yarılanma süresini mum sayısına çevir
    mum_gun = mum_basina_gun(df)
    yarilanma = YARILANMA_GUN / mum_gun

    atr_seri = atr(df)
    son = len(df) - 1
    son_atr = float(atr_seri.iloc[-1])
    son_fiyat = float(df["Close"].iloc[-1])

    # Ortak fiyat ızgarası
    adim = son_atr * 0.05
    izgara = np.arange(df["Low"].min() - son_atr, df["High"].max() + son_atr, adim)

    # --- Kaynak 1: dönüş noktası kümeleri
    noktalar = donus_noktalari(df, atr_seri)
    agirliklar = donus_agirligi(noktalar, son, yarilanma)
    yogunluk = yogunluk_egrisi(noktalar, agirliklar, izgara) if len(noktalar) else np.zeros_like(izgara)

    # --- Kaynak 2: hacim profili
    profil = hacim_profili(df, izgara, son, yarilanma)

    min_aralik = int((2 * BOLGE_YARI * son_atr) / adim)
    adaylar = []

    for t in tepe_bul(yogunluk, min_aralik):
        adaylar.append({"fiyat": izgara[t], "kaynak": "donus"})
    for t in tepe_bul(profil, min_aralik):
        adaylar.append({"fiyat": izgara[t], "kaynak": "hacim"})

    # --- Kaynak 3: pivot seviyeleri
    for p in pivot_seviyeleri(df):
        adaylar.append({"fiyat": p["fiyat"], "kaynak": "pivot", "etiketler": [p["etiket"]]})

    bolgeler = adaylari_birlestir(adaylar, tolerans=2 * BOLGE_YARI * son_atr)

    # Normalleştirme için maksimumlar
    y_max = yogunluk.max() if yogunluk.max() > 0 else 1.0
    p_orta = float(np.median(profil[profil > 0])) if np.any(profil > 0) else 0.0
    p_ust = profil.max() - p_orta if profil.max() > p_orta else 1.0

    sonuc = []
    yari = BOLGE_YARI * son_atr

    # Aynı veri her çağrıda aynı sonucu versin diye sabit tohum
    rng = np.random.default_rng(12345)
    taban_p, taban_tepki = taban_oranlari(df, atr_seri, yari, son, rng, yarilanma)

    for b in bolgeler:
        merkez = b["merkez"]
        uzaklik_atr = (merkez - son_fiyat) / son_atr
        if abs(uzaklik_atr) > TARAMA_ARALIGI:
            continue

        testler = bolgeyi_sina(df, atr_seri, merkez, yari, son, yarilanma)
        w_toplam = sum(t["agirlik"] for t in testler)
        w_tutunan = sum(t["agirlik"] for t in testler if t["tutundu"])

        # --- Anlamlılık: ağırlıklı binom z-skoru
        # Tutunma oranı: p̂ = Σ(w · tutundu) / Σw
        # Eski testler düşük ağırlıklı olduğu için gerçek bilgi miktarı
        # test sayısından azdır. Doğru etkin örnek sayısı:
        #     n_etkin = (Σw)² / Σw²
        # z = (p̂ − p₀) / √(p₀(1−p₀) / n_etkin)
        # p₀ = şans oranı. z ≥ 2 kabaca "%97,7 ihtimalle şans değil".
        w_kare = sum(t["agirlik"] ** 2 for t in testler)
        if w_toplam > 0 and w_kare > 0:
            p_sapka = w_tutunan / w_toplam
            n_etkin = w_toplam ** 2 / w_kare
            z = (p_sapka - taban_p) / np.sqrt(taban_p * (1 - taban_p) / n_etkin)
        else:
            z = 0.0

        tutunan_tepki = [t["tepki"] for t in testler if t["tutundu"]]
        ort_tepki = float(np.mean(tutunan_tepki)) if tutunan_tepki else 0.0

        idx = np.clip(np.searchsorted(izgara, merkez), 0, len(izgara) - 1)

        ozellik = {
            "anlamlilik":  float(np.clip(z / 3.0, 0, 1)),
            # Tepki de şansa göre: rastgele seviyelerden ne kadar fazla?
            "tepki":       float(np.clip((ort_tepki - taban_tepki) / taban_tepki, 0, 1)),
            "donus_yogun": yogunluk[idx] / y_max,
            "hacim":       float(np.clip((profil[idx] - p_orta) / p_ust, 0, 1)),
            "cakisma":     len(b["kaynaklar"]) / 3,
            "yuvarlak":    yuvarlak_sayi_puani(merkez, yari),
        }
        puan = 100 * sum(AGIRLIK[k] * v for k, v in ozellik.items())

        sonuc.append({
            "merkez": round(merkez, 4),
            "alt": round(merkez - yari, 4),
            "ust": round(merkez + yari, 4),
            "tur": "destek" if merkez < son_fiyat else "direnç",
            "puan": round(puan, 1),
            "uzaklik_yuzde": round((merkez / son_fiyat - 1) * 100, 2),
            "uzaklik_atr": round(uzaklik_atr, 2),
            "test": len(testler),
            "tutunan": sum(1 for t in testler if t["tutundu"]),
            "ort_tepki_atr": round(ort_tepki, 2),
            "z": round(float(z), 2),
            "kaynaklar": ", ".join(sorted(b["kaynaklar"])),
            "etiketler": ", ".join(b["etiketler"]),
            "son_test": df.index[testler[-1]["indeks"]].date() if testler else None,
            "ozellikler": {k: round(float(v), 3) for k, v in ozellik.items()},
        })

    sonuc.sort(key=lambda s: s["merkez"], reverse=True)
    return {
        "fiyat": son_fiyat,
        "atr": son_atr,
        "sans_orani": round(taban_p, 3),
        "sans_tepki": round(taban_tepki, 2),
        "tarih": df.index[-1].date(),
        "mum_gun": mum_gun,
        "yarilanma_mum": round(yarilanma, 1),
        "bolgeler": sonuc,
    }
