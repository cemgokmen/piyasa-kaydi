"""
Sayı, tutar ve tarihleri Türkçe gösterime çeviren yardımcılar ve
Jinja şablon süzgeçleri.
"""

from datetime import date

import numpy as np

from piyasa.slug import slugify

AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
         "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
AYLAR_UZUN = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
              "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

PARTILER = {
    "D": ("Demokrat", "dem"),
    "R": ("Cumhuriyetçi", "rep"),
    "I": ("Bağımsız", "ind"),
}

# Yasal bildirim süreleri. Form 4: işlemden sonra 2 iş günü.
# STOCK Act: işlemden sonra en geç 45 gün.
FORM4_IS_GUNU = 2
STOCK_ACT_GUN = 45

# Kongre bildiriminde alt sınırı bu tutar ve üzerindeki alımlar "yüklü" sayılır
YUKLU_ALIM_ALT_SINIR = 50_001


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
# KAYITLAR
# ---------------------------------------------------------------------------

def parti_bilgisi(kod):
    if not kod or kod not in PARTILER:
        return None
    ad, sinif = PARTILER[kod]
    return {"kod": kod, "ad": ad, "sinif": sinif}


def rol_metni(kayit):
    if kayit.get("chamber"):
        parcalar = [kayit["chamber"], kayit.get("state")]
        return " · ".join(p for p in parcalar if p)
    return kayit.get("job_title") or "Bildirim yükümlüsü"


def gec_mi(kayit):
    """Bildirim yasal süreden sonra mı yapılmış?"""
    if kayit.get("chamber"):
        return kayit["gecikme"] > STOCK_ACT_GUN
    is_gunu = int(np.busday_count(kayit["transaction_date"], kayit["disclosed_date"]))
    return is_gunu > FORM4_IS_GUNU


def islem_hazirla(satir):
    """Veritabanı satırını şablonda kullanılacak hale getirir."""
    k = dict(satir)
    k["transaction_date"] = tarih_temizle(k["transaction_date"])
    k["disclosed_date"] = tarih_temizle(k["disclosed_date"])
    k["gecikme"] = (
        date.fromisoformat(k["disclosed_date"]) - date.fromisoformat(k["transaction_date"])
    ).days
    k["siyasetci"] = bool(k.get("chamber"))
    k["gec"] = gec_mi(k)
    k["tutar_tam"] = tam_tutar(k["amount_min"], k["amount_max"])
    k["tutar_kisa"] = kisa_aralik(k["amount_min"], k["amount_max"])
    k["islem_metni"] = "Alım" if k["action"] == "buy" else "Satım"
    k["rol"] = rol_metni(k)
    k["parti"] = parti_bilgisi(k.get("party"))
    k["yuklu"] = (
        k["siyasetci"] and k["action"] == "buy"
        and (k["amount_min"] or 0) >= YUKLU_ALIM_ALT_SINIR
    )
    if not k.get("person_slug"):
        k["person_slug"] = slugify(k["person"])
    return k


# ---------------------------------------------------------------------------
# ŞABLON SÜZGEÇLERİ
# ---------------------------------------------------------------------------

def sablonlara_kaydet(app):
    """Süzgeçleri ve ortak değişkenleri Flask uygulamasına tanıtır."""
    app.add_template_filter(sayi, "sayi")
    app.add_template_filter(kisa_tutar, "tutar")
    app.add_template_filter(uzun_tarih, "uzun_tarih")
    app.add_template_filter(kisa_tarih, "kisa_tarih")
    app.add_template_filter(yuzde, "yuzde")
    app.add_template_filter(fiyat, "fiyat")
    app.add_template_global(kisa_aralik, "aralik")

    @app.context_processor
    def ortak():
        return {
            "yasal_gun": STOCK_ACT_GUN,
            "form4_gun": FORM4_IS_GUNU,
            "partiler": PARTILER,
        }
