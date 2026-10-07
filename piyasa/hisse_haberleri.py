"""
Hisse sayfasının en altındaki "Güncel haberler": şirketle ilgili son 30 günün
haberleri (Google Haberler).

Önce Türkçe haberler alınır. Az ise İngilizce haberlerle tamamlanır; İngilizce
başlıklar Türkçeye çevrilir, sayfada haberin İngilizce olduğu belirtilir.
Yalnızca başlığında şirketin adı ya da borsa kodu geçen haberler alınır.
Elenenler: şirket ya da fiyat sayfası gibi haber olmayan bağlantılar, başlıkta
başka bir borsa kodu geçen (aynı adlı başka şirket) haberler, Form 4 bildiriminden
otomatik üretilmiş başlıklar (bu işlemler sitede zaten ayrıca gösteriliyor) ve
neredeyse aynı başlığı taşıyan tekrarlar.

Sonuçlar 30 dakika bellekte tutulur.
"""

import re

from piyasa import haber
from piyasa.bicim import sirket_gorunen_ad
from piyasa.onbellek import sureli
from piyasa.sirket_profili import cevir

ONBELLEK_SURESI = 30 * 60
GUN = 30
ADET = 10
TURKCE_YETERLI = 5            # bundan az Türkçe haber varsa İngilizceyle tamamlanır

# Tek başına aranırsa başka şeylerle karışan ilk kelimeler: adın tamamı aranır
GENEL_KELIMELER = {
    "the", "first", "general", "american", "united", "international", "national", "global",
    "applied", "advanced", "digital", "big", "new", "great", "southern", "northern", "western",
    "eastern", "central", "royal", "public", "universal", "texas", "group", "bank", "capital",
}

# Haber olmayan sayfalar (fiyat sayfası, şirket bilgi sayfası, yatırımcı ilişkileri)
HABER_DEGIL = re.compile(
    r"stock price|price, news|quote and history|investor relations|hisse fiyatı|hisse senedi fiyatı|"
    r"canlı fiyat|grafiği ve|company profile|\| stock|stock quote",
    re.IGNORECASE,
)

# Yönetici işlem bildirimlerinden otomatik başlık üreten kaynaklar ve başlıklar
OTOMATIK_KAYNAKLAR = ("stock titan", "marketbeat", "tipranks auto")
OTOMATIK_BASLIK = re.compile(
    r"^form (4|144)\b|\bform 4\b.*\bfor\b|"
    r"\b(director|officer|ceo|cfo|coo|president|chairman|insider|chief \w+ officer)\b.{0,80}"
    r"\b(buys|sells|acquires|disposes|purchases|sold|bought|picks up|unloads)\b.{0,40}\bshares\b",
    re.IGNORECASE,
)

# Başlıktaki borsa kodu: '(NASDAQ: AIP)', '(OTCMKTS:FMCB)', '(CRDO)'
KOD_IZI = re.compile(r"\((?:[A-Z]+:\s?)?([A-Z]{1,5}(?:\.[A-Z])?)\)")

BENZERLIK_SINIRI = 0.7

_TR_KUCUK = str.maketrans("Iİ", "ıi")


def _kucuk(metin):
    return metin.translate(_TR_KUCUK).lower()


def arama_adi(sirket):
    """'LOCKHEED MARTIN CORP' -> 'Lockheed Martin'"""
    return sirket_gorunen_ad(sirket)


def _ilgili_mi(baslik, ad, ticker):
    """Başlıkta şirket adı (ya da ayırt edici ilk kelimesi) veya borsa kodu geçiyor mu?"""
    kucuk = _kucuk(baslik)
    kelimeler = ad.split()
    anahtar = kelimeler[0] if kelimeler and len(kelimeler[0]) >= 5 and \
        kelimeler[0].lower() not in GENEL_KELIMELER else ad
    if _kucuk(anahtar) in kucuk:
        return True
    return bool(re.search(rf"\b{re.escape(ticker)}\b", baslik))


def _baska_sirket_mi(baslik, ticker):
    """Başlıkta borsa kodu var ve hiçbiri bu şirketin kodu değilse aynı adlı başka şirkettir."""
    kodlar = KOD_IZI.findall(baslik)
    return bool(kodlar) and ticker not in kodlar


def _elenir_mi(h, ad, ticker):
    return (HABER_DEGIL.search(h["baslik"]) or OTOMATIK_BASLIK.search(h["baslik"])
            or any(k in h["kaynak"].lower() for k in OTOMATIK_KAYNAKLAR)
            or not _ilgili_mi(h["baslik"], ad, ticker) or _baska_sirket_mi(h["baslik"], ticker))


def _kelimeler(baslik):
    return {k for k in re.findall(r"\w+", _kucuk(baslik)) if len(k) > 2}


def tekrarlari_ele(haberler):
    """Kelimelerinin çoğu ortak olan başlıklardan yalnızca ilki (en yenisi) kalır."""
    kalan, gorulen = [], []
    for h in haberler:
        k = _kelimeler(h["baslik"])
        if any(k and len(k & g) / min(len(k), len(g)) >= BENZERLIK_SINIRI for g in gorulen if g):
            continue
        gorulen.append(k)
        kalan.append(h)
    return kalan


def _basliklari_cevir(haberler):
    """İngilizce başlıkları tek istekle çevirir; olmazsa tek tek, o da olmazsa olduğu gibi bırakır."""
    if not haberler:
        return haberler
    toplu = cevir("\n".join(h["baslik"] for h in haberler))
    satirlar = toplu.split("\n") if toplu else []
    if len(satirlar) != len(haberler):
        satirlar = [cevir(h["baslik"]) for h in haberler]
    for h, tr in zip(haberler, satirlar, strict=True):
        h["orijinal"] = h["baslik"]
        h["baslik"] = (tr or h["baslik"]).strip()
    return haberler


def _al(ticker, ad):
    def ele(h):
        return _elenir_mi(h, ad, ticker)

    turkce = tekrarlari_ele(haber.sec(
        haber.indir(f'"{ad}" (hisse OR hisseleri OR hissesi OR şirket OR şirketi)', "tr", GUN), ADET * 2, ele))[:ADET]
    for h in turkce:
        h["dil"] = "tr"
    if len(turkce) >= TURKCE_YETERLI:
        return turkce
    ingilizce = tekrarlari_ele(haber.sec(
        haber.indir(f'"{ad}" ({ticker} OR stock OR shares)', "en", GUN), ADET * 2, ele))[:ADET - len(turkce)]
    for h in ingilizce:
        h["dil"] = "en"
    return tekrarlari_ele(turkce + _basliklari_cevir(ingilizce))


@sureli(ONBELLEK_SURESI, hatada_eskisi=True)
def _haberler(ticker, ad):
    return _al(ticker, ad)


def hisse_haberleri(ticker, sirket):
    """Şirketin son 30 günlük haberleri (yeniden eskiye); ağ hatasında boş liste."""
    ad = arama_adi(sirket)
    if not ad:
        return []
    try:
        haberler = _haberler(ticker.upper(), ad)
    except Exception:
        return []
    return sorted(haberler, key=lambda h: h["zaman"], reverse=True)
