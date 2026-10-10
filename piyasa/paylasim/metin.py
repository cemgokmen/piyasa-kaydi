"""
Gönderi metinleri: bir haber ajansının kısa bülten dili. Olguyu söyler (kim, hangi şirket, ne kadar,
ne zaman, kaynak); yorum, emoji ya da "al/sat" yönlendirmesi içermez.
"""

import re
from datetime import date

from piyasa.bicim import AYLAR_UZUN, ek

SITE = "piyasakaydi.com"


def tutar(n, birim="TL"):
    """30_400_000 → '30,4 milyon TL'; 1_250_000_000 → '1,25 milyar TL'; 850_000 → '850 bin TL'."""
    if n >= 1e9:
        sayi, ek_ = f"{n / 1e9:.2f}".rstrip("0").rstrip("."), "milyar"
    elif n >= 1e6:
        sayi, ek_ = f"{n / 1e6:.1f}".rstrip("0").rstrip("."), "milyon"
    else:
        sayi, ek_ = f"{round(n / 1e3):.0f}", "bin"
    return f"{sayi.replace('.', ',')} {ek_} {birim}"


def gun(iso):
    """'2026-10-08' → '8 Ekim' (yıl bu yıl değilse yılıyla)."""
    d = date.fromisoformat(iso[:10])
    metin = f"{d.day} {AYLAR_UZUN[d.month - 1]}"
    return metin if d.year == date.today().year else f"{metin} {d.year}"


def adet(n):
    """14_160_000 → '14,16 milyon'; 180_000 → '180.000'"""
    if n >= 1e6:
        return f"{n / 1e6:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " milyon"
    return f"{n:,.0f}".replace(",", ".")


def ondalik(n, basamak=2):
    """1234.5 → '1.234,50'"""
    return f"{n:,.{basamak}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fiyat_metni(n, birim):
    return f"{ondalik(n)} {birim}"


# ---------------------------------------------------------------------------
# Borsa İstanbul (KAP)
# ---------------------------------------------------------------------------

SIRKET_ADI = re.compile(r"\b(A\.?\s?Ş|ANON[İI]M|HOLD[İI]NG|LTD|L[İI]M[İI]TED|ŞİRKETİ|ŞTİ|YATIRIM ORTAKLI)", re.IGNORECASE)


def _cumle(metin):
    """İlk harfi büyütür, gerisine dokunmaz ('tl' gibi küçültmeler olmasın)."""
    return metin[:1].upper() + metin[1:]


def kap_islem(x):
    """KAP'a bildirilen içeriden alım ya da satım."""
    fiil = "alım" if x["islem"] == "buy" else "satış"
    sirket_mi = x["kisi_turu"] == "sirket" or bool(SIRKET_ADI.search(x["kisi"] or ""))
    if sirket_mi:
        kim = x["sirket"] if x["kisi"] == x["sirket"] else f"{x['sirket']} ortağı {x['kisi_kisa']}"
    elif x.get("gorev"):
        kim = f"{x['sirket']} {x['gorev'].lower()} {x['kisi']}"
    else:
        kim = f"{x['sirket']} ortağı {x['kisi']}"
    ilk = f"{kim}, {ek(gun(x['islem_tarihi']), 'de')} şirket paylarında {tutar(x['tutar'])} tutarında {fiil} yaptı."
    ayrinti = []
    if x.get("nominal") and x.get("fiyat"):
        ayrinti.append(f"{adet(x['nominal'])} adet pay, ortalama {fiyat_metni(x['fiyat'], 'TL')}")
    if x.get("oran_sonra") is not None:
        ayrinti.append(f"işlem sonrası payı %{ondalik(x['oran_sonra'])}")
    govde = [ilk] + ([_cumle(" · ".join(ayrinti)) + "."] if ayrinti else [])
    return "\n\n".join(govde) + f"\n\nKaynak: KAP · #{x['kod']} #BIST\n{SITE}/bist/{x['kod']}"


def geri_alim(x):
    """Şirketin kendi paylarını geri alması."""
    ilk = (f"{x['sirket']}, {ek(gun(x['son_tarih']), 'de')} borsadan {tutar(x['tutar'])} tutarında "
           f"kendi payını geri aldı.")
    ikinci = f"Son 90 günde toplam geri alım: {tutar(x['toplam_90'])}." if x.get("toplam_90") else ""
    return "\n\n".join(p for p in (ilk, ikinci) if p) + f"\n\nKaynak: KAP · #{x['kod']} #BIST\n{SITE}/bist/{x['kod']}"


# ---------------------------------------------------------------------------
# ABD (SEC Form 4, Kongre)
# ---------------------------------------------------------------------------

def form4(x):
    """ABD'de şirket yöneticisinin kendi şirketinin hissesinde alım ya da satımı."""
    fiil = "alım" if x["action"] == "buy" else "satış"
    rol = x["rol"]
    if rol in ("CEO", "CFO"):
        kim = f"{ek(x['sirket'], 'in')} {ek(rol, 'si')} {x['kisi']}"
    elif rol == "%10 üzeri ortak":
        kim = f"{x['sirket']} hisselerinin %10'undan fazlasına sahip {x['kisi']}"
    elif rol and rol not in ("Bildirim yükümlüsü", "Üst düzey yönetici"):
        kim = f"{x['sirket']} {rol.lower()} {x['kisi']}"
    else:
        kim = f"{x['sirket']} yöneticilerinden {x['kisi']}"
    ilk = f"{kim}, şirket hisselerinde {tutar(x['tutar'], 'dolar')}lık {fiil} yaptı."
    ayrinti = f"{adet(x['adet'])} adet hisse, ortalama {fiyat_metni(x['fiyat'], 'dolar')}." if x.get("adet") and x.get("fiyat") else ""
    return "\n\n".join(p for p in (ilk, ayrinti) if p) + \
        f"\n\nKaynak: SEC Form 4 · ${x['ticker']}\n{SITE}/hisse/{x['ticker']}"


def kongre(x):
    """ABD Kongresi üyesinin hisse işlemi (tutar aralık olarak bildirilir)."""
    fiil = "alım" if x["action"] == "buy" else "satış"
    parti = {"D": "Demokrat", "R": "Cumhuriyetçi"}.get(x.get("parti") or "", "")
    eyalet = (x.get("eyalet") or "")[:2]
    kimlik = ", ".join(p for p in (parti, eyalet) if p)
    unvan_ = "Senatör" if "senato" in (x.get("meclis") or "").lower() else "ABD Temsilciler Meclisi üyesi"
    aralik = f"{tutar(x['alt'], '').strip()} – {tutar(x['ust'], 'dolar')}" if x["alt"] != x["ust"] else tutar(x["ust"], "dolar")
    ilk = (f"{unvan_} {x['kisi']}{f' ({kimlik})' if kimlik else ''}, {x['sirket']} hissesinde "
           f"{aralik} arasında {fiil} bildirdi.")
    ikinci = f"İşlem tarihi: {gun(x['islem_tarihi'])}." if x.get("islem_tarihi") else ""
    return "\n\n".join(p for p in (ilk, ikinci) if p) + \
        f"\n\nKaynak: Kongre işlem bildirimi · ${x['ticker']}\n{SITE}/hisse/{x['ticker']}"
