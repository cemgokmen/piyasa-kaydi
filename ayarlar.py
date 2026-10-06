"""
Projenin ortak ayarları.
"""

import os

# SEC, kendisine istek atan herkesin kim olduğunu bildirmesini istiyor.
# Kendi adını ve e-posta adresini SEC_USER_AGENT ortam değişkeniyle ver:
#     export SEC_USER_AGENT="PiyasaKaydi ad@ornek.com"
USER_AGENT = os.environ.get("SEC_USER_AGENT", "PiyasaKaydi cemgokmen101@gmail.com")
