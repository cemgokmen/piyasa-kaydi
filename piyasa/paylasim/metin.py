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


# ---------------------------------------------------------------------------
# Paylaşım kartları (görsel): elle paylaşım için 1200×675 kartın alanları
# ---------------------------------------------------------------------------

YESIL, KIRMIZI, MAVI = "#22C55E", "#EF4444", "#3B82F6"


def _uzun_gun(iso):
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {AYLAR_UZUN[d.month - 1]} {d.year}"


def kap_karti(x):
    alim = x["islem"] == "buy"
    sirket_mi = x["kisi_turu"] == "sirket" or bool(SIRKET_ADI.search(x["kisi"] or ""))
    kisi = x["kisi_kisa"] if sirket_mi else x["kisi"]
    rol = "Ortak" if sirket_mi or not x.get("gorev") else x["gorev"]
    ayrinti = []
    if x.get("nominal") and x.get("fiyat"):
        ayrinti.append(f"{adet(x['nominal'])} adet · ort. {fiyat_metni(x['fiyat'], 'TL')}")
    if x.get("oran_sonra") is not None:
        ayrinti.append(f"işlem sonrası pay %{ondalik(x['oran_sonra'])}")
    return {"etiket": f"KAP · İÇERİDEN {'ALIM' if alim else 'SATIŞ'}", "renk": YESIL if alim else KIRMIZI,
            "kod": x["kod"], "sirket": x["sirket"], "tutar": tutar(x["tutar"]), "kisi": f"{kisi} · {rol}",
            "ayrinti": " · ".join(ayrinti), "tarih": _uzun_gun(x["islem_tarihi"]),
            "adres": f"{SITE}/bist/{x['kod']}", "kaynak": "Kaynak: KAP", "dosya": f"{x['kod']}-{x['islem_tarihi']}",
            "neden": ("Yöneticinin ya da büyük ortağın kendi şirketinden hisse alması güven işareti sayılır." if alim else
                      "İçeriden satışlar kişisel nedenlerle de yapılabilir; tek başına olumsuz işaret değildir.")}


def geri_karti(x):
    return {"etiket": "KAP · PAY GERİ ALIMI", "renk": MAVI, "kod": x["kod"], "sirket": x["sirket"],
            "tutar": tutar(x["tutar"]), "kisi": "Şirket kendi payını borsadan geri aldı",
            "ayrinti": f"Son 90 günde toplam {tutar(x['toplam_90'])}" if x.get("toplam_90") else "",
            "tarih": _uzun_gun(x["son_tarih"]), "adres": f"{SITE}/bist/{x['kod']}", "kaynak": "Kaynak: KAP",
            "dosya": f"{x['kod']}-geri-alim-{x['son_tarih']}",
            "neden": "Şirketin kendi hissesini alması, hissenin ucuz olduğunu düşündüğünü gösterir."}


def form4_karti(x):
    alim = x["action"] == "buy"
    rol = x["rol"] if x["rol"] not in ("Bildirim yükümlüsü", "Üst düzey yönetici", "") else "Yönetici"
    return {"etiket": f"ABD · YÖNETİCİ {'ALIMI' if alim else 'SATIŞI'}", "renk": YESIL if alim else KIRMIZI,
            "kod": x["ticker"], "sirket": x["sirket"], "tutar": tutar(x["tutar"], "dolar"), "kisi": f"{x['kisi']} · {rol}",
            "ayrinti": f"{adet(x['adet'])} adet · ort. {fiyat_metni(x['fiyat'], 'dolar')}" if x.get("adet") and x.get("fiyat") else "",
            "tarih": _uzun_gun(x["disclosed_date"]), "adres": f"{SITE}/hisse/{x['ticker']}", "kaynak": "Kaynak: SEC Form 4",
            "dosya": f"{x['ticker']}-{x['disclosed_date']}",
            "neden": ("ABD'de yöneticilerin kendi parasıyla hisse alması şirkete güvenin işareti sayılır." if alim else
                      "Büyük yönetici satışları piyasada yakından izlenir.")}


def kongre_karti(x):
    alim = x["action"] == "buy"
    parti = {"D": "Demokrat", "R": "Cumhuriyetçi"}.get(x.get("parti") or "", "")
    unvan_ = "Senatör" if "senato" in (x.get("meclis") or "").lower() else "Temsilciler Meclisi"
    aralik = f"{tutar(x['alt'], '').strip()} – {tutar(x['ust'], 'dolar')}" if x["alt"] != x["ust"] else tutar(x["ust"], "dolar")
    return {"etiket": f"ABD KONGRESİ · {'ALIM' if alim else 'SATIŞ'}", "renk": YESIL if alim else KIRMIZI,
            "kod": x["ticker"], "sirket": x["sirket"], "tutar": aralik,
            "kisi": " · ".join(p for p in (x["kisi"], unvan_, parti) if p),
            "ayrinti": f"İşlem tarihi {_uzun_gun(x['islem_tarihi'])}" if x.get("islem_tarihi") else "",
            "tarih": _uzun_gun(x["disclosed_date"]), "adres": f"{SITE}/hisse/{x['ticker']}",
            "kaynak": "Kaynak: Kongre bildirimi", "dosya": f"{x['ticker']}-kongre-{x['disclosed_date']}",
            "neden": "ABD'li siyasetçiler hisse işlemlerini yasa gereği 45 gün içinde açıklamak zorunda."}


