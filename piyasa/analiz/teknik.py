"""
Teknik analiz: göstergeler, puanlama ve grafik okuması.

Girdi : günlük OHLCV tablosu (Open, High, Low, Close, Volume), tarih indeksli; en az ~1 yıl,
        tercihen 3-5 yıl. İsteğe bağlı olarak aynı tarihlerde endeksin kapanış serisi.
Çıktı : son günün göstergeleri, bileşen puanları, üç vade için teknik puan ve Türkçe okuma.

Puanlama bütün geçmiş için vektörel hesaplanır (puan_serileri). Böylece aynı kural, geçmişte
verdiği puanlardan sonra fiyatın ne yaptığıyla sınanabilir (gecmis_isabet) — kurallar
kanıtla ayarlanır, sezgiyle değil.

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

from piyasa.analiz.destek_direnc import atr as atr_hesapla
from piyasa.bicim import ek, ondalik
from piyasa.bicim import fiyat as _p

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

YILLIK = 252


def _o(x, n=1):
    return ondalik(x, n)


# ---------------------------------------------------------------------------
# 1. GÖSTERGELER (hepsi seri döndürür)
# ---------------------------------------------------------------------------

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


def stokastik(df, n=14, d=3):
    en_dusuk = df["Low"].rolling(n, min_periods=n).min()
    en_yuksek = df["High"].rolling(n, min_periods=n).max()
    k = 100 * (df["Close"] - en_dusuk) / (en_yuksek - en_dusuk).replace(0, np.nan)
    return k, k.rolling(d).mean()


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


def zigzag(df, atr_seri, katsayi=2.0):
    """
    Anlamlı tepe ve dipler: fiyat son uç noktadan en az katsayi × ATR geri dönünce uç kesinleşir.
    [(indeks, fiyat, 'tepe'|'dip'), ...] ve henüz kesinleşmemiş son uç.
    """
    yuksek, dusuk = df["High"].to_numpy(), df["Low"].to_numpy()
    a = atr_seri.bfill().to_numpy()
    noktalar = []
    yon = 1
    uc_i, uc_f = 0, yuksek[0]
    for i in range(1, len(df)):
        esik = katsayi * a[i]
        if yon > 0:
            if yuksek[i] >= uc_f:
                uc_i, uc_f = i, yuksek[i]
            elif uc_f - dusuk[i] > esik:
                noktalar.append((uc_i, float(uc_f), "tepe"))
                yon, uc_i, uc_f = -1, i, dusuk[i]
        else:
            if dusuk[i] <= uc_f:
                uc_i, uc_f = i, dusuk[i]
            elif yuksek[i] - uc_f > esik:
                noktalar.append((uc_i, float(uc_f), "dip"))
                yon, uc_i, uc_f = 1, i, yuksek[i]
    son = (uc_i, float(uc_f), "tepe" if yon > 0 else "dip")
    return noktalar, son


# ---------------------------------------------------------------------------
# 2. GÖSTERGE TABLOSU
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 3. PUANLAMA (vektörel: her gün için)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 5. MUM VE GRAFİK FORMASYONLARI
# ---------------------------------------------------------------------------

def mum_formasyonlari(df, g):
    """Son mum(lar)da bilinen formasyonlar. Bağlam (trend, destek) okumada eklenir."""
    if len(df) < 5:
        return []
    o, h, lo, c = (df[k].to_numpy()[-3:] for k in ("Open", "High", "Low", "Close"))
    a = float(g["atr"].iloc[-1]) or 1e-9
    govde = np.abs(c - o)
    aralik = np.maximum(h - lo, 1e-9)
    ust_fitil = h - np.maximum(o, c)
    alt_fitil = np.minimum(o, c) - lo
    dusus_oncesi = df["Close"].iloc[-1] < df["Close"].iloc[-6] if len(df) > 6 else False
    yukselis_oncesi = df["Close"].iloc[-1] > df["Close"].iloc[-6] if len(df) > 6 else False
    sonuc = []

    def ekle(ad, yon, aciklama):
        sonuc.append({"ad": ad, "yon": yon, "aciklama": aciklama})

    # Yutan mumlar
    if c[-2] < o[-2] and c[-1] > o[-1] and c[-1] >= o[-2] and o[-1] <= c[-2] and govde[-1] > govde[-2]:
        ekle("Yükselen yutan mum", 1, "Son mumun gövdesi bir önceki düşüş mumunu tamamen içine aldı; alıcılar kontrolü ele aldı.")
    if c[-2] > o[-2] and c[-1] < o[-1] and c[-1] <= o[-2] and o[-1] >= c[-2] and govde[-1] > govde[-2]:
        ekle("Düşen yutan mum", -1, "Son mumun gövdesi bir önceki yükseliş mumunu tamamen içine aldı; satıcılar baskın.")
    # Çekiç / ters çekiç / kayan yıldız / asılı adam
    if alt_fitil[-1] >= 2 * govde[-1] and ust_fitil[-1] <= 0.3 * aralik[-1] and aralik[-1] > 0.6 * a:
        if dusus_oncesi:
            ekle("Çekiç", 1, "Düşüşten sonra uzun alt fitil: gün içinde satış geldi ama alıcılar fiyatı geri topladı.")
        elif yukselis_oncesi:
            ekle("Asılı adam", -1, "Yükselişten sonra uzun alt fitil: gün içi sert satış, alıcıların gücü sorgulanıyor.")
    if ust_fitil[-1] >= 2 * govde[-1] and alt_fitil[-1] <= 0.3 * aralik[-1] and aralik[-1] > 0.6 * a:
        if yukselis_oncesi:
            ekle("Kayan yıldız", -1, "Yükselişten sonra uzun üst fitil: yukarıda satış baskısı var, fiyat zirveden geri itildi.")
        elif dusus_oncesi:
            ekle("Ters çekiç", 1, "Düşüşten sonra uzun üst fitil: alıcılar ilk kez yukarı denedi; ertesi gün teyit gerekir.")
    # Doji
    if govde[-1] <= 0.1 * aralik[-1] and aralik[-1] > 0.3 * a:
        ekle("Doji", 0, "Açılış ve kapanış neredeyse aynı: kararsızlık. Trendin sonunda dönüş habercisi olabilir.")
    # Sabah / akşam yıldızı
    if (c[-3] < o[-3] and govde[-3] > 0.6 * a and govde[-2] < 0.35 * govde[-3]
            and c[-1] > o[-1] and c[-1] > (o[-3] + c[-3]) / 2):
        ekle("Sabah yıldızı", 1, "Üç mumluk dönüş: güçlü düşüş, kararsız gün, sonra düşüşün yarısını aşan yükseliş.")
    if (c[-3] > o[-3] and govde[-3] > 0.6 * a and govde[-2] < 0.35 * govde[-3]
            and c[-1] < o[-1] and c[-1] < (o[-3] + c[-3]) / 2):
        ekle("Akşam yıldızı", -1, "Üç mumluk dönüş: güçlü yükseliş, kararsız gün, sonra yükselişin yarısını silen düşüş.")
    # İçeride mum (sıkışma)
    if h[-1] < h[-2] and lo[-1] > lo[-2]:
        ekle("İçeride mum", 0, "Son mum bir öncekinin aralığında kaldı: sıkışma. Hangi yöne kırılırsa o yön önemli.")
    return sonuc


def grafik_formasyonlari(df, g, noktalar):
    """Kırılımlar, sıkışma, ikili tepe/dip, ortalama kesişimleri, boşluklar."""
    sonuc = []
    c = g["close"]
    son = len(df) - 1
    a = float(g["atr"].iloc[-1])
    hacim_kat = float(g["hacim"].iloc[-1] / g["hacim20"].iloc[-1]) if g["hacim20"].iloc[-1] else None

    def ekle(ad, yon, aciklama, guc=1.0):
        sonuc.append({"ad": ad, "yon": yon, "aciklama": aciklama, "guc": guc})

    # 55 günlük kanal kırılımı (Donchian / kaplumbağa kuralı)
    if pd.notna(g["donchian_ust"].iloc[-1]) and c.iloc[-1] > g["donchian_ust"].iloc[-1]:
        teyit = hacim_kat and hacim_kat >= 1.5
        ekle("55 günlük zirve kırıldı", 1,
             "Fiyat son 55 günün en yükseğinin üstünde kapattı" + (f"; hacim ortalamanın {_o(hacim_kat)} katı, kırılım hacimle teyitli."
                                                                    if teyit else "; hacim zayıf, teyit için hacim artışı beklenir."),
             1.0 if teyit else 0.6)
    if pd.notna(g["donchian_alt"].iloc[-1]) and c.iloc[-1] < g["donchian_alt"].iloc[-1]:
        ekle("55 günlük dip kırıldı", -1, "Fiyat son 55 günün en düşüğünün altında kapattı: düşüş trendi güç kazanıyor.")

    # Bollinger sıkışması: bant genişliği son 6 ayın en dar %10'unda
    genislik = g["bb_genislik"].iloc[-126:]
    if genislik.notna().sum() > 60 and genislik.iloc[-1] <= genislik.quantile(0.10):
        ekle("Bollinger sıkışması", 0, "Bantlar son 6 ayın en dar seviyesinde: oynaklık düştü, sert bir hareket yaklaşıyor olabilir. "
             "Yönü, bandın hangi tarafının kırıldığı belirler.")

    # Altın / ölüm kesişimi (son 20 gün)
    fark = np.sign(g["sma50"] - g["sma200"])
    degisim = fark.diff().iloc[-20:]
    if (degisim > 0).any():
        ekle("Altın kesişim", 1, "50 günlük ortalama son 20 günde 200 günlüğün üstüne çıktı: orta-uzun vadeli trend yukarı döndü.")
    if (degisim < 0).any():
        ekle("Ölüm kesişimi", -1, "50 günlük ortalama son 20 günde 200 günlüğün altına indi: orta-uzun vadeli trend aşağı döndü.")

    # İkili tepe / dip: son iki tepe (dip) birbirine 0,6 ATR yakın, aradaki geri çekilme ≥ 2 ATR
    tepeler = [n for n in noktalar if n[2] == "tepe"][-2:]
    dipler = [n for n in noktalar if n[2] == "dip"][-2:]
    if len(tepeler) == 2 and son - tepeler[1][0] <= 40 and abs(tepeler[1][1] - tepeler[0][1]) <= 0.6 * a:
        arada = df["Low"].iloc[tepeler[0][0]:tepeler[1][0] + 1].min()
        if tepeler[0][1] - arada >= 2 * a:
            kirildi = c.iloc[-1] < arada
            ekle("İkili tepe" + (" (teyitli)" if kirildi else " (oluşum aşamasında)"), -1,
                 f"Fiyat {_p(tepeler[0][1])} civarında iki kez durdu. Aradaki dip {_p(arada)}; "
                 + ("bu seviye kırıldı, formasyon tamamlandı." if kirildi else "bu seviye kırılırsa formasyon tamamlanır."),
                 1.0 if kirildi else 0.5)
    if len(dipler) == 2 and son - dipler[1][0] <= 40 and abs(dipler[1][1] - dipler[0][1]) <= 0.6 * a:
        arada = df["High"].iloc[dipler[0][0]:dipler[1][0] + 1].max()
        if arada - dipler[0][1] >= 2 * a:
            kirildi = c.iloc[-1] > arada
            ekle("İkili dip" + (" (teyitli)" if kirildi else " (oluşum aşamasında)"), 1,
                 f"Fiyat {_p(dipler[0][1])} civarında iki kez tutundu. Aradaki tepe {_p(arada)}; "
                 + ("bu seviye aşıldı, formasyon tamamlandı." if kirildi else "bu seviye aşılırsa formasyon tamamlanır."),
                 1.0 if kirildi else 0.5)

    # Boşluk (gap): son 5 günde 1 ATR'den büyük açılış boşluğu
    for i in range(max(1, len(df) - 5), len(df)):
        bosluk = df["Open"].iloc[i] - df["Close"].iloc[i - 1]
        if abs(bosluk) > a:
            dolu = (df["Low"].iloc[i:].min() <= df["Close"].iloc[i - 1]) if bosluk > 0 else (df["High"].iloc[i:].max() >= df["Close"].iloc[i - 1])
            ekle("Yukarı boşluk" if bosluk > 0 else "Aşağı boşluk", 1 if bosluk > 0 else -1,
                 f"{df.index[i]:%d.%m} günü fiyat {_p(abs(bosluk))} (%{_o(abs(bosluk) / df['Close'].iloc[i - 1] * 100)}) "
                 f"{'yukarı' if bosluk > 0 else 'aşağı'} boşlukla açıldı" + ("; boşluk kapandı." if dolu else "; boşluk henüz kapanmadı."),
                 0.5)
            break
    return sonuc


# ---------------------------------------------------------------------------
# 6. YAPI: tepe-dip dizisi, uyumsuzluk, Weinstein evresi, Fibonacci
# ---------------------------------------------------------------------------

def yapi(noktalar, son_uc):
    """Son tepe ve diplerin sırası: yükselen tepe-dip = yükseliş yapısı."""
    tepeler = [n for n in noktalar if n[2] == "tepe"][-2:]
    dipler = [n for n in noktalar if n[2] == "dip"][-2:]
    if len(tepeler) < 2 or len(dipler) < 2:
        return {"kod": "belirsiz", "metin": "Tepe-dip yapısı için yeterli salınım yok.", "yon": 0}
    yt = tepeler[1][1] > tepeler[0][1]
    yd = dipler[1][1] > dipler[0][1]
    if yt and yd:
        return {"kod": "yukselis", "yon": 1, "metin": "Yükselen tepeler ve yükselen dipler: klasik yükseliş yapısı (Dow teorisi)."}
    if not yt and not yd:
        return {"kod": "dusus", "yon": -1, "metin": "Alçalan tepeler ve alçalan dipler: düşüş yapısı sürüyor."}
    if yd and not yt:
        return {"kod": "daralan", "yon": 0, "metin": "Dipler yükseliyor ama tepeler alçalıyor: daralan üçgen, kırılım bekleniyor."}
    return {"kod": "genisleyen", "yon": 0, "metin": "Tepeler yükseliyor ama dipler alçalıyor: genişleyen, oynak ve yönsüz yapı."}


def uyumsuzluklar(g, noktalar, son_gun):
    """Fiyat ile RSI arasındaki uyumsuzluk (son iki tepe/dip, son 40 gün içinde)."""
    sonuc = []
    r = g["rsi"].to_numpy()
    m = g["macd_hist"].to_numpy()
    tepeler = [n for n in noktalar if n[2] == "tepe"][-2:]
    dipler = [n for n in noktalar if n[2] == "dip"][-2:]
    if len(tepeler) == 2 and son_gun - tepeler[1][0] <= 40:
        (i1, f1, _), (i2, f2, _) = tepeler
        if f2 > f1 and r[i2] < r[i1] - 2 and r[i1] > 55:
            ek = " MACD histogramı da daha zayıf." if m[i2] < m[i1] else ""
            sonuc.append({"ad": "Negatif uyumsuzluk", "yon": -1,
                          "aciklama": f"Fiyat daha yüksek tepe yaptı ({_p(f1)} → {_p(f2)}) ama RSI daha düşük ({r[i1]:.0f} → {r[i2]:.0f}): "
                                      f"yükselişin gücü azalıyor.{ek}"})
    if len(dipler) == 2 and son_gun - dipler[1][0] <= 40:
        (i1, f1, _), (i2, f2, _) = dipler
        if f2 < f1 and r[i2] > r[i1] + 2 and r[i1] < 45:
            ek = " MACD histogramı da daha güçlü." if m[i2] > m[i1] else ""
            sonuc.append({"ad": "Pozitif uyumsuzluk", "yon": 1,
                          "aciklama": f"Fiyat daha düşük dip yaptı ({_p(f1)} → {_p(f2)}) ama RSI daha yüksek ({r[i1]:.0f} → {r[i2]:.0f}): "
                                      f"satış baskısı zayıflıyor.{ek}"})
    return sonuc


def weinstein_evresi(df):
    """
    Stan Weinstein'ın evre analizi (haftalık 30 haftalık ortalama):
    1 taban, 2 yükseliş, 3 tepe, 4 düşüş. Uzun vadeli yatırımda yalnızca 2. evrede alım önerir.
    """
    haftalik = df["Close"].resample("W-FRI").last().dropna()
    if len(haftalik) < 40:
        return None
    ort = haftalik.rolling(30).mean()
    egim = ort.iloc[-1] / ort.iloc[-5] - 1
    ustunde = haftalik.iloc[-1] > ort.iloc[-1]
    yil_getiri = haftalik.iloc[-1] / haftalik.iloc[-min(52, len(haftalik) - 1)] - 1
    if egim > 0.01 and ustunde:
        evre, metin, yon = 2, "2. evre (yükseliş): fiyat yükselen 30 haftalık ortalamanın üstünde. Trend takipçileri için en verimli evre.", 1
    elif egim < -0.01 and not ustunde:
        evre, metin, yon = 4, "4. evre (düşüş): fiyat alçalan 30 haftalık ortalamanın altında. Uzun vadeli alım için erken.", -1
    elif yil_getiri > 0.15:
        evre, metin, yon = 3, "3. evre (tepe oluşumu): uzun yükselişten sonra 30 haftalık ortalama yataylaştı; dağıtım olabilir.", -0.5
    else:
        evre, metin, yon = 1, "1. evre (taban): düşüşten sonra 30 haftalık ortalama yataylaştı; birikim olabilir, kırılım beklenir.", 0
    return {"evre": evre, "metin": metin, "yon": yon, "egim": float(egim), "ort30": float(ort.iloc[-1])}


def fibonacci(df, pencere=126):
    """Son ~6 ayın en büyük salınımına göre Fibonacci düzeltme seviyeleri."""
    parca = df.iloc[-pencere:]
    if len(parca) < 30:
        return None
    i_ust, i_alt = parca["High"].to_numpy().argmax(), parca["Low"].to_numpy().argmin()
    ust, alt = float(parca["High"].iloc[i_ust]), float(parca["Low"].iloc[i_alt])
    if ust <= alt:
        return None
    yukari = i_alt < i_ust            # önce dip sonra tepe: yükseliş salınımı, düzeltme aşağı ölçülür
    oranlar = (0.236, 0.382, 0.5, 0.618, 0.786)
    seviyeler = [{"oran": o, "fiyat": round(ust - (ust - alt) * o if yukari else alt + (ust - alt) * o, 4)} for o in oranlar]
    fiyat = float(df["Close"].iloc[-1])
    duzeltme = (ust - fiyat) / (ust - alt) if yukari else (fiyat - alt) / (ust - alt)
    return {"yon": "yukari" if yukari else "asagi", "ust": ust, "alt": alt,
            "ust_tarih": parca.index[i_ust].date(), "alt_tarih": parca.index[i_alt].date(),
            "seviyeler": seviyeler, "duzeltme": float(duzeltme)}


# ---------------------------------------------------------------------------
# 7. ANA FONKSİYON
# ---------------------------------------------------------------------------

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
        "oynaklik", "endeks_oynaklik", "beta", "donchian_ust", "donchian_alt")}
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
        "noktalar": [{"tarih": df.index[i].strftime("%Y-%m-%d"), "fiyat": round(f, 4), "tur": t} for i, f, t in noktalar[-12:]],
        "isabet": {v: gecmis_isabet(g, b, v) for v in VADELER},
        "_g": g, "_b": b, "_df": df,
    }


# ---------------------------------------------------------------------------
# 8. GRAFİK OKUMASI (Türkçe yorum)
# ---------------------------------------------------------------------------

def _yuzde(x):
    return f"%{_o(abs(x) * 100)}".replace(".", ",")


def okuma(t, bolgeler=None):
    """
    Teknik analiz sonucunu, deneyimli bir grafik okuyucunun yazacağı gibi başlıklar altında
    Türkçe cümlelere çevirir. Her madde: {'baslik', 'yon' (+1/0/−1), 'metin'}.
    """
    gs = t["gosterge"]
    c = gs["close"]
    m = []

    def ekle(baslik, yon, metin):
        m.append({"baslik": baslik, "yon": yon, "metin": metin})

    # Ana trend
    if gs["sma200"]:
        ust200 = c > gs["sma200"]
        ust50 = gs["sma50"] and c > gs["sma50"]
        dizilim = gs["sma50"] and gs["sma20"] and gs["sma20"] > gs["sma50"] > gs["sma200"]
        ters = gs["sma50"] and gs["sma20"] and gs["sma20"] < gs["sma50"] < gs["sma200"]
        uzaklik = c / gs["sma200"] - 1
        if dizilim and ust200:
            metin = (f"Fiyat 20, 50 ve 200 günlük ortalamaların üstünde ve ortalamalar yükseliş sırasında dizili (20 > 50 > 200). "
                     f"200 günlüğe uzaklık {_yuzde(uzaklik)}.")
            ekle("Ana trend: yükseliş", 1, metin)
        elif ters and not ust200:
            ekle("Ana trend: düşüş", -1, f"Fiyat bütün ana ortalamaların altında ve ortalamalar düşüş sırasında (20 < 50 < 200). "
                 f"200 günlüğün {_yuzde(uzaklik)} altında.")
        elif ust200:
            ekle("Ana trend: yükseliş, kısa vadede dinlenme" if not ust50 else "Ana trend: yükseliş", 1 if ust50 else 0,
                 f"Fiyat 200 günlük ortalamanın {_yuzde(uzaklik)} üstünde" + ("" if ust50 else ", ama 50 günlüğün altına sarktı: ana trend bozulmadan düzeltme.") + ".")
        else:
            ekle("Ana trend: zayıf", -1 if not ust50 else 0, f"Fiyat 200 günlük ortalamanın {_yuzde(uzaklik)} altında"
                 + (", kısa vadede 50 günlüğün üstüne çıkarak toparlanma deniyor." if ust50 else "."))
    if t["evre"]:
        ekle("Haftalık grafik (Weinstein evresi)", 1 if t["evre"]["yon"] > 0 else (-1 if t["evre"]["yon"] < 0 else 0), t["evre"]["metin"])
    ekle("Tepe-dip yapısı", t["yapi"]["yon"], t["yapi"]["metin"])

    # Trend gücü
    if gs["adx"] is not None:
        yon_di = "alıcılar (+DI)" if (gs["arti_di"] or 0) > (gs["eksi_di"] or 0) else "satıcılar (−DI)"
        if gs["adx"] >= 25:
            ekle("Trend gücü", 1 if yon_di.startswith("alıcı") else -1,
                 f"ADX {gs['adx']:.0f}: güçlü bir trend var ve yönünü {yon_di} belirliyor. Güçlü trendde osilatörlerin aşırı alım/satım "
                 "uyarıları sık yanıltır; trend yönünde işlem daha güvenlidir.")
        elif gs["adx"] < 18:
            ekle("Trend gücü", 0, f"ADX {gs['adx']:.0f}: belirgin bir trend yok, fiyat yatay. Bu ortamda destekten alıp dirençte satmak, "
                 "kırılım kovalamaktan daha iyi çalışır.")
        else:
            ekle("Trend gücü", 0, f"ADX {gs['adx']:.0f}: trend orta güçte, {yon_di} hafif üstün.")

    # Momentum
    r = gs["rsi"]
    if r is not None:
        if r >= 70:
            metin, yon = f"RSI {r:.0f}: aşırı alım bölgesi. Güçlü trendlerde uzun süre burada kalabilir; tek başına satış sebebi değil ama yeni alım için risk/getiri zayıflar.", 0
        elif r <= 30:
            metin, yon = f"RSI {r:.0f}: aşırı satım bölgesi. Tepki yükselişi ihtimali arttı; düşüş trendinde ise teyit (yükselen dip, hacim) beklenmeli.", 0
        elif r >= 50:
            metin, yon = f"RSI {r:.0f}: momentum alıcılar lehine (50'nin üstü).", 1
        else:
            metin, yon = f"RSI {r:.0f}: momentum satıcılar lehine (50'nin altı).", -1
        if gs["macd_hist"] is not None:
            if gs["macd"] > gs["macd_sinyal"]:
                metin += " MACD sinyal çizgisinin üstünde" + (" ve sıfırın üstünde: yükseliş momentumu teyitli." if gs["macd"] > 0 else ", ancak sıfırın altında: düşüş içinde toparlanma.")
            else:
                metin += " MACD sinyal çizgisinin altında" + (" ve sıfırın altında: düşüş momentumu sürüyor." if gs["macd"] < 0 else ", sıfırın üstünde: yükseliş ivme kaybediyor.")
        ekle("Momentum", yon, metin)

    # Göreli güç
    if gs.get("endeks_getiri"):
        g3, e3 = gs["getiriler"]["3a"], gs["endeks_getiri"]["3a"]
        g6, e6 = gs["getiriler"]["6a"], gs["endeks_getiri"]["6a"]
        if g3 is not None and e3 is not None:
            fark = g3 - e3
            metin = f"Son 3 ayda hisse {'+' if g3 >= 0 else '−'}{_yuzde(g3)}, endeks {'+' if e3 >= 0 else '−'}{_yuzde(e3)}"
            if g6 is not None and e6 is not None:
                metin += f"; 6 ayda hisse {'+' if g6 >= 0 else '−'}{_yuzde(g6)}, endeks {'+' if e6 >= 0 else '−'}{_yuzde(e6)}"
            metin += ". " + ("Hisse endeksten güçlü: piyasa liderleri arasında." if fark > 0.03 else
                             "Hisse endeksin gerisinde: para başka hisselere akıyor." if fark < -0.03 else "Endeksle benzer seyir.")
            ekle("Endekse göre güç", 1 if fark > 0.03 else (-1 if fark < -0.03 else 0), metin)

    # Hacim
    if gs["cmf"] is not None and gs["hacim20"]:
        oran = gs["hacim"] / gs["hacim20"] if gs["hacim20"] else None
        metin = f"Chaikin para akışı {'+' if gs['cmf'] >= 0 else '−'}{ondalik(abs(gs['cmf']), 2)}: " + ("alıcılar kapanışları günün üst bölümüne taşıyor, para girişi var." if gs["cmf"] > 0.05
                                                       else "kapanışlar günün alt bölümünde, para çıkışı var." if gs["cmf"] < -0.05 else "belirgin bir para akışı yok.")
        if oran:
            metin += f" Son günün hacmi 20 günlük ortalamanın {_o(oran)} katı."
        ekle("Hacim ve para akışı", 1 if gs["cmf"] > 0.05 else (-1 if gs["cmf"] < -0.05 else 0), metin)

    # Oynaklık
    if gs["bb_b"] is not None:
        b_ = gs["bb_b"]
        if b_ > 1:
            metin = "Fiyat üst Bollinger bandının dışında kapattı: güçlü itiş ama kısa vadede gerilmiş."
        elif b_ < 0:
            metin = "Fiyat alt Bollinger bandının dışında kapattı: sert satış, kısa vadeli tepki yükselişi sık görülür."
        else:
            metin = f"Fiyat Bollinger bantlarının içinde (%b = {ondalik(b_, 2)})."
        metin += f" Günlük ortalama hareket (ATR) {_p(gs['atr'])}, yani fiyatın {ek('%' + _o(gs['atr'] / c * 100), 'si')}"
        if gs["oynaklik"]:
            metin += f"; yıllık oynaklık %{gs['oynaklik'] * 100:.0f}"
            if gs.get("endeks_oynaklik"):
                metin += f" (endeks %{gs['endeks_oynaklik'] * 100:.0f})"
        ekle("Oynaklık", 0, metin + ".")

    # Ichimoku
    if gs["span_a"] and gs["span_b"]:
        bulut_ust, bulut_alt = max(gs["span_a"], gs["span_b"]), min(gs["span_a"], gs["span_b"])
        if c > bulut_ust:
            metin, yon = "Fiyat Ichimoku bulutunun üstünde", 1
        elif c < bulut_alt:
            metin, yon = "Fiyat Ichimoku bulutunun altında", -1
        else:
            metin, yon = "Fiyat Ichimoku bulutunun içinde (kararsız bölge)", 0
        if gs["tenkan"] and gs["kijun"]:
            metin += "; dönüş çizgisi (tenkan) temel çizginin (kijun) " + ("üstünde." if gs["tenkan"] > gs["kijun"] else "altında.")
        ekle("Ichimoku", yon, metin)

    # Fibonacci
    fib = t["fibonacci"]
    if fib:
        d = fib["duzeltme"]
        if fib["yon"] == "yukari":
            metin = (f"Son 6 ayın yükseliş salınımı {_p(fib['alt'])} → {_p(fib['ust'])}. Fiyat bu yükselişin %{round(d * 100)} kadarını geri verdi. ")
            if d < 0.236:
                metin += "Zirveye yakın, düzeltme sığ: güçlü trend işareti."
            elif d <= 0.618:
                metin += "Sağlıklı düzeltme bölgesi (%38,2–61,8): trend devamı için klasik alım alanı."
            else:
                metin += "%61,8'in ötesine geçen derin düzeltme: yükseliş trendinin geçerliliği sorgulanıyor."
        else:
            metin = (f"Son 6 ayın düşüş salınımı {_p(fib['ust'])} → {_p(fib['alt'])}. Fiyat düşüşün %{round(d * 100)} kadarını geri aldı. ")
            metin += ("Tepki zayıf." if d < 0.382 else "Tepki %38,2–61,8 direnç bölgesinde: düşüş trendinde satış baskısı burada artar." if d <= 0.618
                      else "Düşüşün çoğu geri alındı: dönüş ihtimali güçleniyor.")
        ekle("Fibonacci", 0, metin)

    # Destek / direnç
    if bolgeler:
        destek = [b for b in bolgeler if b["tur"] == "destek"]
        direnc = [b for b in bolgeler if b["tur"] == "direnç"]
        parca = []
        if destek:
            d = max(destek, key=lambda b: b["merkez"])
            parca.append(f"En yakın destek {_p(d['alt'])}–{_p(d['ust'])} (%{_o(abs(d['uzaklik_yuzde']))} aşağıda, güç {d['puan']:.0f}/100, "
                         f"{d['test']} testte {d['tutunan']} kez tutundu)")
        if direnc:
            r_ = min(direnc, key=lambda b: b["merkez"])
            parca.append(f"en yakın direnç {_p(r_['alt'])}–{_p(r_['ust'])} (%{_o(abs(r_['uzaklik_yuzde']))} yukarıda, güç {r_['puan']:.0f}/100)")
        if parca:
            metin = "; ".join(parca)
            ekle("Destek ve direnç", 0, metin[0].upper() + metin[1:] + ".")

    return m


def senaryolar(t, bolgeler):
    """Boğa ve ayı senaryosu: hangi seviyede ne olur."""
    gs = t["gosterge"]
    c, a = gs["close"], gs["atr"]
    destek = sorted([b for b in bolgeler or [] if b["tur"] == "destek"], key=lambda b: -b["merkez"])
    direnc = sorted([b for b in bolgeler or [] if b["tur"] == "direnç"], key=lambda b: b["merkez"])
    yukari_esik = direnc[0]["ust"] if direnc else c + 2 * a
    asagi_esik = destek[0]["alt"] if destek else c - 2 * a
    hedef_yukari = direnc[1]["merkez"] if len(direnc) > 1 else yukari_esik + 2 * a
    hedef_asagi = destek[1]["merkez"] if len(destek) > 1 else asagi_esik - 2 * a
    return {
        "boga": f"{_p(yukari_esik)} üstünde hacimli günlük kapanış, yükselişin devamını teyit eder; ilk hedef {_p(hedef_yukari)}.",
        "ayi": f"{_p(asagi_esik)} altında kapanış yapıyı bozar; bir sonraki durak {_p(hedef_asagi)}.",
        "yukari_esik": yukari_esik, "asagi_esik": asagi_esik,
    }
