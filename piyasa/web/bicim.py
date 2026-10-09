"""
Jinja şablon süzgeçleri ve bütün şablonlarda kullanılabilen ortak değişkenler.
"""

import re

from markupsafe import Markup

from piyasa.bicim import (
    ek,
    fiyat,
    kisa_aralik,
    kisa_tarih,
    kisa_tutar,
    ne_zaman,
    ondalik,
    para,
    sayi,
    sirket_gorunen_ad,
    unvan,
    uzun_tarih,
    yuzde,
)
from piyasa.kurallar import FORM4_IS_GUNU, PARTILER, STOCK_ACT_GUN
from piyasa.web.hisse_kodlari import hisse_kodlari

_SAPKALI = str.maketrans("âîûÂÎÛ", "aiuAIU")
_FAZLA_BOSLUK = re.compile(r"(?<=\S) {2,}(?=\S)")


def metin_sadelestir(deger):
    """Kelime arasındaki fazla boşluğu teke indirir, şapkalı harfleri düzleştirir (HTML güvenliği korunur)."""
    if not isinstance(deger, str) or not ("  " in deger or any(h in deger for h in "âîûÂÎÛ")):
        return deger
    yeni = _FAZLA_BOSLUK.sub(" ", deger).translate(_SAPKALI)
    return Markup(yeni) if isinstance(deger, Markup) else yeni


def sablonlara_kaydet(app):
    """Süzgeçleri ve ortak değişkenleri Flask uygulamasına tanıtır."""
    app.add_template_filter(sayi, "sayi")
    app.add_template_filter(kisa_tutar, "tutar")
    app.add_template_filter(lambda n: para(n, "TRY"), "tl")
    app.add_template_filter(uzun_tarih, "uzun_tarih")
    app.add_template_filter(kisa_tarih, "kisa_tarih")
    app.add_template_filter(yuzde, "yuzde")
    app.add_template_filter(fiyat, "fiyat")
    app.add_template_filter(ondalik, "ondalik")
    app.add_template_filter(sirket_gorunen_ad, "sirket_adi")
    app.add_template_filter(unvan, "unvan")
    # Şablondan çıkan her metin: kaynaklardan (KAP, CoinGecko, haberler) gelen fazla boşluk
    # ve şapkalı harfler (â, î, û) sitede görünmesin
    app.jinja_env.finalize = metin_sadelestir
    app.add_template_filter(ne_zaman, "ne_zaman")
    app.add_template_filter(ek, "ek")
    app.add_template_global(kisa_aralik, "aralik")
    app.add_template_global(hisse_kodlari, "hisse_kodlari")

    @app.context_processor
    def ortak():
        from piyasa.emtia import serit
        from piyasa.zamanlama import son_kontrol
        return {
            "son_kontrol": son_kontrol(),
            "serit_gostergeleri": serit.son_hali(),
            "yasal_gun": STOCK_ACT_GUN,
            "form4_gun": FORM4_IS_GUNU,
            "partiler": PARTILER,
        }
