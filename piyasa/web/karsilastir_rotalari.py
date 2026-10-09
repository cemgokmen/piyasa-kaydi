"""
Yatırım karşılaştırma sayfası (/yatirim-karsilastir): geçmişte yapılan bir yatırımın bugünkü
değeri; dolar, altın, borsalar, kripto paralar ve istenen hisseler, enflasyonla birlikte.
Bütün seçimler adreste durur: her karşılaştırma bağlantısıyla paylaşılabilir.
"""

import threading
from datetime import date

from flask import Blueprint, render_template, request

from piyasa.analiz import karsilastirma as k
from piyasa.bicim import AYLAR_UZUN, ay_yil, para_metni

karsilastir = Blueprint("karsilastir", __name__)

PARALAR = {"TRY": "TL", "USD": "Dolar"}
TURLER = {"tek": "Tek seferlik", "aylik": "Her ay"}
EN_FAZLA_TUTAR = 1_000_000_000

# Hazır karşılaştırmalar: (başlık, açıklama, parametreler)
HAZIRLAR = [
    ("Dolar mı, altın mı, borsa mı?", "10 yıl önce 10.000 TL",
     {"para": "TRY", "tutar": 10_000, "v": "tl,dolar,altin,bist100,sp500"}),
    ("Her ay 1.000 TL biriktirseydim", "Son 10 yıl, düzenli yatırım",
     {"para": "TRY", "tutar": 1_000, "tur": "aylik", "v": "tl,dolar,euro,altin,bist100"}),
    ("Bitcoin mi, altın mı?", "10 yıl önce 1.000 dolar",
     {"para": "USD", "tutar": 1_000, "v": "bitcoin,altin,gumus,sp500"}),
    ("Borsa İstanbul ve ABD borsası", "Dolar bazında, 2010'dan bugüne",
     {"para": "USD", "tutar": 10_000, "bas": "2010-01", "v": "bist100,sp500,nasdaq,dolar"}),
    ("2008 krizinden bugüne", "Eylül 2008'de 10.000 dolar",
     {"para": "USD", "tutar": 10_000, "bas": "2008-09", "v": "sp500,nasdaq,altin,bist100,dolar"}),
]


def _secimler():
    a = request.args
    para = a.get("para") if a.get("para") in PARALAR else "TRY"
    tur = a.get("tur") if a.get("tur") in TURLER else "tek"
    try:
        tutar = float(str(a.get("tutar", "")).replace(".", "").replace(",", "."))
    except ValueError:
        tutar = 0
    if not 0 < tutar <= EN_FAZLA_TUTAR:
        tutar = 1_000 if (tur == "aylik" or para == "USD") else 10_000
    bas = k.gecerli_baslangic(a.get("bas")) or k.varsayilan_baslangic()
    anahtarlar = [x for x in ",".join(a.getlist("v")).split(",") if x in k.VARLIK]
    if "v" not in a:
        anahtarlar = list(k.VARSAYILAN["varliklar"])
    ekler = [x.strip().upper() for x in a.get("ek", "").replace(" ", ",").split(",") if x.strip()]
    ekler = list(dict.fromkeys(e for e in ekler if k.KOD.match(e)))[:k.EN_FAZLA_EK]
    return {"para": para, "tur": tur, "tutar": tutar, "bas": bas, "v": anahtarlar, "ek": ekler}


def grafik_verisi(sonuc, secim):
    n = len(sonuc["aylar"])
    return {
        "aylar": sonuc["aylar"],
        "para": secim["para"],
        "seriler": [{"ad": v["ad"], "renk": v["renk"], "degerler": [round(d, 2) for d in v["degerler"]]}
                    for v in sonuc["varliklar"]],
        "enflasyon": [round(d, 2) for d in sonuc["enflasyon"]] if sonuc["enflasyon"] else None,
        # Yatırılan para: tek seferlikte sabit, düzenli yatırımda her ay artar
        "yatirilan": [secim["tutar"] * (i + 1 if secim["tur"] == "aylik" else 1) for i in range(n)],
    }


@karsilastir.route("/yatirim-karsilastir")
def sayfa():
    s = _secimler()
    varliklar = [k.VARLIK[x] for x in s["v"]]
    varliklar += [e for i, kod in enumerate(s["ek"]) if (e := k.ek_varlik(kod, i))]
    varliklar = varliklar[:k.EN_FAZLA_VARLIK]
    sonuc = k.hesapla(varliklar, s["bas"], s["tutar"], s["para"], s["tur"]) if varliklar else None
    bugun = date.today()
    return render_template(
        "karsilastir.html", aktif="karsilastir", s=s, sonuc=sonuc,
        grafik=grafik_verisi(sonuc, s) if sonuc and sonuc["varliklar"] else None,
        varlik_gruplari=_gruplar(), paralar=PARALAR, turler=TURLER, ay_adlari=AYLAR_UZUN,
        yillar=list(range(int(k.ILK_AY[:4]), bugun.year)), hazirlar=HAZIRLAR,
        ay_metni=ay_yil, para_metni=para_metni,
    )


def _gruplar():
    gruplar = {}
    for v in k.VARLIKLAR:
        gruplar.setdefault(v[4], []).append(k.VARLIK[v[0]])
    return gruplar


def ana_sayfa_ozeti():
    """Ana sayfadaki tanıtım kutusu için: 10 yıl önce 10.000 TL; hesap yapılamazsa None."""
    try:
        sonuc = k.hesapla([k.VARLIK[x] for x in ("dolar", "altin", "bist100", "bitcoin")],
                          k.varsayilan_baslangic(), 10_000, "TRY", "tek")
    except Exception:
        return None
    if not sonuc or not sonuc["varliklar"]:
        return None
    return {"bas": ay_yil(sonuc["aylar"][0], "den"), "varliklar": [(v["ad"], para_metni(v["son"], "TRY")) for v in sonuc["varliklar"]],
            "enflasyon": para_metni(sonuc["enflasyon"][-1], "TRY") if sonuc["enflasyon"] else None}


def isit():
    """Yayındaki sitede varsayılan karşılaştırmanın fiyatlarını arka planda önceden indirir."""
    def calis():
        try:
            k.hesapla([k.VARLIK[x[0]] for x in k.VARLIKLAR], k.varsayilan_baslangic(), 10_000)
        except Exception:
            pass
    threading.Thread(target=calis, name="karsilastir-isitma", daemon=True).start()
