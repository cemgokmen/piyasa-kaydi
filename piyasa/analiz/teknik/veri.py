"""Fiyat verisinin analizden önce temizlenmesi."""

import numpy as np
import pandas as pd

# Baz fiyat ağırlıklı ortalamadayken sınır kapanıştan kapanışa ±%10 değildi: en çok 1,10 / 0,90 ≈ +%22, 0,90 / 1,10 ≈ −%18.
# Veride +%10,5 üstü günler 2021 Ocak'ta biter; geçiş ayı eski kurala bırakıldı.
KAPANIS_BAZI = pd.Timestamp("2021-02-01")
ESKI_DUSUS = -0.22
YENI_SINIR = 0.105      # kapanış bazında bir seansta en çok %10, küsur payıyla
SICRAMA_YUKARI = 0.25   # temettü düzeltmesi bir sınır günü %10'dan yukarı taşıyabilir; bedelsiz fiyatı zaten düşürür


def _sicramalar(index, oran):
    """Gerçek işlemle açıklanamayacak kapanış değişimleri. Yahoo'nun atladığı seanslar sınırı genişletir."""
    gunler = pd.DatetimeIndex(index).tz_localize(None).normalize().to_numpy(dtype="datetime64[D]")
    seans = np.ones(len(gunler))
    seans[1:] = np.maximum(np.busday_count(gunler[:-1], gunler[1:]), 1)
    yeni = gunler >= np.datetime64(KAPANIS_BAZI, "D")
    alt = np.where(yeni, 1 - YENI_SINIR, 1 + ESKI_DUSUS) ** seans
    ust = np.where(yeni, np.maximum(1 + SICRAMA_YUKARI, (1 + YENI_SINIR) ** seans), (1 + SICRAMA_YUKARI) ** seans)
    return (oran < alt) | (oran > ust)


def bolunme_duzelt(df):
    """
    Yahoo, BIST'teki bazı bedelsiz sermaye artırımlarını işlemez: CCOLA 2024-08-01'de 815'ten 75'e "düşmüş" görünür.
    Fiyat sınırının açıklayamadığı sıçramada önceki fiyatlar sıçrama kadar ölçeklenir, son fiyat değişmez; hacim ters
    yönde düzeltilir (TSPAKB 2011, s. 56–57). Yalnızca BIST verisine uygulanır.

    Sınır dönemlere göre değişir: VESTL 2026-11-04'te +%21'dir ama Yahoo bir önceki seansı atlamıştır (iki tavan), 2011–2020
    arasındaki +%22'ye varan günler de gerçektir. Bunlara dokunulmaz.
    """
    kapanis = df["Close"]
    oran = (kapanis / kapanis.shift(1)).to_numpy()
    sicrama = pd.Series(_sicramalar(df.index, oran), index=df.index)
    if not sicrama.any():
        return df
    # Her gün için, kendisinden sonraki sıçramaların çarpımı
    carpan = pd.Series(oran, index=df.index).where(sicrama, 1.0)
    katsayi = carpan[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
    sonuc = df.copy()
    for sutun in ("Open", "High", "Low", "Close"):
        sonuc[sutun] = df[sutun] * katsayi
    sonuc["Volume"] = df["Volume"] / katsayi
    return sonuc


def bist_mi(yahoo):
    return isinstance(yahoo, str) and yahoo.upper().endswith(".IS")


__all__ = ["bist_mi", "bolunme_duzelt"]