# ---------------------------------------------------------------------------
# Finans haberleri: kaynağı belirtilen kısa haber; kartta konu çizimi ve canlı fiyat
# ---------------------------------------------------------------------------

# Konu: (kart rengi, etiket, X etiketleri, "neden önemli" — finans bilmeyen için tek cümle, ilgili gösterge)
HABER_KONULARI = {
    "faiz": ("#8B5CF6", "FAİZ VE ENFLASYON", "#faiz #enflasyon",
             "Faiz ve enflasyon; kredi, mevduat ve döviz kurlarını doğrudan etkiler.", "TRY=X"),
    "doviz": ("#EAB308", "DÖVİZ VE ALTIN", "#dolar #altın",
              "Kurdaki ve altındaki hareketler birikimlerin değerini doğrudan etkiler.", "GRAM"),
    "borsa": ("#22C55E", "BORSA", "#borsa #BIST100",
              "Hisse fiyatları şirketlerin kazancına ve yatırımcı beklentisine göre değişir.", "XU100.IS"),
    "enerji": ("#F97316", "ENERJİ", "#petrol #enerji",
               "Enerji fiyatları akaryakıttan faturalara kadar günlük harcamalara yansır.", "BZ=F"),
    "kripto": ("#F59E0B", "KRİPTO", "#bitcoin #kripto",
               "Kripto paralar çok oynaktır; fiyatları kısa sürede sert değişebilir.", "BTC-USD"),
    "dunya": ("#3B82F6", "DÜNYA EKONOMİSİ", "#ekonomi",
              "Büyük ekonomilerdeki gelişmeler Türkiye piyasalarını da etkiler.", "^GSPC"),
    "ekonomi": ("#14B8A6", "EKONOMİ", "#ekonomi",
                "Ekonomideki gelişmeler gelirlere, fiyatlara ve piyasalara yansır.", "TRY=X"),
}


def _gosterge_kodu(x):
    """Haberin konusuna ve başlığına göre kartta gösterilecek canlı fiyat."""
    b = x["baslik"].lower()
    if x["konu"] == "doviz":
        if "gümüş" in b:
            return "SI=F"
        if "altın" in b or "ons" in b:
            return "GRAM"
        if "euro" in b or "avro" in b:
            return "EURTRY=X"
        return "TRY=X"
    if x["konu"] == "enerji":
        # Brent fiyatı yalnızca petrol ve akaryakıt haberlerinde anlamlı
        return "BZ=F" if any(k in b for k in ("petrol", "brent", "akaryakıt", "benzin", "motorin", "opec")) else None
    return HABER_KONULARI.get(x["konu"], HABER_KONULARI["ekonomi"])[4]


def haber(x):
    """X metni: başlık, özet, kaynak. Haberin kendisi kaynağındadır; biz kısa aktarırız."""
    renk, etiket, etiketler, neden, _ = HABER_KONULARI.get(x["konu"], HABER_KONULARI["ekonomi"])
    govde = [x["baslik"]]
    if x.get("ozet") and x["ozet"].lower()[:60] != x["baslik"].lower()[:60]:
        govde.append(x["ozet"])
    return "\n\n".join(govde) + f"\n\nKaynak: {x['kaynak']} · {etiketler}\n{SITE}/gunluk-ozet"


def satirlara_bol(metin, en_cok_karakter, en_cok_satir):
    """Kelimeleri bölmeden satırlara ayırır; sığmazsa son satır '…' ile biter."""
    import textwrap
    satirlar = textwrap.wrap(metin, en_cok_karakter)
    if len(satirlar) > en_cok_satir:
        satirlar = satirlar[:en_cok_satir]
        satirlar[-1] = satirlar[-1].rstrip(" ,.;:") + "…"
    return satirlar


def haber_karti(x, gosterge=None):
    renk, etiket, _, neden, _ = HABER_KONULARI.get(x["konu"], HABER_KONULARI["ekonomi"])
    # Başlık en çok 3 satır: uzun başlıkta yazı küçülür
    boyut, satirlar = 38, []
    for secenek, karakter in ((54, 24), (48, 27), (42, 31), (38, 34)):
        boyut, satirlar = secenek, satirlara_bol(x["baslik"], karakter, 3)
        if not satirlar[-1].endswith("…"):
            break
    ozet = satirlara_bol(x.get("ozet") or "", 52, 2) if x.get("ozet") else []
    yayin = x.get("yayin_yerel") or ""
    return {"tip": "haber", "konu": x["konu"], "renk": renk, "etiket": etiket, "baslik_satirlari": satirlar,
            "baslik_boyut": boyut, "ozet_satirlari": ozet, "neden": neden, "gosterge": gosterge,
            "kaynak": f"Kaynak: {x['kaynak']}", "tarih": yayin, "adres": f"{SITE}/gunluk-ozet",
            "dosya": f"haber-{x['konu']}-{(x.get('yayin') or '')[:16].replace(':', '')}"}
