"""
Borsa İstanbul'da günün hareketi: en çok yükselen ve düşen hisseler, yükselen/düşen sayısı.

Borsa İstanbul'da günlük hareket ±%10 ile sınırlı: bunu aşan değişim, bölünme ya da bedelsiz
sermaye artırımının düzeltilmediği veri hatasıdır ve gösterilmez. Son işlem günü fiyatı
gelmeyen (eski kalan) hisseler de sayılmaz.
"""

from collections import Counter

from piyasa.bist import sorgular

GUNLUK_SINIR = 0.105        # fiyat marjı ±%10 (yuvarlama payıyla)
EN_DUSUK_FIYAT = 1          # 1 TL altındaki kuruşluk hisseler sıralamaya girmez


def tum_kodlar():
    """Fiyatı tazelenecek bütün hisseler: BIST 100 önce (ilk parçada gelsin)."""
    return [x["kod"] for x in sorted(sorgular.sirketler(), key=lambda x: (not x["xu100"], x["kod"]))]


def gecerli(f):
    """Günlük değişimi borsanın ±%10 sınırını aşan fiyatın günlük değişimi gösterilmez."""
    if f and f.get("g1") is not None and abs(f["g1"]) > GUNLUK_SINIR:
        return {**f, "g1": None}
    return f


def fiyat_ekle(sirketler, fiyatlar):
    for s in sirketler:
        s["f"] = gecerli(fiyatlar.get(s["kod"]))
    return sirketler


def gunun_hareketi(fiyatlar, adet=6):
    tum = fiyat_ekle(sorgular.sirketler(), fiyatlar)
    fiyatli = [s for s in tum if s["f"] and s["f"]["g1"] is not None]
    son_gun = Counter(s["f"]["tarih"] for s in fiyatli).most_common(1)[0][0] if fiyatli else None
    fiyatli = [s for s in fiyatli if s["f"]["tarih"] == son_gun]
    hareketli = sorted((s for s in fiyatli if s["f"]["fiyat"] >= EN_DUSUK_FIYAT), key=lambda s: s["f"]["g1"])
    return {
        "toplam": len(tum),
        "yukselenler": hareketli[::-1][:adet],
        "dusenler": hareketli[:adet],
        "artan": sum(1 for s in fiyatli if s["f"]["g1"] > 0),
        "azalan": sum(1 for s in fiyatli if s["f"]["g1"] < 0),
        "hareket_gunu": son_gun,
    }
