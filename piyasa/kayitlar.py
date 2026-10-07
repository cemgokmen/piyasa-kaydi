"""
İşlem kayıtlarını gösterime hazırlar: gecikme, geç bildirim, yüklü alım,
rol ve parti gibi türetilmiş alanlar.
"""

from datetime import date

import numpy as np

from piyasa.bicim import kisa_aralik, tam_tutar, tarih_temizle, unvan
from piyasa.kurallar import FORM4_IS_GUNU, STOCK_ACT_GUN, YUKLU_ALIM_ALT_SINIR, parti_bilgisi
from piyasa.slug import slugify


def rol_metni(kayit):
    if kayit.get("chamber"):
        parcalar = [kayit["chamber"], kayit.get("state")]
        return " · ".join(p for p in parcalar if p)
    return unvan(kayit.get("job_title")) or "Bildirim yükümlüsü"


def gec_mi(kayit):
    """Bildirim yasal süreden sonra mı yapılmış?"""
    if kayit.get("chamber"):
        return kayit["gecikme"] > STOCK_ACT_GUN
    is_gunu = int(np.busday_count(kayit["transaction_date"], kayit["disclosed_date"]))
    return is_gunu > FORM4_IS_GUNU


def islem_hazirla(satir):
    """Veritabanı satırını şablonda kullanılacak hale getirir."""
    k = dict(satir)
    k["transaction_date"] = tarih_temizle(k["transaction_date"])
    k["disclosed_date"] = tarih_temizle(k["disclosed_date"])
    k["gecikme"] = (
        date.fromisoformat(k["disclosed_date"]) - date.fromisoformat(k["transaction_date"])
    ).days
    k["siyasetci"] = bool(k.get("chamber"))
    k["gec"] = gec_mi(k)
    k["tutar_tam"] = tam_tutar(k["amount_min"], k["amount_max"])
    k["tutar_kisa"] = kisa_aralik(k["amount_min"], k["amount_max"])
    # Tutarı sıfır bildirilen yönetici işlemleri: hisse ödülü, vergi için alıkoyma, hediye
    k["bedelsiz"] = k["amount_max"] == 0 and not k["siyasetci"]
    if k["bedelsiz"]:
        k["tutar_kisa"] = "Bedelsiz"
        k["tutar_tam"] = "Bildirimde tutar yok: hisse ödülü, vergi için alıkoyma ya da hediye olabilir"
    k["islem_metni"] = "Alım" if k["action"] == "buy" else "Satım"
    k["rol"] = rol_metni(k)
    k["parti"] = parti_bilgisi(k.get("party"))
    k["yuklu"] = (
        k["siyasetci"] and k["action"] == "buy"
        and (k["amount_min"] or 0) >= YUKLU_ALIM_ALT_SINIR
    )
    if not k.get("person_slug"):
        k["person_slug"] = slugify(k["person"])
    return k
