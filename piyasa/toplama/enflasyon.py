"""
Aylık tüketici fiyatları endeksi (enflasyon), yatırım karşılaştırma sayfası için.

  Türkiye  TCMB'nin TÜFE tablosu (aylık % değişim; TÜİK verisi). Endeks, aylık değişimlerin
           zincirlenmesiyle kurulur (ilk ay = 100); oranlar için mutlak düzeyi önemsizdir.
  ABD      FRED CPIAUCSL (ABD Çalışma İstatistikleri Bürosu, mevsimsellikten arındırılmış).

Çalıştırmak için:  python -m piyasa enflasyon
"""

import csv
import html
import io
import re
from datetime import UTC, datetime

import requests

from piyasa.ayarlar import USER_AGENT
from piyasa.veritabani import get_connection, init_db

TCMB_URL = ("https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Istatistikler/"
            "Enflasyon+Verileri/Tuketici+Fiyatlari")
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"
# FRED'e ulaşılamazsa: OECD'nin ABD tüketici fiyatları endeksi
OECD_URL = ("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL,1.0/"
            "USA.M.N.CPI.IX._T.N._Z?startPeriod=2000-01&format=csvfile")
# Tarayıcı kimliği olmadan TCMB sayfası boş dönebiliyor
TARAYICI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36"
# Tablo satırı: '09-2026 29.73 1.84' → ay, yıllık %, aylık %
SATIR = re.compile(r"\b(\d{2})-(\d{4})\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")


def tcmb_aylik(sayfa):
    """{'2026-09': 1.84, ...} — TÜFE aylık % değişimleri."""
    metin = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", sayfa)))
    return {f"{yil}-{ay}": float(aylik) for ay, yil, _, aylik in SATIR.findall(metin)}


def zincirle(aylik):
    """Aylık % değişimlerden endeks: [(ay, endeks, aylik)], ilk ay 100."""
    aylar = sorted(aylik)
    sonuc, endeks = [], 100.0
    for i, ay in enumerate(aylar):
        if i:
            endeks *= 1 + aylik[ay] / 100
        sonuc.append((ay, endeks, aylik[ay]))
    return sonuc


def fred_endeks(metin):
    """[(ay, endeks, aylik %)] — FRED CSV'sinden."""
    satirlar = [(r[0][:7], float(r[1])) for r in csv.reader(io.StringIO(metin)) if r and r[0][:1].isdigit() and r[1] not in ("", ".")]
    return [(ay, deger, (deger / satirlar[i - 1][1] - 1) * 100 if i else None) for i, (ay, deger) in enumerate(satirlar)]


def oecd_endeks(metin):
    satirlar = sorted((r["TIME_PERIOD"], float(r["OBS_VALUE"])) for r in csv.DictReader(io.StringIO(metin))
                      if r.get("OBS_VALUE"))
    return [(ay, deger, (deger / satirlar[i - 1][1] - 1) * 100 if i else None) for i, (ay, deger) in enumerate(satirlar)]


def abd_endeksi():
    try:
        cevap = requests.get(FRED_URL, headers={"User-Agent": USER_AGENT}, timeout=60)
        cevap.raise_for_status()
        return fred_endeks(cevap.text), "FRED"
    except requests.RequestException:
        cevap = requests.get(OECD_URL, headers={"User-Agent": USER_AGENT}, timeout=60)
        cevap.raise_for_status()
        return oecd_endeks(cevap.text), "OECD"


def kaydet(conn, ulke, satirlar):
    simdi = datetime.now(UTC).isoformat()
    conn.execute("DELETE FROM enflasyon WHERE ulke = ?", (ulke,))
    conn.executemany("INSERT INTO enflasyon (ulke, ay, endeks, aylik, guncelleme) VALUES (?, ?, ?, ?, ?)",
                     [(ulke, ay, e, a, simdi) for ay, e, a in satirlar])
    conn.commit()


def main():
    init_db()
    conn = get_connection()
    try:
        cevap = requests.get(TCMB_URL, headers={"User-Agent": TARAYICI}, timeout=60)
        cevap.raise_for_status()
        aylik = tcmb_aylik(cevap.text)
        if len(aylik) < 120:                     # sayfa yapısı değiştiyse eski veriyi silme
            raise RuntimeError(f"TCMB TÜFE tablosu okunamadı ({len(aylik)} ay)")
        tr = zincirle(aylik)
        kaydet(conn, "TR", tr)
        print(f"  Türkiye TÜFE: {len(tr)} ay, {tr[0][0]} – {tr[-1][0]}", flush=True)

        abd, kaynak = abd_endeksi()
        if len(abd) < 120:
            raise RuntimeError(f"ABD TÜFE okunamadı ({len(abd)} ay)")
        kaydet(conn, "US", abd)
        print(f"  ABD TÜFE ({kaynak}): {len(abd)} ay, {abd[0][0]} – {abd[-1][0]}", flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
