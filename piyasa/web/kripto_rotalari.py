"""
Kripto sayfaları: genel bakış (/kripto) ve her coinin profili (/kripto/<slug>).
"""

from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template

from piyasa import fiyat
from piyasa.emtia import haberler
from piyasa.kripto import piyasa, sorgular
from piyasa.kripto.tanimlar import GRUPLAR, KRIPTO, KRIPTOLAR

kripto = Blueprint("kripto", __name__)


def _kucuk_grafik(degerler, genislik=120, yukseklik=34):
    """Küçük fiyat çizgisi için SVG noktaları."""
    degerler = [v for v in degerler or [] if v is not None]
    if len(degerler) < 2:
        return None
    az, cok = min(degerler), max(degerler)
    aralik = (cok - az) or 1
    adim = genislik / (len(degerler) - 1)
    noktalar = " ".join(
        f"{i * adim:.1f},{(1 - (v - az) / aralik) * (yukseklik - 4) + 2:.1f}" for i, v in enumerate(degerler)
    )
    return {"noktalar": noktalar, "artis": degerler[-1] >= degerler[0]}


def _sirket_fiyatlari(ozetler):
    """Kripto şirketlerinin son fiyatı ve günlük değişimi (paralel, önbellekli)."""
    bilgiler = fiyat.toplu_fiyat_bilgisi([o["ticker"] for o in ozetler], ham=False)
    for o in ozetler:
        b = bilgiler.get(o["ticker"])
        o["fiyat"] = b["fiyat"] if b else None
        o["g1"] = next((d["oran"] for d in b["degisimler"] if d["anahtar"] == "1g"), None) if b else None
    return ozetler


@kripto.route("/kripto")
def liste():
    bilgiler = piyasa.toplu_bilgi()
    kartlar = []
    for k in KRIPTOLAR:
        b = bilgiler.get(k["slug"]) or dict.fromkeys(piyasa.ALANLAR)
        kartlar.append({"k": k, "b": b, "grup": GRUPLAR.get(k["tur"], "Diğer"),
                        "grafik": _kucuk_grafik(b.get("hafta_serisi"))})
    # Piyasa değerine göre; bilgisi alınamayanlar sona
    kartlar.sort(key=lambda x: -(x["b"].get("piyasa_degeri") or 0))
    gruplar = [g for g in dict.fromkeys(GRUPLAR.values()) if any(x["grup"] == g for x in kartlar)]

    return render_template(
        "kriptolar.html",
        aktif="kripto",
        kartlar=kartlar,
        gruplar=gruplar,
        genel=piyasa.genel_piyasa(),
        korku=piyasa.korku_endeksi(),
        kur=piyasa.dolar_tl(),
        cotlar=[(k, c) for k in KRIPTOLAR if k["cot"] and (c := sorgular.cot(k["slug"], hafta=53))],
        etf=[(k, e) for k in KRIPTOLAR if k["etfler"] and (e := sorgular.etf_kurumlari(k["slug"]))],
        siyaset=sorgular.siyasetci_islemleri(limit=60),
        siyaset_ozet=sorgular.siyasetci_ozeti(),
        sirketler=_sirket_fiyatlari(sorgular.sirket_ozetleri()),
        sirket_yonetici=sorgular.sirket_islemleri(siyasetci=False, limit=40),
        sirket_siyaset=sorgular.sirket_islemleri(siyasetci=True, limit=40),
        haberler=haberler.haberler('kripto para OR bitcoin OR ethereum', 10),
    )


@kripto.route("/kripto/<slug>")
def detay(slug):
    k = KRIPTO.get(slug)
    if k is None:
        abort(404)
    b = piyasa.bilgi(slug)
    kur = piyasa.dolar_tl()
    sirketler = sorgular.sirket_ozetleri(slug)
    return render_template(
        "kripto.html",
        aktif="kripto",
        k=k,
        b=b,
        kur=kur,
        tl_fiyat=(b["fiyat"] * kur) if b and b["fiyat"] and kur else None,
        cot=sorgular.cot(slug) if k["cot"] else None,
        etf=sorgular.etf_kurumlari(slug),
        vadeli=piyasa.vadeli(slug),
        yarilanma=piyasa.yarilanma() if slug == "bitcoin" else None,
        korku=piyasa.korku_endeksi() if slug in ("bitcoin", "ethereum") else None,
        islemler=sorgular.siyasetci_islemleri(slug),
        siyaset_ozet=sorgular.siyasetci_ozeti(slug),
        sirketler=_sirket_fiyatlari(sirketler) if sirketler else [],
        sirket_islemleri=sorgular.sirket_islemleri(slug, limit=40) if sirketler else [],
        haberler=haberler.haberler(k["haber"], 12),
        diger=[x for x in KRIPTOLAR if x["slug"] != slug],
    )


@kripto.route("/api/kripto/<slug>/fiyat")
def fiyat_api(slug):
    k = KRIPTO.get(slug)
    bilgi = fiyat.fiyat_bilgisi(k["yahoo"], ham=True) if k else None
    if bilgi is None:
        return jsonify({"hata": "Bu kripto para için güncel fiyat bulunamadı."}), 404
    # Kriptoda "gün" yoktur: ilk kutu gerçek son 24 saatlik değişimdir (CoinGecko)
    b = piyasa.bilgi(slug)
    degisimler = [
        {**d, "etiket": "24 saat", "oran": b["degisim_24s"] if b and b.get("degisim_24s") is not None else d["oran"]}
        if d["anahtar"] == "1g" else d
        for d in bilgi["degisimler"]
    ]
    return jsonify({**bilgi, "degisimler": degisimler})


@kripto.route("/api/kripto/<slug>/anlik")
def anlik_api(slug):
    k = KRIPTO.get(slug)
    if k is None:
        return jsonify({"hata": "Anlık fiyat alınamadı."}), 404
    b = piyasa.bilgi(slug)
    if b and b.get("fiyat") and b.get("degisim_24s") is not None:
        try:
            zaman = int(datetime.fromisoformat(b["guncelleme"].replace("Z", "+00:00")).timestamp())
        except (AttributeError, TypeError, ValueError):
            zaman = None
        return jsonify({
            "kod": k["sembol"], "fiyat": b["fiyat"], "onceki_kapanis": b["fiyat"] / (1 + b["degisim_24s"]),
            "degisim": b["degisim_24s"], "zaman": zaman, "durum": "REGULAR",
            "durum_etiket": "7 gün 24 saat işlem görür", "gecikme": 0, "seans_disi": None,
        })
    bilgi = fiyat.anlik_fiyat(k["yahoo"], ham=True)
    if bilgi is None:
        return jsonify({"hata": "Anlık fiyat alınamadı."}), 404
    return jsonify(bilgi)
