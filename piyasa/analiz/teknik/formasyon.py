"""Mum ve grafik formasyonları."""

import numpy as np
import pandas as pd

from piyasa.bicim import fiyat as _p
from piyasa.bicim import ondalik


def _o(x, n=1):
    return ondalik(x, n)


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
