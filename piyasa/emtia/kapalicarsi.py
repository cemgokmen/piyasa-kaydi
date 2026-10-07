"""
Kapalıçarşı (serbest piyasa) altın ve gümüş fiyatları: alış, satış ve günlük
değişim. Kaynak: Truncgil Finans'ın ücretsiz, anahtarsız veri servisi.

Sonuçlar 2 dakika bellekte tutulur; servise ulaşılamazsa son başarılı sonuç döner.
"""

import requests

from piyasa.onbellek import sureli

ADRES = "https://finans.truncgil.com/v4/today.json"
ONBELLEK_SURESI = 2 * 60

# (kaynaktaki kod, sitede gösterilen ad, birim)
ALTINLAR = [
    ("GRA", "Gram altın", "gram"),
    ("HAS", "Has altın", "gram"),
    ("CEYREKALTIN", "Çeyrek altın", "adet"),
    ("YARIMALTIN", "Yarım altın", "adet"),
    ("TAMALTIN", "Tam altın", "adet"),
    ("CUMHURIYETALTINI", "Cumhuriyet altını", "adet"),
    ("ATAALTIN", "Ata altın", "adet"),
    ("YIA", "22 ayar bilezik", "gram"),
    ("18AYARALTIN", "18 ayar altın", "gram"),
    ("14AYARALTIN", "14 ayar altın", "gram"),
]
GUMUSLER = [("GUMUS", "Gram gümüş", "gram")]


def _sayi(deger):
    try:
        return float(deger) or None
    except (TypeError, ValueError):
        return None


@sureli(ONBELLEK_SURESI, hatada_eskisi=True)
def _veri():
    cevap = requests.get(ADRES, timeout=15, headers={"User-Agent": "Mozilla/5.0 PiyasaKaydi"})
    cevap.raise_for_status()
    return cevap.json()


def fiyatlar(tur="altin"):
    """{'guncelleme': '2026-10-07 14:36', 'satirlar': [{ad, birim, alis, satis, degisim}]}; yoksa None."""
    try:
        veri = _veri()
    except Exception:
        return None
    satirlar = []
    for kod, ad, birim in (ALTINLAR if tur == "altin" else GUMUSLER):
        k = veri.get(kod) or {}
        alis, satis = _sayi(k.get("Buying")), _sayi(k.get("Selling"))
        if not (alis or satis):
            continue
        degisim = _sayi(k.get("Change"))
        satirlar.append({"ad": ad, "birim": birim, "alis": alis, "satis": satis,
                         "degisim": degisim / 100 if degisim is not None else None})
    if not satirlar:
        return None
    return {"guncelleme": (veri.get("Update_Date") or "")[:16], "satirlar": satirlar}
