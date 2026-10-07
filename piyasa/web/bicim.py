"""
Jinja şablon süzgeçleri ve bütün şablonlarda kullanılabilen ortak değişkenler.
"""

from piyasa.bicim import (
    fiyat,
    kisa_aralik,
    kisa_tarih,
    kisa_tutar,
    ne_zaman,
    ondalik,
    sayi,
    sirket_gorunen_ad,
    uzun_tarih,
    yuzde,
)
from piyasa.kurallar import FORM4_IS_GUNU, PARTILER, STOCK_ACT_GUN


def sablonlara_kaydet(app):
    """Süzgeçleri ve ortak değişkenleri Flask uygulamasına tanıtır."""
    app.add_template_filter(sayi, "sayi")
    app.add_template_filter(kisa_tutar, "tutar")
    app.add_template_filter(uzun_tarih, "uzun_tarih")
    app.add_template_filter(kisa_tarih, "kisa_tarih")
    app.add_template_filter(yuzde, "yuzde")
    app.add_template_filter(fiyat, "fiyat")
    app.add_template_filter(ondalik, "ondalik")
    app.add_template_filter(sirket_gorunen_ad, "sirket_adi")
    app.add_template_filter(ne_zaman, "ne_zaman")
    app.add_template_global(kisa_aralik, "aralik")

    @app.context_processor
    def ortak():
        from piyasa.web.sorgular import veri_guncelligi
        from piyasa.zamanlama import son_kontrol
        return {
            "veri_guncelligi": veri_guncelligi(),
            "son_kontrol": son_kontrol(),
            "yasal_gun": STOCK_ACT_GUN,
            "form4_gun": FORM4_IS_GUNU,
            "partiler": PARTILER,
        }
