"""
Altay'ın (1997) İMKB deneyinin bugünkü tekrarı: yalnızca stokastik sinyalleriyle yönetilen, eşit ağırlıklı,
açığa satışsız portföy; boştaki nakit gecelik faizde.

Tezin kendi uyarısı "tek dönem, tek yöntem" olduğu için deney son bir yılla sınırlı kalmaz, ardışık yıllarda
tekrarlanır. Karşılaştırmalar: BIST 100, aynı hisseleri al-tut (sağkalım yanlılığını dengeler, çünkü evren bugünkü
BIST 100'dür) ve hiç hisse almadan faizde beklemek. Endeks temettüsüz, hisseler temettü düzeltmelidir.
"""

import numpy as np
import pandas as pd

from piyasa.analiz.teknik.gostergeler import stokastik

KOMISYON_TEZ = 0.007        # tezdeki binde 7
KOMISYON_BUGUN = 0.002      # bugünkü tipik aracı kurum komisyonu, vergi ve fark dahil varsayım
YIL_GUN = 252

# TCMB politika faizi (değişiklik tarihi, yıllık %). Gecelik getirinin yaklaşık vekilidir.
POLITIKA_FAIZI = (
    ("2020-01-01", 15.0), ("2020-12-24", 17.0), ("2021-03-18", 19.0), ("2021-09-23", 18.0), ("2021-10-21", 16.0),
    ("2021-11-18", 15.0), ("2021-12-16", 14.0), ("2022-08-18", 13.0), ("2022-09-22", 12.0), ("2022-10-20", 10.5),
    ("2022-11-24", 9.0), ("2023-02-23", 8.5), ("2023-06-22", 15.0), ("2023-07-20", 17.5), ("2023-08-24", 25.0),
    ("2023-09-21", 30.0), ("2023-10-26", 35.0), ("2023-11-23", 40.0), ("2023-12-21", 42.5), ("2024-01-25", 45.0),
    ("2024-03-21", 50.0), ("2024-12-26", 47.5), ("2025-01-23", 45.0), ("2025-03-06", 42.5), ("2025-04-17", 46.0),
    ("2025-07-24", 43.0), ("2025-09-11", 40.5), ("2025-10-23", 39.5), ("2025-12-11", 38.0), ("2026-01-22", 37.0),
    ("2026-10-22", 36.0),
)


def gunluk_faiz(tarihler):
    s = pd.Series({pd.Timestamp(t): v / 100 for t, v in POLITIKA_FAIZI}).sort_index()
    yillik = s.reindex(s.index.union(tarihler)).ffill().reindex(tarihler)
    return (1 + yillik) ** (1 / 365) - 1


def _sinyaller(fiyatlar):
    """Stokastik 20/80: sinyal kapanışta oluşur, işlem ertesi günün açılışındadır."""
    sonuc = {}
    for kod, df in fiyatlar.items():
        k, _ = stokastik(df, yavaslatma=3)
        al = (k > 20) & (k.shift(1) <= 20)
        sat = (k < 80) & (k.shift(1) >= 80)
        sonuc[kod] = pd.Series(np.where(al, 1, np.where(sat, -1, 0)), index=df.index)
    return sonuc


def portfoy(fiyatlar, bas, bit, komisyon=KOMISYON_TEZ, faizli=True):
    """
    Her hisseye eşit başlangıç payı. Pay, AL'da tamamıyla hisseye, SAT'ta tamamıyla nakde geçer; paylar arasında
    para aktarılmaz. Dönüş: toplam getiri, işlem sayısı, ortalama hissede kalma oranı.
    """
    sinyal = _sinyaller(fiyatlar)
    takvim = pd.DatetimeIndex(sorted({t for d in fiyatlar.values() for t in d.loc[bas:bit].index}))
    if len(takvim) < 20:
        return None
    faiz = gunluk_faiz(takvim) if faizli else pd.Series(0.0, index=takvim)
    bitis_degerleri, islem, hissede = [], 0, []
    kodlar = [k for k, d in fiyatlar.items() if len(d.loc[:bas]) > 0 and len(d.loc[bas:bit]) >= 20]
    for kod in kodlar:
        d = fiyatlar[kod]
        s = sinyal[kod]
        nakit, adet, onceki_sinyal, gun_hisse, gun = 1.0, 0.0, 0, 0, 0
        onceki_i = d.index.get_indexer([takvim[0]], method="ffill")[0] - 1
        onceki_sinyal = int(s.iloc[onceki_i]) if onceki_i >= 0 else 0
        for t in takvim:
            nakit *= 1 + faiz.loc[t]
            gun += 1
            if t not in d.index:
                gun_hisse += adet > 0
                continue
            satir = d.loc[t]
            acilis = satir["Open"] if satir["Open"] > 0 else satir["Close"]
            if onceki_sinyal == 1 and adet == 0:
                adet, nakit = nakit * (1 - komisyon) / acilis, 0.0
                islem += 1
            elif onceki_sinyal == -1 and adet > 0:
                nakit, adet = adet * acilis * (1 - komisyon), 0.0
                islem += 1
            gun_hisse += adet > 0
            onceki_sinyal = int(s.loc[t])
        son = d.loc[:takvim[-1]]["Close"].iloc[-1]
        bitis_degerleri.append(nakit + adet * son)
        hissede.append(gun_hisse / gun)
    if not bitis_degerleri:
        return None
    return {"getiri": float(np.mean(bitis_degerleri) - 1), "islem": islem, "hisse": len(kodlar),
            "hissede_kalma": float(np.mean(hissede))}


def al_tut(fiyatlar, bas, bit, komisyon=KOMISYON_TEZ):
    getiriler = []
    for d in fiyatlar.values():
        p = d.loc[bas:bit]
        if len(d.loc[:bas]) and len(p) >= 20:
            getiriler.append((p["Close"].iloc[-1] / p["Open"].iloc[0]) * (1 - komisyon) ** 2 - 1)
    return float(np.mean(getiriler)) if getiriler else None


def faiz_getirisi(takvim):
    return float((1 + gunluk_faiz(takvim)).prod() - 1)


def donem(fiyatlar, endeks, bas, bit):
    e = endeks.loc[bas:bit]
    if len(e) < 20:
        return None
    return {
        "bas": e.index[0].strftime("%Y-%m-%d"), "bit": e.index[-1].strftime("%Y-%m-%d"),
        "tez": portfoy(fiyatlar, bas, bit, KOMISYON_TEZ),
        "bugun": portfoy(fiyatlar, bas, bit, KOMISYON_BUGUN),
        "endeks": float(e.iloc[-1] / e.iloc[0] - 1),
        "al_tut": al_tut(fiyatlar, bas, bit, KOMISYON_BUGUN),
        "faiz": faiz_getirisi(pd.DatetimeIndex(pd.date_range(e.index[0], e.index[-1]))),
    }


def tekrarla(fiyatlar, endeks, yil=5):
    """Sondan geriye ardışık bir yıllık dönemler; ilki tezin son 1 yıllık tekrarıdır."""
    son = endeks.index[-1]
    sonuc = []
    for i in range(yil):
        bit = son - pd.DateOffset(years=i)
        bas = bit - pd.DateOffset(years=1) + pd.Timedelta(days=1)
        d = donem(fiyatlar, endeks, bas, bit)
        if d and d["tez"]:
            sonuc.append(d)
    return sonuc
