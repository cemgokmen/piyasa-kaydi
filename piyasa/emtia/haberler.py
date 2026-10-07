"""
Emtia haberleri: Google Haberler'in Türkçe RSS akışından son iki haftanın
başlıkları. Başlıklar konuya göre (merkez bankası, OPEC, arz, talep...)
etiketlenir; "bugün gram altın ne kadar?" türü günlük fiyat listeleri elenir.

Sonuçlar 30 dakika bellekte tutulur.
"""

import re

from piyasa import haber
from piyasa.emtia.tanimlar import HABER_ETIKETLERI
from piyasa.onbellek import sureli

ONBELLEK_SURESI = 30 * 60

# Hükümet ve merkez bankası kararları için ortak arama
KARAR_SORGUSU = (
    '(OPEC OR "Fed faiz" OR "Merkez Bankası faiz" OR yaptırım OR "gümrük vergisi" OR ambargo) '
    '(petrol OR altın OR gümüş OR emtia)'
)

# Bilgi taşımayan, her gün tekrarlanan fiyat listesi başlıkları
FIYAT_LISTESI = re.compile(
    r"ne kadar|kaç tl|canlı|anlık|güncel (rakam|fiyat)|fiyatları bugün|güne nasıl|"
    r"alış.?satış|'?(da|de|ta|te) altın fiyatları|tarafından haberler|"
    r"\b\d{1,2} (ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)\b",
    re.IGNORECASE,
)


def etiketle(baslik):
    kucuk = baslik.lower()
    return [ad for ad, kelimeler in HABER_ETIKETLERI if any(k in kucuk for k in kelimeler)]


def _indir(sorgu):
    return [dict(h, etiketler=etiketle(h["baslik"])) for h in haber.indir(sorgu, "tr", 14)]


def _sec(haberler, adet):
    """Yeniden eskiye sıralar, aynı başlıkları ve günlük fiyat listelerini eler."""
    return haber.sec(haberler, adet, ele=lambda h: FIYAT_LISTESI.search(h["baslik"]))


@sureli(ONBELLEK_SURESI, hatada_eskisi=True)
def _secilmis(sorgu):
    return _sec(_indir(sorgu), 40)


def haberler(sorgu, adet=12):
    """Sorgunun son iki haftadaki haberleri; ağ hatasında son başarılı sonuç ya da boş liste."""
    try:
        return _secilmis(sorgu)[:adet]
    except Exception:
        return []


def karar_haberleri(adet=10):
    """OPEC, merkez bankaları, yaptırım ve gümrük kararlarıyla ilgili haberler."""
    return haberler(KARAR_SORGUSU, adet)
