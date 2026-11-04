"""Fiyat verisinin analizden önce temizlenmesi."""

BIST_SICRAMA = 0.15


def bolunme_duzelt(df, esik=BIST_SICRAMA):
    """
    Yahoo, BIST'teki bazı bedelsiz sermaye artırımlarını işlemez: CCOLA 2024-08-01'de 815'ten 75'e "düşmüş" görünür.
    Borsada günlük fiyat sınırı %10 olduğu için kapanıştan kapanışa daha büyük sıçrama gerçek hareket sayılmaz:
    önceki fiyatlar sıçrama kadar ölçeklenir, son fiyat değişmez. Yalnızca BIST verisine uygulanır.
    """
    kapanis = df["Close"]
    oran = kapanis / kapanis.shift(1)
    sicrama = (oran - 1).abs() > esik
    if not sicrama.any():
        return df
    # Her gün için, kendisinden sonraki sıçramaların çarpımı
    katsayi = oran.where(sicrama, 1.0)[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
    sonuc = df.copy()
    for sutun in ("Open", "High", "Low", "Close"):
        sonuc[sutun] = df[sutun] * katsayi
    sonuc["Volume"] = df["Volume"] / katsayi
    return sonuc


def bist_mi(yahoo):
    return isinstance(yahoo, str) and yahoo.upper().endswith(".IS")


__all__ = ["BIST_SICRAMA", "bist_mi", "bolunme_duzelt"]
