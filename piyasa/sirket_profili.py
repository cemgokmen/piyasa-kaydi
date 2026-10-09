"""
Şirketin kısaca ne iş yaptığı: hisse sayfasındaki "Şirket hakkında" kutusu.

İş tanımı, sektör, çalışan sayısı ve merkez Yahoo Finance'ten alınır.

Tanımın kaynağı, öncelik sırasıyla:
  1. piyasa/veri/sirket_tanimlari.json: en çok işlem gören şirketler için
     Yahoo'nun resmi tanımına dayanarak elle yazılmış Türkçe metin. Dosyada
     yapılan düzeltme sayfaya hemen yansır (veritabanını beklemez).
  2. Otomatik çeviri: İngilizce tanım önce sadeleştirilir (uzun ülke listeleri, "bağlı
ortaklıklarıyla birlikte" gibi kalıplar, segment ayrıntıları ve resmi unvan
çıkarılır), sonra ücretsiz çeviri servisiyle Türkçeye çevrilir ve fiil
kipleri tek tipe getirilir. Sonuç veritabanında saklanır; profil 120 günde
bir yenilenir.

Toplu doldurmak için:  python -m piyasa profiller  (piyasa/toplama/profiller.py)
"""

import json
import re
from contextlib import closing
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path

import yfinance as yf

from piyasa import fiyat
from piyasa.bicim import sirket_kisa_ad
from piyasa.ceviri import adi_koruyarak_cevir, baslik_duzelt, cevir, turkcelestir
from piyasa.veritabani import get_connection

YENILEME = timedelta(days=120)
OZET_UZUNLUGU = 300          # karakter: uzun tanımın ilk bir-iki cümlesi

VERI = Path(__file__).parent / "veri"


@cache
def elle_yazilmis_tanimlar():
    """{KOD: Türkçe tanım}; en çok işlem gören şirketler için elle yazılmış metinler."""
    return json.loads((VERI / "sirket_tanimlari.json").read_text(encoding="utf-8"))


@cache
def endustriler():
    """Yahoo'nun faaliyet alanı adları -> Türkçe karşılıkları."""
    return json.loads((VERI / "endustriler.json").read_text(encoding="utf-8"))


def endustri_adi(ingilizce):
    """Sözlükte varsa elle yazılmış karşılık, yoksa çeviri."""
    if not ingilizce:
        return None
    return endustriler().get(ingilizce) or baslik_duzelt(turkcelestir(cevir(ingilizce)))


# Yahoo'nun 11 sektörü
SEKTORLER = {
    "Technology": "Teknoloji",
    "Healthcare": "Sağlık",
    "Financial Services": "Finansal hizmetler",
    "Consumer Cyclical": "Döngüsel tüketim",
    "Consumer Defensive": "Temel tüketim",
    "Industrials": "Sanayi",
    "Energy": "Enerji",
    "Utilities": "Kamu hizmetleri",
    "Real Estate": "Gayrimenkul",
    "Basic Materials": "Temel malzemeler",
    "Communication Services": "İletişim hizmetleri",
}


def kisalt(metin, sinir=OZET_UZUNLUGU):
    """Tanımın baştan, sınırı aşmayan tam cümleleri (en az ilk cümle)."""
    cumleler = re.split(r"(?<=[a-z0-9\)]\.)\s+(?=[A-Z])", (metin or "").strip())
    secilen = []
    for c in cumleler:
        if secilen and len(" ".join(secilen + [c])) > sinir:
            break
        secilen.append(c)
    return " ".join(secilen)


# ---------------------------------------------------------------------------
# Çeviriden önce: İngilizce tanımı sadeleştirme
# ---------------------------------------------------------------------------

