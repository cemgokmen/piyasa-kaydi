"""
Sayı, tutar ve tarihleri Türkçe gösterime çeviren saf yardımcılar.
Web'e bağımlı değildir; analiz ve özet metinleri de bunları kullanır.
"""

import re
from datetime import date

AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
         "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
AYLAR_UZUN = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
              "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


# ---------------------------------------------------------------------------
# SAYILAR VE TUTARLAR
# ---------------------------------------------------------------------------

def sayi(n):
    """1234567 -> '1.234.567'"""
    return f"{int(n or 0):,}".replace(",", ".")


def tam_tutar(alt, ust):
    """Tam yazım: '1.001 – 15.000 $'"""
    if alt is None:
        return "—"
    if alt == ust:
        return f"{sayi(alt)} $"
    return f"{sayi(alt)} – {sayi(ust)} $"


def kisa_tutar(n):
    """1250000 -> '1,3 mn $'"""
    if not n:
        return "0 $"
    for bolen, ek in ((1e12, "trl"), (1e9, "mr"), (1e6, "mn")):
        if n >= bolen:
            return f"{n / bolen:.1f}".replace(".", ",") + f" {ek} $"
    if n >= 1_000:
        return f"{n / 1_000:.0f} bin $"
    return f"{sayi(n)} $"


def kisa_aralik(alt, ust):
    """Kongre bildirimleri aralık verir: '1 bin – 15 bin $'"""
    if alt is None:
        return "—"
    alt, ust = alt or 0, ust or 0
    if alt == ust:
        return kisa_tutar(alt)
    return f"{kisa_tutar(alt)[:-2]} – {kisa_tutar(ust)}"


def yuzde(oran, isaretli=True):
    """0.0532 -> '+%5,32'"""
    if oran is None:
        return "—"
    isaret = ("+" if oran > 0 else "−" if oran < 0 else "") if isaretli else ""
    return f"{isaret}%{abs(oran) * 100:.2f}".replace(".", ",")


def ondalik(n, basamak=1):
    """32.456 -> '32,5'"""
    if n is None:
        return "—"
    tam, _, kesir = f"{n:,.{basamak}f}".partition(".")
    tam = tam.replace(",", ".")
    return f"{tam},{kesir}" if kesir else tam


def fiyat(n):
    """123.456 -> '123,46'"""
    if n is None:
        return "—"
    tam, kesir = f"{n:,.2f}".split(".")
    return f"{tam.replace(',', '.')},{kesir}"


# ---------------------------------------------------------------------------
# TARİHLER
# ---------------------------------------------------------------------------

def tarih_temizle(ham):
    """Saat dilimi ekli tarihleri temizler: '2026-06-12-05:00' -> '2026-06-12'"""
    return ham[:10] if ham and len(ham) >= 10 else ham


def kisa_tarih(iso):
    """'2026-08-18' -> '18 Ağu'"""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {AYLAR[d.month - 1]}"


def uzun_tarih(iso):
    """'2026-08-18' -> '18 Ağustos 2026'"""
    if not iso:
        return ""
    d = date.fromisoformat(str(iso)[:10])
    return f"{d.day} {AYLAR_UZUN[d.month - 1]} {d.year}"


def donem_metni(donem):
    """'2026-06-30' -> '2026 2. çeyrek'"""
    yil, ay, _ = donem.split("-")
    return f"{yil} {(int(ay) - 1) // 3 + 1}. çeyrek"


# ---------------------------------------------------------------------------
# ŞİRKET ADLARI
# ---------------------------------------------------------------------------

_HISSE_TURU = re.compile(
    r"\s*[-–,]?\s*\b(common stock|ordinary shares?|class [a-c]( common stock)?|"
    r"american depositary shares?|ads|sponsored adr|shares?|common)\b.*$",
    re.IGNORECASE,
)
_SIRKET_EKI = re.compile(
    r"[\s,]+(corporation|corp\.?|incorporated|inc\.?|company|co\.?|ltd\.?|limited|plc|n\.?v\.?|s\.?a\.?|l\.?p\.?|ag|se|new)$",
    re.IGNORECASE,
)


def sirket_kisa_ad(ad):
    """'General Dynamics Corporation Common Stock' -> 'General Dynamics'; 'RTX Corporation' -> 'RTX'"""
    ad = re.split(r"\s+-\s+", (ad or "").strip())[0]       # 'Alphabet Inc. - Class A'
    ad = _HISSE_TURU.sub("", ad)
    onceki = None
    while onceki != ad:
        yeni = _SIRKET_EKI.sub("", ad).strip(" ,.")
        if yeni.endswith(("&", " and")):     # 'KKR & Co.', 'Eli Lilly and Company' bir bütündür
            break
        onceki, ad = ad, yeni
    return re.sub(r"^The\s+(?=\S)", "", ad)                # 'The Hershey Company' -> 'Hershey'
