"""
Kripto sayfaları: genel bakış (/kripto) ve her coinin profili (/kripto/<slug>).
"""

from flask import Blueprint, abort, jsonify, render_template

from piyasa import fiyat
from piyasa.emtia import haberler
from piyasa.emtia.sorgular import faiz_kararlari
from piyasa.kripto import piyasa, sorgular
from piyasa.kripto.tanimlar import KRIPTO, KRIPTOLAR

kripto = Blueprint("kripto", __name__)


def _degisim(bilgi, anahtar):
    if not bilgi:
        return None
    return next((d["oran"] for d in bilgi["degisimler"] if d["anahtar"] == anahtar), None)


def _kucuk_grafik(bilgi, genislik=120, yukseklik=34):
    """Kartlardaki küçük 1 yıllık fiyat çizgisi (SVG noktaları)."""
    if not bilgi:
        return None
    degerler = [n[1] for n in bilgi["seriler"].get("1y", []) if n[1] is not None]
    if len(degerler) < 2:
        return None
    az, cok = min(degerler), max(degerler)
    aralik = (cok - az) or 1
    adim = genislik / (len(degerler) - 1)
    noktalar = " ".join(
        f"{i * adim:.1f},{(1 - (v - az) / aralik) * (yukseklik - 4) + 2:.1f}" for i, v in enumerate(degerler)
    )
    return {"noktalar": noktalar, "artis": degerler[-1] >= degerler[0]}


@kripto.route("/kripto")
def liste():
    fiyatlar = fiyat.toplu_fiyat_bilgisi([k["yahoo"] for k in KRIPTOLAR])
    bilgiler = piyasa.toplu_bilgi()
    kartlar = []
    for k in KRIPTOLAR:
        f, b = fiyatlar.get(k["yahoo"]), bilgiler.get(k["slug"])
        kartlar.append({
            "k": k,
            "fiyat": (f and f["fiyat"]) or (b and b["fiyat"]),
            "g1": _degisim(f, "1g"), "h1": _degisim(f, "1h"), "y1": _degisim(f, "1y"),
            "piyasa_degeri": b and b["piyasa_degeri"],
            "hacim": b and b["hacim_24s"],
            "zirveden": b and b["zirveden_uzaklik"],
            "logo": b and b["logo"],
            "grafik": _kucuk_grafik(f),
        })
    # Piyasa değerine göre sırala; bilgisi alınamayanlar sona
    kartlar.sort(key=lambda x: -(x["piyasa_degeri"] or 0))
    toplam = sum(x["piyasa_degeri"] or 0 for x in kartlar)
    btc = next((x for x in kartlar if x["k"]["slug"] == "bitcoin"), None)

    return render_template(
        "kriptolar.html",
        aktif="kripto",
        kartlar=kartlar,
        toplam_deger=toplam,
        btc_payi=(btc["piyasa_degeri"] / toplam) if btc and btc["piyasa_degeri"] and toplam else None,
        kur=piyasa.dolar_tl(),
        cotlar=[(k, c) for k in KRIPTOLAR if k["cot"] and (c := sorgular.cot(k["slug"], hafta=53))],
        etf=[(k, e) for k in KRIPTOLAR if k["etfler"] and (e := sorgular.etf_kurumlari(k["slug"]))],
        siyaset=sorgular.siyasetci_islemleri(limit=30),
        siyaset_ozet=sorgular.siyasetci_ozeti(),
        haberler=haberler.haberler('kripto para OR bitcoin OR ethereum', 10),
    )


@kripto.route("/kripto/<slug>")
def detay(slug):
    k = KRIPTO.get(slug)
    if k is None:
        abort(404)
    b = piyasa.bilgi(slug)
    kur = piyasa.dolar_tl()
    bilgiler = piyasa.toplu_bilgi()
    sira = sorted((s for s in bilgiler if bilgiler[s]), key=lambda s: -bilgiler[s]["piyasa_degeri"])
    faiz = faiz_kararlari() if k["cot"] else None
    return render_template(
        "kripto.html",
        aktif="kripto",
        k=k,
        b=b,
        kur=kur,
        tl_fiyat=(b["fiyat"] * kur) if b and b["fiyat"] and kur else None,
        sira=(sira.index(slug) + 1) if slug in sira else None,
        cot=sorgular.cot(slug) if k["cot"] else None,
        etf=sorgular.etf_kurumlari(slug),
        vadeli=piyasa.vadeli(slug),
        faiz=faiz,
        islemler=sorgular.siyasetci_islemleri(slug),
        siyaset_ozet=sorgular.siyasetci_ozeti(slug),
        haberler=haberler.haberler(k["haber"], 12),
        diger=[x for x in KRIPTOLAR if x["slug"] != slug],
    )


@kripto.route("/api/kripto/<slug>/fiyat")
def fiyat_api(slug):
    k = KRIPTO.get(slug)
    bilgi = fiyat.fiyat_bilgisi(k["yahoo"], ham=True) if k else None
    if bilgi is None:
        return jsonify({"hata": "Bu kripto para için güncel fiyat bulunamadı."}), 404
    return jsonify(bilgi)


@kripto.route("/api/kripto/<slug>/anlik")
def anlik_api(slug):
    k = KRIPTO.get(slug)
    bilgi = fiyat.anlik_fiyat(k["yahoo"], ham=True) if k else None
    if bilgi is None:
        return jsonify({"hata": "Anlık fiyat alınamadı."}), 404
    return jsonify(bilgi)