_ULKELER = [
    "United States", "U.S.", "North America", "South America", "Latin America", "Central America",
    "Americas", "Europe", "Western Europe", "Eastern Europe", "Asia Pacific", "Asia-Pacific",
    "Southeast Asia", "Asia", "Middle East", "Africa", "EMEA", "Oceania", "Caribbean", "Puerto Rico",
    "China", "Japan", "Canada", "Mexico", "Brazil", "United Kingdom", "Germany", "France",
    "Ireland", "Israel", "Taiwan", "Hong Kong", "India", "Australia", "New Zealand", "Korea",
    "South Korea", "Singapore", "Switzerland", "Netherlands", "Italy", "Spain", "Sweden",
    "Norway", "Denmark", "Belgium", "Luxembourg", "Austria", "Finland", "Portugal", "Greece",
    "Poland", "Czech Republic", "Hungary", "Romania", "Ukraine", "Armenia", "Russia", "Turkey",
    "Scotland", "Bermuda", "Cayman Islands", "Scandinavia", "Nordic countries", "Greater China",
    "Mainland China", "Macau", "Argentina", "Chile", "Colombia", "Peru", "Philippines", "Indonesia",
    "Malaysia", "Thailand", "Vietnam", "South Africa", "Nigeria", "Egypt", "Saudi Arabia",
    "United Arab Emirates", "Qatar", "Continental Europe", "Guyana", "U.S. Virgin Islands",
    "internationally", "other countries",
]
_ULKE = r"(?:the\s+)?(?:rest of (?:the\s+)?)?(?:" + "|".join(re.escape(u) for u in sorted(_ULKELER, key=len, reverse=True)) + ")"
# ", in the United States, China, and internationally" gibi yer listeleri
_YER_LISTESI = re.compile(
    rf",?\s+(?:in|across|throughout)\s+{_ULKE}(?:(?:,\s*(?:and\s+)?|\s+and\s+){_ULKE})*(?=[\s,.;]|$)"
)
_DUNYA = re.compile(r",?\s+(?:and\s+)?(?:worldwide|globally|internationally)\b")
_BAGLI = re.compile(r",?\s+(?:together with|through) its (?:consolidated )?subsidiaries,?", re.IGNORECASE)

# "engages in the development, marketing, and sale of X" -> "develops, markets, and sells X"
_FIILLER = {
    "development": "develops", "marketing": "markets", "sale": "sells", "sales": "sells",
    "manufacture": "manufactures", "manufacturing": "manufactures", "design": "designs",
    "distribution": "distributes", "provision": "provides", "operation": "operates",
    "acquisition": "acquires", "exploration": "explores", "production": "produces",
    "ownership": "owns", "research": "researches", "commercialization": "commercializes",
    "discovery": "discovers", "licensing": "licenses", "construction": "constructs",
    "leasing": "leases", "supply": "supplies", "processing": "processes", "retail": "retails",
    "integration": "integrates", "sustainment": "sustains", "servicing": "services",
    "maintenance": "maintains", "installation": "installs", "refining": "refines",
}
_UGRASIR = re.compile(r"\bengages? in the ((?:[a-z]+(?:,\s*|\s+and\s+|,\s+and\s+))*[a-z]+) of\b")

# Kuruluş, merkez gibi ayrıca gösterilen bilgilerin ve yalnızca segment
# adlarını sayan cümleler
_ATLANAN = re.compile(r"\boperates? (?:through|in) .*\bsegments?\b|\bheadquartered\b|\bformerly known\b|\bchanged its name\b|"
                      r"\b(?:was )?(?:founded|incorporated|established) in\b|\bis a subsidiary of\b", re.IGNORECASE)
# Segment ayrıntısı: tanım zaten yeterince uzunsa alınmaz
_SEGMENT = re.compile(r"\bsegments?\b", re.IGNORECASE)
_YETERLI = 140
_KURULUS = re.compile(r"\b(?:founded|incorporated|established) in (\d{4})\b")


def _ugrasir_yerine_fiil(m):
    adlar = re.split(r",\s*(?:and\s+)?|\s+and\s+", m.group(1))
    if not all(a in _FIILLER for a in adlar):
        return m.group(0)
    fiiller = [_FIILLER[a] for a in adlar]
    return fiiller[0] if len(fiiller) == 1 else ", ".join(fiiller[:-1]) + ", and " + fiiller[-1]


def cumleler(metin):
    return [c for c in re.split(r"(?<=[a-z0-9\)]\.)\s+(?=[A-Z])", (metin or "").strip()) if c]


def kurulus_yili(metin):
    m = _KURULUS.search(metin or "")
    return int(m.group(1)) if m else None


def _temizle(cumle):
    cumle = _BAGLI.sub("", cumle)
    cumle = _YER_LISTESI.sub("", cumle)
    cumle = _DUNYA.sub("", cumle)
    cumle = _UGRASIR.sub(_ugrasir_yerine_fiil, cumle)
    return re.sub(r"\s+([,.;])", r"\1", re.sub(r"\s{2,}", " ", cumle)).strip()


def sadelestir(metin, resmi_ad=None):
    """Çeviriye gidecek kısa ve sade İngilizce tanım."""
    if resmi_ad and (metin or "").startswith(resmi_ad):
        kisa = sirket_kisa_ad(resmi_ad)
        if kisa:
            metin = kisa + metin[len(resmi_ad):]
    secilen = []
    for c in cumleler(metin):
        if _ATLANAN.search(c) or (_SEGMENT.search(c) and len(" ".join(secilen)) >= _YETERLI):
            continue
        secilen.append(_temizle(c))
    return kisalt(" ".join(secilen or [_temizle(c) for c in cumleler(metin)[:1]]))


