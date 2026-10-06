"""
Projenin ortak ayarları.
"""

import os
from pathlib import Path

# Proje kökü ve veri klasörü
KOK = Path(__file__).resolve().parent.parent
VERI_DIZINI = KOK / "data"
VERITABANI = VERI_DIZINI / "kayitlar.db"
FON_LISTESI = VERI_DIZINI / "fonlar.json"

# SEC, kendisine istek atan herkesin kim olduğunu bildirmesini istiyor.
# Kendi adını ve e-posta adresini SEC_USER_AGENT ortam değişkeniyle ver:
#     export SEC_USER_AGENT="PiyasaKaydi ad@ornek.com"
USER_AGENT = os.environ.get("SEC_USER_AGENT", "PiyasaKaydi cemgokmen101@gmail.com")
