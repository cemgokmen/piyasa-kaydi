"""
Şirketin kısaca ne iş yaptığı: hisse sayfasındaki "Şirket hakkında" kutusu.

İş tanımı, sektör, çalışan sayısı ve merkez Yahoo Finance'ten alınır.
İngilizce tanım önce sadeleştirilir (uzun ülke listeleri, "bağlı
ortaklıklarıyla birlikte" gibi kalıplar, segment ayrıntıları ve resmi unvan
çıkarılır), sonra ücretsiz çeviri servisiyle Türkçeye çevrilir ve fiil
kipleri tek tipe getirilir. Sonuç veritabanında saklanır; profil 120 günde
bir yenilenir.

Toplu doldurmak için:  python -m piyasa profiller  (piyasa/toplama/profiller.py)
"""

import re
from contextlib import closing
from datetime import UTC, datetime, timedelta

import requests
import yfinance as yf

from piyasa import fiyat
from piyasa.bicim import sirket_kisa_ad
from piyasa.veritabani import get_connection

# Ücretsiz, anahtarsız çeviri uçları: önce Google'ın tarayıcı eklentisi ucu,
# olmazsa MyMemory (günlük kotalı)
GOOGLE_CEVIRI = "https://clients5.google.com/translate_a/t"
MYMEMORY = "https://api.mymemory.translated.net/get"
YENILEME = timedelta(days=120)
OZET_UZUNLUGU = 300          # karakter: uzun tanımın ilk bir-iki cümlesi

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


# ---------------------------------------------------------------------------
# Çeviriden sonra: Türkçeyi düzeltme
# ---------------------------------------------------------------------------

# Çeviri aynı metinde '-yor' ile geniş zamanı karıştırıyor; şirket tanımında
# geniş zaman doğal olandır
_GENIS_ZAMAN = {
    "tasarlıyor": "tasarlar", "üretiyor": "üretir", "pazarlıyor": "pazarlar", "satıyor": "satar",
    "sunuyor": "sunar", "sağlıyor": "sağlar", "geliştiriyor": "geliştirir", "işletiyor": "işletir",
    "gösteriyor": "gösterir", "dağıtıyor": "dağıtır", "yapıyor": "yapar", "ediyor": "eder",
    "veriyor": "verir", "kiralıyor": "kiralar", "araştırıyor": "araştırır", "keşfediyor": "keşfeder",
    "ticarileştiriyor": "ticarileştirir", "yönetiyor": "yönetir", "tedarik ediyor": "tedarik eder",
    "faaliyet gösteriyor": "faaliyet gösterir", "işliyor": "işler", "üstleniyor": "üstlenir",
    "lisanslıyor": "lisanslar", "inşa ediyor": "inşa eder", "çıkarıyor": "çıkarır",
    "taşıyor": "taşır", "yatırım yapıyor": "yatırım yapar", "kuruyor": "kurar", "tutuyor": "tutar",
}
_YOR = re.compile(r"\b(" + "|".join(sorted((k for k in _GENIS_ZAMAN if k.endswith("yor")), key=len, reverse=True)) + r")\b")
# Ekleriyle birlikte doğrudan karşılıkları (ek uyumu bozulmasın diye tek tek)
_KELIMELER = {
    "Amerika Birleşik Devletleri": "ABD", "Amerika Birleşik Devletleri'nde": "ABD'de",
    "Amerika Birleşik Devletleri'ndeki": "ABD'deki", "Amerika Birleşik Devletleri'nin": "ABD'nin",
    "segment": "bölüm", "segmenti": "bölümü", "segmentte": "bölümde", "segmentler": "bölümler",
    "segmentleri": "bölümleri", "segmentinde": "bölümünde", "segmentlerinde": "bölümlerinde",
    "segmentlerde": "bölümlerde", "segmentlerinden": "bölümlerinden",
}
_KELIME = re.compile(r"(?<!\w)(" + "|".join(re.escape(k) for k in sorted(_KELIMELER, key=len, reverse=True)) + r")(?!\w)")
_TR_KUCUK = str.maketrans("Iİ", "ıi")


# Çeviri servisi şirket adlarını da çevirebiliyor ("Applied Materials" ->
# "Uygulamalı Malzemeler"); ad çeviri sırasında bu yer tutucuyla korunur
_AD_YERI = "XQZ"


def adi_koruyarak_cevir(metin, ad):
    if not ad or ad not in metin or _AD_YERI in metin:
        return cevir(metin)
    sonuc = cevir(metin.replace(ad, _AD_YERI))
    return sonuc.replace(_AD_YERI, ad) if sonuc and _AD_YERI in sonuc else cevir(metin)


