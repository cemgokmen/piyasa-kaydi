"""
Google Haberler RSS akışından haber başlıkları (emtia ve hisse haberlerinin ortak kısmı).

    indir('"Lockheed Martin" hisse', dil="tr", gun=30)  -> [{baslik, kaynak, adres, zaman, tarih}]
"""

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote

import requests

DILLER = {
    "tr": "hl=tr&gl=TR&ceid=TR:tr",
    "en": "hl=en-US&gl=US&ceid=US:en",
}
RSS_URL = "https://news.google.com/rss/search?q={sorgu}&{dil}"

# Sosyal medya paylaşımları haber sayılmaz
ELENEN_KAYNAKLAR = ("instagram", "facebook", "youtube", "tiktok", "x.com", "twitter")


def ayristir(xml_metni):
    haberler = []
    for oge in ET.fromstring(xml_metni).iter("item"):
        baslik = oge.findtext("title") or ""
        kaynak = oge.findtext("source") or ""
        # Google başlığın sonuna " - Kaynak" ekliyor
        if kaynak and baslik.endswith(f" - {kaynak}"):
            baslik = baslik[: -len(kaynak) - 3]
        # Bazı kaynakların adı yerine adresi geliyor: 'https://www.ensondakika.com.tr/' -> 'ensondakika.com.tr'
        if kaynak.startswith(("http://", "https://")):
            kaynak = kaynak.split("//", 1)[1].split("/", 1)[0].removeprefix("www.")
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
        })
    return haberler


def indir(sorgu, dil="tr", gun=14):
    adres = RSS_URL.format(sorgu=quote(f"{sorgu} when:{gun}d"), dil=DILLER[dil])
    cevap = requests.get(adres, timeout=10, headers={"User-Agent": "Mozilla/5.0 PiyasaKaydi"})
    cevap.raise_for_status()
    return ayristir(cevap.content)


def sec(haberler, adet, ele=None):
    """Yeniden eskiye sıralar; aynı başlıkları, sosyal medyayı ve ele(haber) True dönenleri çıkarır."""
    gorulen = set()
    secilen = []
    for h in sorted(haberler, key=lambda h: h["zaman"], reverse=True):
        anahtar = re.sub(r"\W+", " ", h["baslik"].lower())[:60]
        if anahtar in gorulen or (ele and ele(h)):
            continue
        if any(e in h["kaynak"].lower() for e in ELENEN_KAYNAKLAR):
            continue
        gorulen.add(anahtar)
        secilen.append(h)
        if len(secilen) >= adet:
            break
    return secilen
