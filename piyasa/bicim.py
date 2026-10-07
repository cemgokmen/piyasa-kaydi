"""
Sayı, tutar ve tarihleri Türkçe gösterime çeviren saf yardımcılar.
Web'e bağımlı değildir; analiz ve özet metinleri de bunları kullanır.
"""

import re
from datetime import UTC, date, datetime

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


PARA_BIRIMLERI = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "TRY": "₺"}


def para(n, birim="USD"):
    """Eksi değer ve farklı para birimiyle kısa tutar: -2.5e9 -> '−2,5 mr $'; TWD -> '4,4 trl TWD'"""
    if n is None:
        return "—"
    simge = PARA_BIRIMLERI.get(birim or "USD", birim)
    isaret = "−" if n < 0 else ""
    n = abs(n)
    for bolen, ek in ((1e12, "trl"), (1e9, "mr"), (1e6, "mn")):
        if n >= bolen:
            return f"{isaret}{n / bolen:.1f}".replace(".", ",") + f" {ek} {simge}"
    if n >= 1_000:
        return f"{isaret}{n / 1_000:.0f} bin {simge}"
    return f"{isaret}{fiyat(n)} {simge}"


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
    ad = re.sub(r"\s*/[A-Z]{2,}/?\s*$", "", ad)              # 'LENNAR CORP /NEW/', 'XYZ INC /DE/'
    ad = _HISSE_TURU.sub("", ad)
    onceki = None
    while onceki != ad:
        yeni = _SIRKET_EKI.sub("", ad).strip(" ,.")
        if yeni.endswith(("&", " and")):     # 'KKR & Co.', 'Eli Lilly and Company' bir bütündür
            break
        onceki, ad = ad, yeni
    return re.sub(r"^The\s+(?=\S)", "", ad)                # 'The Hershey Company' -> 'Hershey'


_TR_KUCUK = str.maketrans("Iİ", "ıi")


def tr_kucuk(metin):
    """Türkçe küçük harf: 'IĞDIR' -> 'ığdır' (str.lower 'I'yı 'i' yapar)."""
    return (metin or "").translate(_TR_KUCUK).lower()


# SEC ve 13F bildirimlerindeki kısaltmalar
AD_KISALTMALARI = {
    "FINL": "Financial", "INDS": "Industries", "HLDGS": "Holdings", "HLDG": "Holding", "HLDS": "Holdings",
    "INTL": "International", "TECHN": "Technologies", "TECHNOLOGIE": "Technologies", "TECH": "Technology",
    "FGHT": "Freight", "MTRS": "Motors", "PETE": "Petroleum", "SVCS": "Services", "SYS": "Systems",
    "PHARMACEUTICALS": "Pharmaceuticals", "PHARMA": "Pharma", "MGMT": "Management", "LABS": "Laboratories",
    "NATL": "National", "AMER": "America", "BK": "Bank", "HLTH": "Health", "ENTMT": "Entertainment",
    "RES": "Resources", "PPTYS": "Properties", "MFG": "Manufacturing", "PRODS": "Products",
    "SOLUTNS": "Solutions", "COMMUN": "Communications", "ELEC": "Electric", "ENGR": "Engineering",
    "INVT": "Investment", "RLTY": "Realty", "RTY": "Royalty", "AIRLS": "Airlines", "CTRY": "Country",
    "ENTMNT": "Entertainment", "GRP": "Group", "BANCSHARES": "Bancshares", "SCIENCES": "Sciences",
}


# Kısaltma sanılmaması gereken kısa kelimeler
KISA_KELIMELER = {"SUN", "NEW", "ONE", "AIR", "BIG", "RED", "SEA", "OIL", "GAS", "CAR", "BIO", "BOX", "TWO",
                  "SKY", "LIFE", "BAY", "OAK", "ICE", "ARC", "AND", "OF", "THE", "FOR"}


def sirket_gorunen_ad(ad):
    """SEC'in büyük harfli adını okunur yapar: 'LOCKHEED MARTIN CORP' -> 'Lockheed Martin'.
    Kısaltmalar (3 harf ve altı, ör. 'IBM', 'AT&T') büyük kalır."""
    kisa = sirket_kisa_ad(ad or "")
    if not kisa.isupper() or len(kisa) <= 4:
        return kisa
    kelimeler = [AD_KISALTMALARI.get(k.strip(".,"), k) for k in kisa.split()]
    def duzelt(k):
        if not k.isupper() or not k.isalpha():
            return k
        if k in ("AND", "OF", "FOR", "THE"):
            return k.lower()
        return k.capitalize() if len(k) > 3 or k in KISA_KELIMELER else k
    return " ".join(duzelt(k) for k in kelimeler)


def ne_zaman(an, simdi=None):
    """Haber zamanı: 'bugün', 'dün', '3 gün önce'; bir haftadan eskiyse '18 Eyl'."""
    if an is None:
        return ""
    simdi = simdi or datetime.now(UTC)
    gun = (simdi.date() - an.astimezone(simdi.tzinfo).date()).days if an.tzinfo else (simdi.date() - an.date()).days
    if gun <= 0:
        return "bugün"
    if gun == 1:
        return "dün"
    if gun < 7:
        return f"{gun} gün önce"
    return kisa_tarih(an.date().isoformat())