def fon_tanimi(ad, yonetici=None):
    yonetim = f", {yonetici} tarafından yönetilen," if yonetici else ","
    return f"{ad}{yonetim} borsada işlem gören bir yatırım fonudur (ETF). Tek bir şirket değil, bir hisse sepetini temsil eder."


# Şapkalı harfler (a, i, u üstünde) kullanılmaz; çeviriden gelse de sade harfe çevrilir
_SAPKASIZ = str.maketrans({"\u00e2": "a", "\u00ee": "i", "\u00fb": "u", "\u00c2": "A", "\u00ce": "\u0130", "\u00db": "U"})


def turkcelestir(metin):
    metin = (metin or "").translate(_SAPKASIZ)
    metin = _YOR.sub(lambda m: _GENIS_ZAMAN[m.group(1)], metin or "")
    metin = _KELIME.sub(lambda m: _KELIMELER[m.group(0)], metin)
    metin = re.sub(r"\s+([,.;])", r"\1", metin)
    return metin.strip()


def baslik_duzelt(metin):
    """'Otomobil Üreticileri' -> 'Otomobil üreticileri' (kısaltmalar korunur)."""
    if not metin:
        return metin
    kelimeler = metin.split()
    return " ".join([kelimeler[0]] + [k if k.isupper() and len(k) > 1 else k.translate(_TR_KUCUK).lower()
                                      for k in kelimeler[1:]])


def _google(metin):
    cevap = requests.get(GOOGLE_CEVIRI, params={"client": "dict-chrome-ex", "sl": "en", "tl": "tr", "q": metin},
                         timeout=20)
    cevap.raise_for_status()
    ilk = cevap.json()[0]
    return ilk[0] if isinstance(ilk, list) else ilk      # kaynak dil otomatikse [metin, dil]


def _mymemory(metin):
    cevap = requests.get(MYMEMORY, params={"q": metin[:500], "langpair": "en|tr"}, timeout=20)
    cevap.raise_for_status()
    govde = cevap.json()
    if govde.get("responseStatus") != 200 or govde.get("quotaFinished"):
        return None
    return govde["responseData"]["translatedText"]


def cevir(metin):
    """İngilizceden Türkçeye; hiçbir servis cevap vermezse None."""
    if not metin:
        return None
    for servis in (_google, _mymemory):
        try:
            sonuc = (servis(metin) or "").strip()
            if sonuc and sonuc != metin:
                return sonuc
        except Exception:
            continue
    return None


def _getir(ticker):
    bilgi = yf.Ticker(fiyat.yahoo_kodu(ticker)).info or {}
    tanim = bilgi.get("longBusinessSummary")
    if not tanim:
        return None
    if bilgi.get("quoteType") == "ETF":
        # Fon tanımları hukuki dille yazılır; yerine kısa, doğal bir cümle
        ozet_en = None
        ozet = fon_tanimi(bilgi.get("longName") or ticker, bilgi.get("fundFamily"))
    else:
        ozet_en = sadelestir(tanim, bilgi.get("longName"))
        ozet = adi_koruyarak_cevir(ozet_en, sirket_kisa_ad(bilgi.get("longName") or ""))
    sektor = bilgi.get("sectorDisp") or bilgi.get("sector")
    endustri = bilgi.get("industryDisp") or bilgi.get("industry")
    merkez = ", ".join(x for x in (bilgi.get("city"), bilgi.get("state") or bilgi.get("country")) if x)
    return {
        "ticker": ticker,
        "ozet": turkcelestir(ozet) if ozet and ozet_en else ozet,
        "ozet_en": ozet_en,
        "sektor": SEKTORLER.get(sektor, sektor),
        "endustri": baslik_duzelt(turkcelestir(cevir(endustri))) if endustri else None,
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


def kayitli(ticker):
    """Yalnızca veritabanındaki profil (ağa çıkmaz); yoksa None."""
    with closing(get_connection()) as conn:
        kayit = conn.execute("SELECT * FROM sirket_profili WHERE ticker = ? AND ozet IS NOT NULL",
                             (ticker.upper(),)).fetchone()
    return dict(kayit) if kayit else None


def profil(ticker):
    """Kayıtlı profil; yoksa ya da eskiyse Yahoo'dan alınır. Bulunamazsa None."""
    ticker = ticker.upper()
    with closing(get_connection()) as conn:
        kayit = conn.execute("SELECT * FROM sirket_profili WHERE ticker = ?", (ticker,)).fetchone()
        if kayit and not _eski_mi(kayit):
            return dict(kayit)
        try:
            yeni = _getir(ticker)
        except Exception:
            yeni = None
        if yeni:
            _kaydet(conn, yeni)
            return yeni
    return dict(kayit) if kayit else None

