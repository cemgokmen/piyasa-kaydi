"""
İngilizceden Türkçeye ücretsiz makine çevirisi ve çeviri sonrası düzeltmeler
(şirket tanımları, faaliyet alanları, İngilizce haber başlıkları).

  cevir(metin)                    Google'ın tarayıcı eklentisi ucu; olmazsa MyMemory
  adi_koruyarak_cevir(metin, ad)  şirket adı çevrilmesin ('Applied Materials')
  turkcelestir(metin)             karışık fiil kipleri, 'ABD', 'bölüm', şapkasız harfler
  baslik_duzelt(metin)            'Otomobil Üreticileri' -> 'Otomobil üreticileri'
"""

import re

import requests

from piyasa.bicim import tr_kucuk

# Ücretsiz, anahtarsız çeviri uçları: önce Google'ın tarayıcı eklentisi ucu,
# olmazsa MyMemory (günlük kotalı)
GOOGLE_CEVIRI = "https://clients5.google.com/translate_a/t"
MYMEMORY = "https://api.mymemory.translated.net/get"


# Çeviri aynı metinde '-yor' ile geniş zamanı karıştırıyor; şirket tanımında
# geniş zaman doğal olandır
_GENIS_ZAMAN = {
    "tasarlıyor": "tasarlar", "üretiyor": "üretir", "pazarlıyor": "pazarlar", "satıyor": "satar",
    "sunuyor": "sunar", "sağlıyor": "sağlar", "geliştiriyor": "geliştirir", "işletiyor": "işletir",
    "gösteriyor": "gösterir", "dağıtıyor": "dağıtır", "yapıyor": "yapar", "ediyor": "eder",
    "veriyor": "verir", "kiralıyor": "kiralar", "araştırıyor": "araştırır", "keşfediyor": "keşfeder",
    "ticarileştiriyor": "ticarileştirir", "yönetiyor": "yönetir", "tedarik ediyor": "tedarik eder",
    "faaliyet gösteriyor": "faaliyet gösterir", "işliyor": "işler", "üstleniyor": "üstlenir",
    "lisanslıyor": "lisanslar", "inşa ediyor": "inşa eder", "çıkarıyor": "çıkarır",
    "taşıyor": "taşır", "yatırım yapıyor": "yatırım yapar", "kuruyor": "kurar", "tutuyor": "tutar",
}
_YOR = re.compile(r"\b(" + "|".join(sorted((k for k in _GENIS_ZAMAN if k.endswith("yor")), key=len, reverse=True)) + r")\b")
# Ekleriyle birlikte doğrudan karşılıkları (ek uyumu bozulmasın diye tek tek)
_KELIMELER = {
    "Amerika Birleşik Devletleri": "ABD", "Amerika Birleşik Devletleri'nde": "ABD'de",
    "Amerika Birleşik Devletleri'ndeki": "ABD'deki", "Amerika Birleşik Devletleri'nin": "ABD'nin",
    "segment": "bölüm", "segmenti": "bölümü", "segmentte": "bölümde", "segmentler": "bölümler",
    "segmentleri": "bölümleri", "segmentinde": "bölümünde", "segmentlerinde": "bölümlerinde",
    "segmentlerde": "bölümlerde", "segmentlerinden": "bölümlerinden",
}
_KELIME = re.compile(r"(?<!\w)(" + "|".join(re.escape(k) for k in sorted(_KELIMELER, key=len, reverse=True)) + r")(?!\w)")


# Çeviri servisi şirket adlarını da çevirebiliyor ("Applied Materials" ->
# "Uygulamalı Malzemeler"); ad çeviri sırasında bu yer tutucuyla korunur
_AD_YERI = "XQZ"


def adi_koruyarak_cevir(metin, ad):
    if not ad or ad not in metin or _AD_YERI in metin:
        return cevir(metin)
    sonuc = cevir(metin.replace(ad, _AD_YERI))
    return sonuc.replace(_AD_YERI, ad) if sonuc and _AD_YERI in sonuc else cevir(metin)


# Şapkalı harfler (a, i, u üstünde) kullanılmaz; çeviriden gelse de sade harfe çevrilir
_SAPKASIZ = str.maketrans({"\u00e2": "a", "\u00ee": "i", "\u00fb": "u", "\u00c2": "A", "\u00ce": "\u0130", "\u00db": "U"})


def turkcelestir(metin):
    metin = (metin or "").translate(_SAPKASIZ)
    metin = _YOR.sub(lambda m: _GENIS_ZAMAN[m.group(1)], metin or "")
    metin = _KELIME.sub(lambda m: _KELIMELER[m.group(0)], metin)
    metin = re.sub(r"\s+([,.;])", r"\1", metin)
    return metin.strip()


def baslik_duzelt(metin):
    """'Otomobil Üreticileri' -> 'Otomobil üreticileri' (kısaltmalar korunur)."""
    if not metin:
        return metin
    kelimeler = metin.split()
    return " ".join([kelimeler[0]] + [k if k.isupper() and len(k) > 1 else tr_kucuk(k)
                                      for k in kelimeler[1:]])


def _google(metin):
    cevap = requests.get(GOOGLE_CEVIRI, params={"client": "dict-chrome-ex", "sl": "en", "tl": "tr", "q": metin},
                         timeout=20)
    cevap.raise_for_status()
    ilk = cevap.json()[0]
    return ilk[0] if isinstance(ilk, list) else ilk      # kaynak dil otomatikse [metin, dil]


def _mymemory(metin):
    cevap = requests.get(MYMEMORY, params={"q": metin[:500], "langpair": "en|tr"}, timeout=20)
    cevap.raise_for_status()
    govde = cevap.json()
    if govde.get("responseStatus") != 200 or govde.get("quotaFinished"):
        return None
    return govde["responseData"]["translatedText"]


def cevir(metin):
    """İngilizceden Türkçeye; hiçbir servis cevap vermezse None."""
    if not metin:
        return None
    for servis in (_google, _mymemory):
        try:
            sonuc = (servis(metin) or "").strip()
            if sonuc and sonuc != metin:
                return sonuc
        except Exception:
            continue
    return None
