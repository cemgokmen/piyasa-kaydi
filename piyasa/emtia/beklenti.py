"""
Piyasanın beklentisi (vadeli işlem fiyatlarından, Yahoo Finance):

  vadeli_fiyat(emtia)   bir yıl sonrası için vadeli piyasada bugün anlaşılan fiyat
  faiz_beklentisi()     Fed faiz vadelilerinden çıkan beklenen politika faizi

Bunlar tahmin değildir: bugün, ileri bir tarih için yapılan anlaşmaların fiyatıdır.
Analist hedefleri ücretsiz ve düzenli bir kaynakta bulunmadığı için piyasanın
kendi fiyatladığı beklenti gösterilir. Sonuçlar 30 dakika bellekte tutulur.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from piyasa import fiyat
from piyasa.bicim import AYLAR_UZUN
from piyasa.onbellek import sureli

AY_HARFLERI = "FGHJKMNQUVXZ"      # vadeli işlem ay kodları: F=Ocak ... Z=Aralık

# emtia → (Yahoo kök kodu, borsa eki, işlem gören aylar)
VADELI = {
    "altin": ("GC", "CMX", (6, 12)),
    "gumus": ("SI", "CMX", (3, 5, 7, 9, 12)),
    "platin": ("PL", "NYM", (1, 4, 7, 10)),
    "bakir": ("HG", "CMX", (3, 5, 7, 9, 12)),
    "brent": ("BZ", "NYM", tuple(range(1, 13))),
}


def vade_kodu(kok, borsa, aylar, bugun=None, ay_sonra=12):
    """Bugünden en az 'ay_sonra' ay sonraki ilk işlem gören vade: ('GCZ27.CMX', 2027, 12)."""
    bugun = bugun or date.today()
    hedef = bugun.year * 12 + bugun.month - 1 + ay_sonra
    for ek in range(0, 24):
        yil, ay = divmod(hedef + ek, 12)
        ay += 1
        if ay in aylar:
            return f"{kok}{AY_HARFLERI[ay - 1]}{yil % 100:02d}.{borsa}", yil, ay
    return None


@sureli(30 * 60)
def vadeli_fiyat(slug, spot_kodu):
    if slug not in VADELI:
        return None
    kod, yil, ay = vade_kodu(*VADELI[slug])
    vadeli = fiyat.anlik_fiyat(kod, ham=True)
    spot = fiyat.anlik_fiyat(spot_kodu, ham=True)
    if not vadeli or not spot or not vadeli["fiyat"] or not spot["fiyat"]:
        return None
    return {"vade": f"{AYLAR_UZUN[ay - 1]} {yil}", "fiyat": vadeli["fiyat"], "spot": spot["fiyat"],
            "fark": vadeli["fiyat"] / spot["fiyat"] - 1}


@sureli(30 * 60)
def faiz_beklentisi(guncel_ust):
    """
    guncel_ust: Fed politika faizi bandının üst sınırı (ör. 4,00). Vadeli fiyattan çıkan
    oran (100 − fiyat) o ayın ortalama gecelik faizini gösterir; bandın ortasıyla karşılaştırılır.
    """
    if not guncel_ust:
        return None
    orta = guncel_ust - 0.125
    bugun = date.today()
    vadeler = []
    for ay_sonra in (3, 6, 9, 12):
        yil, ay = divmod(bugun.year * 12 + bugun.month - 1 + ay_sonra, 12)
        vadeler.append((f"ZQ{AY_HARFLERI[ay]}{yil % 100:02d}.CBT", yil, ay))
    with ThreadPoolExecutor(len(vadeler)) as havuz:
        fiyatlar = list(havuz.map(lambda v: fiyat.anlik_fiyat(v[0], ham=True), vadeler))
    noktalar = []
    for (_kod, yil, ay), b in zip(vadeler, fiyatlar, strict=True):
        if not b or not b["fiyat"]:
            continue
        oran = 100 - b["fiyat"]
        degisim = oran - orta
        noktalar.append({"vade": f"{AYLAR_UZUN[ay]} {yil}", "oran": oran, "degisim": degisim,
                         "adim": round(degisim / 0.25, 1)})
    if not noktalar:
        return None
    son = noktalar[-1]
    yon = "artış" if son["adim"] >= 0.5 else "indirim" if son["adim"] <= -0.5 else "sabit"
    return {"guncel": orta, "guncel_ust": guncel_ust, "noktalar": noktalar, "yon": yon,
            "adim_sayisi": abs(round(son["adim"])), "son": son}
