"""
X (Twitter) API v2 ile gönderi: POST https://api.x.com/2/tweets, OAuth 1.0a kullanıcı imzası.

Anahtarlar data/x.env dosyasındadır (depoya girmez):
    X_API_KEY=...
    X_API_SECRET=...
    X_ACCESS_TOKEN=...
    X_ACCESS_SECRET=...
"""

import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import quote

import requests

from piyasa.ayarlar import VERI_DIZINI

ADRES = "https://api.x.com/2/tweets"
ANAHTAR_DOSYASI = VERI_DIZINI / "x.env"
GEREKLI = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")


def anahtarlar():
    """{'X_API_KEY': ...}; dosya yoksa ya da eksikse None."""
    try:
        satirlar = ANAHTAR_DOSYASI.read_text().splitlines()
    except OSError:
        return None
    degerler = {}
    for s in satirlar:
        if "=" in s and not s.lstrip().startswith("#"):
            k, v = s.split("=", 1)
            degerler[k.strip()] = v.strip().strip('"').strip("'")
    return degerler if all(degerler.get(k) for k in GEREKLI) else None


def _yuzde_kodla(metin):
    return quote(str(metin), safe="~-._")


def oauth_basligi(yontem, adres, a, zaman=None, rastgele=None):
    """OAuth 1.0a (HMAC-SHA1) yetki başlığı. JSON gövdeli isteklerde gövde imzaya girmez."""
    parametreler = {
        "oauth_consumer_key": a["X_API_KEY"],
        "oauth_nonce": rastgele or secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(zaman or int(time.time())),
        "oauth_token": a["X_ACCESS_TOKEN"],
        "oauth_version": "1.0",
    }
    dizi = "&".join(f"{_yuzde_kodla(k)}={_yuzde_kodla(v)}" for k, v in sorted(parametreler.items()))
    temel = "&".join((yontem.upper(), _yuzde_kodla(adres), _yuzde_kodla(dizi)))
    anahtar = f"{_yuzde_kodla(a['X_API_SECRET'])}&{_yuzde_kodla(a['X_ACCESS_SECRET'])}"
    imza = base64.b64encode(hmac.new(anahtar.encode(), temel.encode(), hashlib.sha1).digest()).decode()
    parametreler["oauth_signature"] = imza
    return "OAuth " + ", ".join(f'{_yuzde_kodla(k)}="{_yuzde_kodla(v)}"' for k, v in sorted(parametreler.items()))


def gonder(metin, a=None):
    """Gönderiyi paylaşır; gönderinin numarasını döndürür. Hata olursa açıklamalı RuntimeError."""
    a = a or anahtarlar()
    if not a:
        raise RuntimeError(f"X anahtarları bulunamadı: {ANAHTAR_DOSYASI}")
    cevap = requests.post(ADRES, json={"text": metin}, timeout=30,
                          headers={"Authorization": oauth_basligi("POST", ADRES, a)})
    if cevap.status_code >= 400:
        raise RuntimeError(f"X {cevap.status_code}: {cevap.text[:300]}")
    return cevap.json()["data"]["id"]
