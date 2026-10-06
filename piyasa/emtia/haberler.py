"""
Emtia haberleri: Google Haberler'in Türkçe RSS akışından son iki haftanın
başlıkları. Başlıklar konuya göre (merkez bankası, OPEC, arz, talep...)
etiketlenir; "bugün gram altın ne kadar?" türü günlük fiyat listeleri elenir.

Sonuçlar 30 dakika bellekte tutulur.
"""

import re
import threading
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

from piyasa.emtia.tanimlar import HABER_ETIKETLERI

RSS_URL = "https://news.google.com/rss/search?q={sorgu}&hl=tr&gl=TR&ceid=TR:tr"
ONBELLEK_SURESI = 30 * 60

# Hükümet ve merkez bankası kararları için ortak arama
KARAR_SORGUSU = (
    '(OPEC OR "Fed faiz" OR "Merkez Bankası faiz" OR yaptırım OR "gümrük vergisi" OR ambargo) '
    '(petrol OR altın OR emtia OR doğalgaz OR buğday)'
)

# Bilgi taşımayan, her gün tekrarlanan fiyat listesi başlıkları
FIYAT_LISTESI = re.compile(
    r"ne kadar|kaç tl|canlı|anlık|güncel (rakam|fiyat)|fiyatları bugün|güne nasıl|"
    r"alış.?satış|'?(da|de|ta|te) altın fiyatları|"
    r"\b\d{1,2} (ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık)\b",
    re.IGNORECASE,
)

# Sosyal medya paylaşımları haber sayılmaz
ELENEN_KAYNAKLAR = ("instagram", "facebook", "youtube", "tiktok", "x.com", "twitter")

_onbellek = {}
_kilit = threading.Lock()


def etiketle(baslik):
    kucuk = baslik.lower()
    return [ad for ad, kelimeler in HABER_ETIKETLERI if any(k in kucuk for k in kelimeler)]


def _ayristir(xml_metni):
    haberler = []
    for oge in ET.fromstring(xml_metni).iter("item"):
        baslik = oge.findtext("title") or ""
        kaynak = oge.findtext("source") or ""
        # Google başlığın sonuna " - Kaynak" ekliyor
        if kaynak and baslik.endswith(f" - {kaynak}"):
            baslik = baslik[: -len(kaynak) - 3]
        try:
            zaman = parsedate_to_datetime(oge.findtext("pubDate"))
        except (TypeError, ValueError):
            continue
        haberler.append({
            "baslik": baslik.strip(),
            "kaynak": kaynak,
            "adres": oge.findtext("link"),
            "zaman": zaman,
            "tarih": zaman.strftime("%Y-%m-%d"),
            "etiketler": etiketle(baslik),
        })
    return haberler


def _indir(sorgu):
    adres = RSS_URL.format(sorgu=quote(f"{sorgu} when:14d"))
    cevap = requests.get(adres, timeout=10, headers={"User-Agent": "Mozilla/5.0 PiyasaKaydi"})
    cevap.raise_for_status()
    return _ayristir(cevap.content)


def _sec(haberler, adet):
    """Yeniden eskiye sıralar, aynı başlıkları ve fiyat listelerini eler."""
    gorulen = set()
    secilen = []
    for h in sorted(haberler, key=lambda h: h["zaman"], reverse=True):
        anahtar = re.sub(r"\W+", " ", h["baslik"].lower())[:60]
        if anahtar in gorulen or FIYAT_LISTESI.search(h["baslik"]):
            continue
        if any(e in h["kaynak"].lower() for e in ELENEN_KAYNAKLAR):
            continue
        gorulen.add(anahtar)
        secilen.append(h)
        if len(secilen) >= adet:
            break
    return secilen


def haberler(sorgu, adet=12):
    """Sorgunun son iki haftadaki haberleri; ulaşılamazsa boş liste."""
    simdi = time.time()
    with _kilit:
        kayit = _onbellek.get(sorgu)
        if kayit and simdi - kayit[0] < ONBELLEK_SURESI:
            return kayit[1][:adet]

    try:
        sonuc = _sec(_indir(sorgu), 40)
    except Exception:
        # Ağ hatasında eski sonucu (varsa) göster, yoksa boş dön
        return kayit[1][:adet] if kayit else []

    with _kilit:
        _onbellek[sorgu] = (simdi, sonuc)
    return sonuc[:adet]


def karar_haberleri(adet=10):
    """OPEC, merkez bankaları, yaptırım ve gümrük kararlarıyla ilgili haberler."""
    return haberler(KARAR_SORGUSU, adet)
