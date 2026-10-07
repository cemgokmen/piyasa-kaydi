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

# Devlet sözleşmeleri (USAspending.gov) bu tarihten itibaren toplanır
IHALE_BASLANGIC = "2024-01-01"

# Borsa kodu olmayan ihraççılar Form 4'te bu yer tutucularla gelir
GECERSIZ_KODLAR = ("NONE", "N/A", "NA", "")

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
