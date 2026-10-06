"""
Şirketin kısaca ne iş yaptığı: hisse sayfasındaki "Şirket hakkında" kutusu.

İş tanımı, sektör, çalışan sayısı ve merkez Yahoo Finance'ten alınır. İngilizce
tanımın ilk birkaç cümlesi ücretsiz Google Çeviri ile Türkçeye çevrilir ve
veritabanında saklanır; profil 120 günde bir yenilenir.

Toplu doldurmak için:  python -m piyasa profiller  (piyasa/toplama/profiller.py)
"""

import re
from contextlib import closing
from datetime import UTC, datetime, timedelta

import requests
import yfinance as yf

from piyasa import fiyat
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
    ozet_en = kisalt(bilgi.get("longBusinessSummary"))
    if not ozet_en:
        return None
    sektor = bilgi.get("sectorDisp") or bilgi.get("sector")
    endustri = bilgi.get("industryDisp") or bilgi.get("industry")
    merkez = ", ".join(x for x in (bilgi.get("city"), bilgi.get("state") or bilgi.get("country")) if x)
    return {
        "ticker": ticker,
        "ozet": cevir(ozet_en),
        "ozet_en": ozet_en,
        "sektor": SEKTORLER.get(sektor, sektor),
        "endustri": cevir(endustri) if endustri else None,
        "calisan": bilgi.get("fullTimeEmployees"),
        "merkez": merkez or None,
        "site": bilgi.get("website"),
        "guncelleme": datetime.now(UTC).isoformat(),
    }


def _kaydet(conn, p):
    conn.execute(
        """INSERT OR REPLACE INTO sirket_profili
           (ticker, ozet, ozet_en, sektor, endustri, calisan, merkez, site, guncelleme)
           VALUES (:ticker, :ozet, :ozet_en, :sektor, :endustri, :calisan, :merkez, :site, :guncelleme)""",
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

