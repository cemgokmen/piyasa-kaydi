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


def yuzde(oran, isaretli=True, basamak=2):
    """0.0532 -> '+%5,32'; basamak=1 -> '+%5,3'"""
    if oran is None:
        return "—"
    isaret = ("+" if oran > 0 else "−" if oran < 0 else "") if isaretli else ""
    return f"{isaret}%{abs(oran) * 100:.{basamak}f}".replace(".", ",")


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
    r"american depositary shares?|ads|sponsored adr|adr|shares?|common)\b.*$",
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


# Markası büyük harfle yazılan şirketler (SEC adı düzeltilirken korunur)
BUYUK_HARFLI_MARKALAR = {"NVIDIA", "AECOM", "CACI", "ASML", "SAP", "USAA", "NXP", "ADT", "AGCO", "ANSYS", "EPAM",
                         "HEICO", "HNI", "IDEXX", "KLA", "MSCI", "NETGEAR", "PACCAR", "RTX", "SLM", "TEGNA", "TTM"}


def sirket_gorunen_ad(ad):
    """SEC'in büyük harfli adını okunur yapar: 'LOCKHEED MARTIN CORP' -> 'Lockheed Martin'.
    Kısaltmalar (3 harf ve altı, ör. 'IBM', 'AT&T') büyük kalır."""
    kisa = sirket_kisa_ad(ad or "")
    # Yalnızca adın tamamı büyük harfle yazılmışsa (SEC biçimi) düzeltilir;
    # 'NVIDIA Corporation' gibi markanın kendi yazımı korunur
    if not (ad or "").isupper() or len(kisa) <= 4:
        return kisa
    kelimeler = [AD_KISALTMALARI.get(k.strip(".,"), k) for k in kisa.split()]
    def duzelt(k):
        if not k.isupper() or not k.isalpha():
            return k
        if k in ("AND", "OF", "FOR", "THE"):
            return k.lower()
        if k in BUYUK_HARFLI_MARKALAR:
            return k
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


# ---------------------------------------------------------------------------
# YÖNETİCİ UNVANLARI (Form 4)
# ---------------------------------------------------------------------------

