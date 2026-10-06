"""
Şirket adından borsa koduna (ticker) eşleme.

Mali durum bildirimlerinde hisseler kod yerine adla, çoğu zaman kısaltılmış
ya da boşluksuz yazılır: "SUNSTONE HOTEL INVS INC", "TESLAMOTORSINC".
Bu modül adları sadeleştirip SEC'in resmi şirket-kod listesiyle eşler.

Kurallar bilinçli olarak tutucudur: emin olunamayan ad eşlenmez. Yanlış bir
hisseyi göstermektense o kalemi dışarıda bırakmak tercih edilir.
"""

import difflib
import re
from collections import defaultdict

import requests

from piyasa.ayarlar import USER_AGENT

SEC_KODLAR = "https://www.sec.gov/files/company_tickers.json"
SEC_FON_KODLARI = "https://www.sec.gov/files/company_tickers_mf.json"

# Yatırım ortaklığı (unit/grantor trust) yapısındaki büyük borsa yatırım fonları
# SEC'in fon listesinde yer almıyor
EK_FON_KODLARI = {"SPY", "DIA", "GLD", "SLV", "IAU", "MDY", "GDX", "USO", "XLK", "XLF", "XLE", "XLV"}

# Ad karşılaştırmasında anlam taşımayan ekler
EKLER = {
    "INC", "CORP", "CORPORATION", "CO", "COMPANY", "COS", "LTD", "PLC", "LLC", "LP",
    "HOLDINGS", "HOLDING", "HLDGS", "HLDG", "GROUP", "GRP", "CLASS", "CL", "A", "B", "C",
    "NEW", "COM", "THE", "SA", "NV", "AG", "ADR", "SPONSORED", "ORD", "SHS", "SE", "DEL",
    "DE", "INCORPORATED", "LIMITED", "REIT",
}

# Bildirimlerde sık görülen kısaltmalar
KISALTMALAR = {
    "INTL": "INTERNATIONAL", "INDS": "INDUSTRIES", "MTRS": "MOTORS", "FINL": "FINANCIAL",
    "PETE": "PETROLEUM", "SVCS": "SERVICES", "TECHS": "TECHNOLOGIES", "TECH": "TECHNOLOGY",
    "PHARMA": "PHARMACEUTICALS", "MGMT": "MANAGEMENT", "SYS": "SYSTEMS", "LABS": "LABORATORIES",
    "INVS": "INVESTORS", "FMRS": "FARMERS", "MKT": "MARKET", "AMER": "AMERICA", "NATL": "NATIONAL",
    "BK": "BANK", "HLTH": "HEALTH", "ENTMT": "ENTERTAINMENT", "RES": "RESOURCES",
    "PPTYS": "PROPERTIES", "MFG": "MANUFACTURING", "PRODS": "PRODUCTS", "GEN": "GENERAL",
    "SOLUTNS": "SOLUTIONS", "COMMUN": "COMMUNICATIONS", "ELEC": "ELECTRIC",
}

# Boşluksuz yazılmış adların sonunda atılabilecek ekler (uzundan kısaya)
BITISIK_EKLER = ("CORPORATION", "INCORPORATED", "COMPANY", "HOLDINGS", "MOTORS",
                 "GROUP", "CORP", "INC", "PLC", "LTD", "CO")

# Tahvil, mevduat ve benzeri hisse olmayan kalemleri ele veren ifadeler
HISSE_DEGIL = re.compile(
    r"\bDUE\b|\bNOTES?\b|\bBND\b|\bBONDS?\b|%|\bREV\b|\bSENIOR\b|\bSR\b|\bDEBS?\b|\bTREAS|"
    r"\bMTN\b|\bSER\b|\d+\.\d{2,3}\b|\bCMNTY\b|\bAUTH\b|\bDEPOSIT\b|\bFDIC\b|\bMONEY MARKET\b|"
    r"\bCASH\b|\bSWEEP\b|\bCD\b|\bCERT\b|\bLLC\b|\bFINL\b|\bFINANCE\b|\bFUNDING\b|\bCAPITAL TR\b|"
    r"^\s*\*\*\*|\bMUNI|\bSCH DIST\b|\bCNTY\b|\bCITY OF\b|\bSTATE OF\b|\bPFD\b|\bPREFERRED\b|\bWTS?\b|\bWARRANTS?\b",
    re.IGNORECASE,
)


