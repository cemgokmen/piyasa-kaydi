"""
Alan kuralları: yasal süreler, eşikler, partiler ve her sorguda tekrar eden
SQL koşulları. Veri toplama, analiz ve web katmanları bu tek kaynağı kullanır.
"""

# Yasal bildirim süreleri. Form 4: işlemden sonra 2 iş günü.
# STOCK Act: işlemden sonra en geç 45 gün.
FORM4_IS_GUNU = 2
STOCK_ACT_GUN = 45

# Kongre bildiriminde alt sınırı bu tutar ve üzerindeki alımlar "yüklü" sayılır
YUKLU_ALIM_ALT_SINIR = 50_001

# Getiri karşılaştırmasında piyasa ölçüsü (S&P 500 fonu)
ENDEKS = "SPY"

# Hiçbir adi hisse bu fiyatın üzerinde işlem görmez; daha yüksek bildirilen fiyat
# yazım hatasıdır. İstisna: Berkshire Hathaway A sınıfı gerçekten bu seviyede.
MUTLAK_FIYAT_TAVANI = 50_000
TAVAN_ISTISNALARI = {"BRK-A", "BRK.A", "BRKA"}


def fiyat_imkansiz_mi(ticker, fiyat):
    """Tek başına bakıldığında bile hatalı olduğu belli olan hisse fiyatı."""
    return bool(fiyat) and fiyat > MUTLAK_FIYAT_TAVANI and ticker not in TAVAN_ISTISNALARI


# Devlet sözleşmeleri (USAspending.gov) bu tarihten itibaren toplanır
IHALE_BASLANGIC = "2024-01-01"

# Borsa kodu olmayan ihraççılar Form 4'te bu yer tutucularla gelir
GECERSIZ_KODLAR = ("NONE", "N/A", "NA", "", "[NONE]")


def kod_duzelt(kod):
    """
    Bildirimlerdeki borsa kodunu tek biçime getirir:
    'vicr' -> 'VICR', 'LEN, LEN.B' -> 'LEN', 'CRDA CRDB' -> 'CRDA', 'ASX:LNW' -> 'LNW'.
    """
    kod = (kod or "").strip().upper()
    if ":" in kod:                       # borsa öneki
        kod = kod.split(":")[-1]
    parca = [p for p in kod.replace(",", " ").replace(";", " ").split() if p]
    return parca[0] if parca else kod

PARTILER = {
    "D": ("Demokrat", "dem"),
    "R": ("Cumhuriyetçi", "rep"),
    "I": ("Bağımsız", "ind"),
}


def parti_bilgisi(kod):
    """'D' -> {'kod': 'D', 'ad': 'Demokrat', 'sinif': 'dem'}; bilinmiyorsa None."""
    if not kod or kod not in PARTILER:
        return None
    ad, sinif = PARTILER[kod]
    return {"kod": kod, "ad": ad, "sinif": sinif}


def temiz(tablo=""):
    """Anormal fiyatlı (yazım hatası şüpheli) kayıtları dışlayan SQL koşulu."""
    on = f"{tablo}." if tablo else ""
    return f"({on}suspect IS NULL OR {on}suspect = 0)"


def gecerli_kod(tablo=""):
    """Borsa kodu yer tutucu olan kayıtları dışlayan SQL koşulu."""
    on = f"{tablo}." if tablo else ""
    kodlar = ", ".join(f"'{k}'" for k in GECERSIZ_KODLAR)
    return f"{on}ticker NOT IN ({kodlar})"


# Sık kullanılan, takma adsız biçimler
TEMIZ = temiz()
GECERLI_KOD = gecerli_kod()