UNVANLAR = {
    "ceo": "CEO", "chief executive officer": "CEO",
    "cfo": "Finans direktörü (CFO)", "chief financial officer": "Finans direktörü (CFO)",
    "coo": "Operasyon direktörü (COO)", "chief operating officer": "Operasyon direktörü (COO)",
    "co-chief operating officer": "Eş operasyon direktörü",
    "cto": "Teknoloji direktörü (CTO)", "chief technology officer": "Teknoloji direktörü (CTO)",
    "clo": "Hukuk direktörü", "chief legal officer": "Hukuk direktörü", "general counsel": "Hukuk müşaviri",
    "chief accounting officer": "Muhasebe direktörü", "cao": "Muhasebe direktörü",
    "chief medical officer": "Tıp direktörü", "chief strategy officer": "Strateji direktörü",
    "chief commercial officer": "Ticari direktör", "chief revenue officer": "Gelir direktörü",
    "chief development officer": "Geliştirme direktörü", "chief business officer": "İş geliştirme direktörü",
    "chief scientific officer": "Bilim direktörü", "chief marketing officer": "Pazarlama direktörü",
    "chief people officer": "İnsan kaynakları direktörü", "chief human resources officer": "İnsan kaynakları direktörü",
    "chief information officer": "Bilgi işlem direktörü", "chief product officer": "Ürün direktörü",
    "chief investment officer": "Yatırım direktörü", "chief risk officer": "Risk direktörü",
    "chief credit officer": "Kredi direktörü", "chief administrative officer": "İdari işler direktörü",
    "chairman": "Yönetim kurulu başkanı", "chairperson": "Yönetim kurulu başkanı", "chair": "Yönetim kurulu başkanı",
    "board chair": "Yönetim kurulu başkanı", "chairman of the board": "Yönetim kurulu başkanı",
    "co-chair": "Yönetim kurulu eş başkanı", "board co-chair": "Yönetim kurulu eş başkanı",
    "executive chairman": "İcracı yönetim kurulu başkanı", "exec. chairman": "İcracı yönetim kurulu başkanı",
    "vice chairman": "Yönetim kurulu başkan yardımcısı", "lead independent director": "Bağımsız baş üye",
    "president": "Başkan", "pres.": "Başkan", "pres": "Başkan",
    "evp": "Kıdemli başkan yardımcısı", "executive vice president": "Kıdemli başkan yardımcısı",
    "svp": "Kıdemli başkan yardımcısı", "senior vice president": "Kıdemli başkan yardımcısı",
    "vp": "Başkan yardımcısı", "vice president": "Başkan yardımcısı",
    "secretary": "Sekreter", "corporate secretary": "Şirket sekreteri", "treasurer": "Hazine sorumlusu",
    "director": "Yönetim kurulu üyesi", "see remarks": "Yönetici", "other": "Yönetici",
    "chief exec. officer": "CEO", "chief executive": "CEO", "founder": "Kurucu", "co-founder": "Kurucu ortak",
    "co-ceo": "Eş CEO", "co-chief executive officer": "Eş CEO", "interim ceo": "Geçici CEO", "interim cfo": "Geçici finans direktörü",
    "executive chair": "İcracı yönetim kurulu başkanı", "executive chairman of board": "İcracı yönetim kurulu başkanı",
    "executive chairman of the board": "İcracı yönetim kurulu başkanı", "co-chairman": "Yönetim kurulu eş başkanı",
    "vice chair": "Yönetim kurulu başkan yardımcısı", "cmo": "Pazarlama direktörü", "cro": "Gelir direktörü",
    "cso": "Strateji direktörü", "cio": "Bilgi işlem direktörü", "pao": "Muhasebe müdürü", "controller": "Muhasebe müdürü",
    "principal accounting officer": "Muhasebe müdürü", "chief of staff": "Genel koordinatör",
    "10% owner": "%10 üzeri ortak", "managing director": "Genel müdür", "general manager": "Genel müdür",
    "executive officer": "Üst düzey yönetici",
    # Form 4 dışından gelen Türkçe değerler olduğu gibi kalır
    "yönetim kurulu üyesi": "Yönetim kurulu üyesi", "bildirim yükümlüsü": "Bildirim yükümlüsü",
    "%10 üzeri ortak": "%10 üzeri ortak", "yönetici": "Yönetici",
}

# Başı tanıdık, devamı bölüm adı olan unvanlar: 'SVP Information Technology', 'President Generac Home'
UNVAN_ONEKLERI = (
    (r"(co-)?chief executive|(co-)?ceo\b", "CEO"),
    (r"(senior|sr\.?|exec(utive)?\.?|s?evp|svp|senior executive|corp(orate)?)[\s-]*(vice[\s-]president|vp)|s?evp\b|svp\b",
     "Kıdemli başkan yardımcısı"),
    (r"(vice[\s-]president|vp)\b", "Başkan yardımcısı"),
    (r"(group |segment |division )?president|.*\bpresident\b", "Bölüm başkanı"),
    (r"chief financial|cfo\b", "Finans direktörü (CFO)"),
    (r".*\bceo\b", "CEO"),
    (r"chief .*officer|chief .*off\b|chief\b", "Üst düzey yönetici"),
    (r".*\bdirector\b|md\b|.*\bhead of\b|.*\blead\b", "Üst düzey yönetici"),
)