def fon_tanimi(ad, yonetici=None):
    yonetim = f", {yonetici} tarafından yönetilen," if yonetici else ","
    return f"{ad}{yonetim} borsada işlem gören bir yatırım fonudur (ETF). Tek bir şirket değil, bir hisse sepetini temsil eder."



def _getir(ticker, yahoo=None):
    """yahoo: Yahoo kodu verilirse olduğu gibi kullanılır (Borsa İstanbul: 'THYAO.IS')."""
    bilgi = yf.Ticker(yahoo or fiyat.yahoo_kodu(ticker)).info or {}
    tanim = bilgi.get("longBusinessSummary")
    if not tanim:
        return None
    if bilgi.get("quoteType") == "ETF":
        # Fon tanımları hukuki dille yazılır; yerine kısa, doğal bir cümle
        ozet_en = None
        ozet = fon_tanimi(bilgi.get("longName") or ticker, bilgi.get("fundFamily"))
    else:
        ozet_en = sadelestir(tanim, bilgi.get("longName"))
        # Elle yazılmış tanımı olan şirket için çeviri servisine gidilmez
        ozet = elle_yazilmis_tanimlar().get(ticker.upper()) or \
            adi_koruyarak_cevir(ozet_en, sirket_kisa_ad(bilgi.get("longName") or ""))
    sektor = bilgi.get("sector") or bilgi.get("sectorDisp")
    endustri = bilgi.get("industry") or bilgi.get("industryDisp")
    merkez = ", ".join(x for x in (bilgi.get("city"), bilgi.get("state") or bilgi.get("country")) if x)
    return {
        "ticker": ticker,
        "ozet": turkcelestir(ozet) if ozet and ozet_en else ozet,
        "ozet_en": ozet_en,
        "sektor": SEKTORLER.get(sektor, sektor),
        "endustri": endustri_adi(endustri),
        "kurulus": kurulus_yili(tanim),
        "calisan": bilgi.get("fullTimeEmployees"),
        "merkez": merkez or None,
        "site": bilgi.get("website"),
        "guncelleme": datetime.now(UTC).isoformat(),
    }


def _kaydet(conn, p):
    conn.execute(
        """INSERT OR REPLACE INTO sirket_profili
           (ticker, ozet, ozet_en, sektor, endustri, calisan, merkez, site, kurulus, guncelleme)
           VALUES (:ticker, :ozet, :ozet_en, :sektor, :endustri, :calisan, :merkez, :site, :kurulus, :guncelleme)""",
        p,
    )
    conn.commit()


def _eski_mi(kayit):
    if not kayit["ozet"]:                         # çeviri başarısızdı: yeniden dene
        return True
    return datetime.fromisoformat(kayit["guncelleme"]) < datetime.now(UTC) - YENILEME


def _elle_yazilani_uygula(profil):
    if profil:
        elle = elle_yazilmis_tanimlar().get(profil["ticker"].upper())
        if elle:
            profil = dict(profil, ozet=elle)
    return profil


def kayitli(ticker):
    """Yalnızca veritabanındaki profil (ağa çıkmaz); yoksa None."""
    with closing(get_connection()) as conn:
        kayit = conn.execute("SELECT * FROM sirket_profili WHERE ticker = ? AND ozet IS NOT NULL",
                             (ticker.upper(),)).fetchone()
    return _elle_yazilani_uygula(dict(kayit)) if kayit else None


def yeniden_al(ticker):
    """Kayıtlı olsa da Yahoo'dan yeniden alıp kaydeder; alınamazsa False."""
    try:
        yeni = _getir(ticker.upper())
    except Exception:
        return False
    if not yeni:
        return False
    with closing(get_connection()) as conn:
        _kaydet(conn, yeni)
    return True


def profil(ticker, yahoo=None):
    """Kayıtlı profil; yoksa ya da eskiyse Yahoo'dan alınır. Bulunamazsa None."""
    ticker = ticker.upper()
    with closing(get_connection()) as conn:
        kayit = conn.execute("SELECT * FROM sirket_profili WHERE ticker = ?", (ticker,)).fetchone()
        if kayit and not _eski_mi(kayit):
            return _elle_yazilani_uygula(dict(kayit))
        try:
            yeni = _getir(ticker, yahoo)
        except Exception:
            yeni = None
        if yeni:
            _kaydet(conn, yeni)
            return _elle_yazilani_uygula(yeni)
    return _elle_yazilani_uygula(dict(kayit)) if kayit else None