def anahtar(ad):
    ad = (ad or "").upper().replace("&", " AND ").replace("*", " ")
    kelimeler = [KISALTMALAR.get(k, k) for k in re.findall(r"[A-Z0-9]+", ad)]
    return "".join(k for k in kelimeler if k not in EKLER)


def bitisik_kok(ad):
    """'THEKROGERCO' -> 'KROGER', 'TESLAMOTORSINC' -> 'TESLA' (yalnızca tek kelimelik adlar)."""
    kok = re.sub(r"[^A-Z0-9]", "", (ad or "").upper())
    if kok.startswith("THE"):
        kok = kok[3:]
    degisti = True
    while degisti:
        degisti = False
        for ek in BITISIK_EKLER:
            if kok.endswith(ek) and len(kok) - len(ek) >= 4:
                kok = kok[: -len(ek)]
                degisti = True
                break
    return kok


class Eslestirici:
    def __init__(self, sec_listesi=None):
        if sec_listesi is None:
            cevap = requests.get(SEC_KODLAR, headers={"User-Agent": USER_AGENT}, timeout=60)
            cevap.raise_for_status()
            sec_listesi = cevap.json().values()
        self.kodlar = {}
        self.gecerli = set()
        self.adlar = {}          # kod → SEC'teki resmi şirket adı
        for k in sec_listesi:
            kod = k["ticker"].upper()
            self.gecerli.add(kod)
            self.adlar.setdefault(kod, k["title"])
            self.kodlar.setdefault(anahtar(k["title"]), kod)
        # Fonlar (ETF, yatırım fonu) yalnızca açıkça kodla yazıldıklarında eşlenir
        try:
            fonlar = requests.get(SEC_FON_KODLARI, headers={"User-Agent": USER_AGENT}, timeout=60).json()
            self.gecerli |= {satir[3].upper() for satir in fonlar["data"] if satir[3]}
        except Exception:
            pass
        self.gecerli |= EK_FON_KODLARI
        self.kova = defaultdict(list)
        for a in self.kodlar:
            self.kova[a[:4]].append(a)

    def resmi_ad(self, kod, yedek=""):
        """Kodun SEC'teki adı; fonlarda bildirimdeki ad."""
        return self.adlar.get(kod) or yedek

    def bul(self, ad):
        """(kod, yöntem) ya da (None, None)."""
        if not ad or ad.lstrip().startswith("***"):
            return None, None

        # "QQQ - Invesco QQQ Trust" gibi kodu açıkça yazılmış kalemler (tahvil
        # fonları da borsada işlem gördüğü için dahil)
        m = re.match(r"^\s*([A-Z]{1,5})\s*-\s*\S", ad)
        if m and m.group(1) in self.gecerli:
            return m.group(1), "kod"

        if HISSE_DEGIL.search(ad):
            return None, None

        a = anahtar(ad)
        if not a:
            return None, None
        if a in self.kodlar:
            return self.kodlar[a], "tam"
        if len(a) < 3:          # çok kısa adlar yalnızca tam eşleşmeyle
            return None, None

        # Boşluksuz yazılmış tek kelimelik ad
        if " " not in ad.strip():
            kok = bitisik_kok(ad)
            if kok in self.kodlar:
                return self.kodlar[kok], "bitisik"

        # Kısaltılmış (kesilmiş) ad: SEC adı bizimkiyle başlıyorsa ve tek adaysa.
        # Tersi (bizim ad daha uzun) bağlı ortaklık ya da tahvil ihraççısı olabilir; eşlenmez.
        adaylar = [x for x in self.kova.get(a[:4], []) if x.startswith(a)]
        if len(adaylar) == 1 and len(a) >= 8:
            return self.kodlar[adaylar[0]], "onek"

        yakin = difflib.get_close_matches(a, self.kova.get(a[:4], []), n=2, cutoff=0.92)
        if len(yakin) == 1:
            return self.kodlar[yakin[0]], "yakin"
        return None, None