def unvan(metin):
    """'PRESIDENT AND CEO' -> 'Başkan, CEO'; 'Chairperson & CEO' -> 'Yönetim kurulu başkanı, CEO'.
    Tanınmayan parçalar atılır; hiçbiri tanınmazsa 'Üst düzey yönetici' olur."""
    if not metin:
        return metin
    parcalar = [p.strip(" .") for p in re.split(r"\s*(?:&|\band\b|,|/|;)\s*", metin, flags=re.IGNORECASE)]
    sonuc, bilinmeyen = [], []
    for p in parcalar:
        p = p.strip(" *-")
        if not p:
            continue
        karsilik = UNVANLAR.get(p.lower()) or UNVANLAR.get(p.lower() + ".")
        if not karsilik:
            karsilik = next((k for desen, k in UNVAN_ONEKLERI if re.match(desen, p, re.IGNORECASE)), None)
        if not karsilik:
            bilinmeyen.append(p)
        elif karsilik not in sonuc:
            sonuc.append(karsilik)
    # 'CEO, Data' gibi: tanınan parça yeterli, bölüm adı İngilizce kalmasın
    if len(sonuc) > 1 and "Üst düzey yönetici" in sonuc:
        sonuc.remove("Üst düzey yönetici")
    if sonuc:
        return ", ".join(sonuc)
    return "Üst düzey yönetici" if bilinmeyen else metin


# ---------------------------------------------------------------------------
# KİŞİ ADLARI (Form 4)
# ---------------------------------------------------------------------------

KURUM_KELIMELERI = {
    "LLC", "LP", "L.P.", "LLP", "LLLP", "INC", "INC.", "LTD", "LTD.", "LIMITED", "FUND", "FUNDS", "TRUST",
    "CAPITAL", "PARTNERS", "MANAGEMENT", "HOLDINGS", "HOLDING", "GROUP", "ADVISORS", "ADVISERS", "CORP",
    "CORP.", "CORPORATION", "CO", "CO.", "COMPANY", "BANK", "FOUNDATION", "INVESTMENT", "INVESTMENTS",
    "VENTURES", "ASSOCIATES", "PLC", "N.V.", "S.A.", "AG", "GMBH", "PARTNERSHIP", "ESTATE", "SECURITIES",
    "FINANCIAL", "OPPORTUNITY", "OPPORTUNITIES", "MASTER", "OFFSHORE", "ENTERPRISES", "AB", "SA", "NV",
}
KISI_EKLERI = {"JR", "JR.", "SR", "SR.", "II", "III", "IV", "V", "MD", "PHD", "CPA"}
KISALTMA_KURUM = {"Llc": "LLC", "Lp": "LP", "L.p.": "L.P.", "Llp": "LLP", "Lllp": "LLLP", "Plc": "PLC", "Ag": "AG"}


def _buyuk_harf(kelime):
    """'mcbee' -> 'McBee', 'le-quoc' -> 'Le-Quoc', "o'neil" -> "O'Neil" """
    parcalar = []
    for p in re.split(r"([-'])", kelime.lower()):
        p = p[:1].upper() + p[1:]
        if p.startswith("Mc") and len(p) > 2:
            p = "Mc" + p[2].upper() + p[3:]
        parcalar.append(p)
    return "".join(parcalar)


def kisi_adi(ham):
    """
    SEC'in 'SOYAD AD ORTAAD' biçimini doğal sıraya çevirir:
    'KURTZ GEORGE' -> 'George Kurtz', 'LIGHTFOOT ROBERT M JR' -> 'Robert M Lightfoot Jr'.
    Şirket ve fon adları ('DST GLOBAL ADVISORS LTD') sırası değiştirilmeden yazılır.
    """
    kelimeler = (ham or "").replace(",", " ").split()
    if not kelimeler:
        return ""
    if any(k.upper() in KURUM_KELIMELERI for k in kelimeler) or len(kelimeler) == 1:
        return " ".join(KISALTMA_KURUM.get(_buyuk_harf(k), _buyuk_harf(k)) for k in kelimeler)
    ekler = []
    while len(kelimeler) > 2 and kelimeler[-1].upper() in KISI_EKLERI:
        ekler.insert(0, kelimeler.pop())
    soyad, adlar = kelimeler[0], kelimeler[1:]
    sira = [*adlar, soyad, *ekler]
    return " ".join(k if k.upper() in ("II", "III", "IV") else _buyuk_harf(k) for k in sira)
