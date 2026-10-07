"""
Temsilciler Meclisi (kongre.py) ve Senato (senato.py) toplayıcılarının ortak
parçaları: üye listesi, ad sadeleştirme, tutar aralığı ve parti kodları.
"""

import re
import unicodedata

import requests

# Kongre'nin güncel ve geçmiş üyeleri (açık veri seti)
UYELER_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
GECMIS_UYELER_URL = "https://unitedstates.github.io/congress-legislators/legislators-historical.json"

PARTI_KISA = {"Democrat": "D", "Republican": "R", "Independent": "I"}

TUTAR = re.compile(r"\$([\d,]+)")


def json_al_uyeler(gecmis=False):
    """Kongre üyeleri (Meclis ve Senato) — congress-legislators veri seti."""
    return requests.get(GECMIS_UYELER_URL if gecmis else UYELER_URL, timeout=120).json()


def parti_kodu(parti):
    """'Democrat' -> 'D'"""
    return PARTI_KISA.get(parti, (parti or "")[:1])


def sade(metin):
    """'Sánchez' -> 'sanchez': aksanlı ve aksansız yazımlar eşleşsin."""
    ayrik = unicodedata.normalize("NFKD", metin or "")
    return "".join(c for c in ayrik if not unicodedata.combining(c)).lower()


def tutar_coz(metin):
    """'$1,001 - $15,000' -> (1001, 15000); 'Over $50,000,000' -> (50000000, 50000000)"""
    sayilar = [int(s.replace(",", "")) for s in TUTAR.findall(metin or "")]
    if not sayilar:
        return None, None
    return sayilar[0], sayilar[-1]


KRIPTO_SUTUNLARI = [
    "source_id", "source", "person", "person_slug", "chamber", "state", "party", "coin", "varlik", "ticker",
    "action", "amount_min", "amount_max", "transaction_date", "disclosed_date", "source_url", "sahip", "fetched_at",
]


def kripto_kaydet(conn, kayit):
    """Kongre bildirimindeki kripto para ya da kripto fonu işlemini kripto_islem tablosuna yazar."""
    degerler = [kayit.get(s) for s in KRIPTO_SUTUNLARI]
    imlec = conn.execute(
        f"INSERT OR IGNORE INTO kripto_islem ({', '.join(KRIPTO_SUTUNLARI)}) "
        f"VALUES ({', '.join('?' for _ in KRIPTO_SUTUNLARI)})",
        degerler,
    )
    return imlec.rowcount
