"""
Emtia sayfaları: genel bakış (/emtialar) ve her emtianın sayfası (/emtia/<slug>).
"""

from concurrent.futures import ThreadPoolExecutor

from flask import Blueprint, abort, jsonify, render_template

from piyasa.emtia import haberler, sorgular
from piyasa.emtia.tanimlar import EMTIA, EMTIALAR, GOSTERGELER, GRUPLAR, ONS_GRAM
from piyasa.web import fiyat

emtia = Blueprint("emtia", __name__)


def _fiyatlar(kodlar):
    """Birden çok Yahoo kodunun fiyat bilgisini paralel alır (önbellekten ya da Yahoo'dan)."""
    with ThreadPoolExecutor(max_workers=len(kodlar)) as havuz:
        return dict(zip(kodlar, havuz.map(lambda k: fiyat.fiyat_bilgisi(k, ham=True), kodlar)))


def _degisim(bilgi, anahtar):
    if not bilgi:
        return None
    return next((d["oran"] for d in bilgi["degisimler"] if d["anahtar"] == anahtar), None)


def _kucuk_grafik(bilgi, genislik=120, yukseklik=34):
    """Kartlardaki küçük 1 yıllık fiyat çizgisi için SVG noktaları."""
    if not bilgi:
        return None
    degerler = [n[1] for n in bilgi["seriler"].get("1y", []) if n[1] is not None]
    if len(degerler) < 2:
        return None
    az, cok = min(degerler), max(degerler)
    aralik = (cok - az) or 1
    adim = genislik / (len(degerler) - 1)
    noktalar = " ".join(
        f"{i * adim:.1f},{(1 - (v - az) / aralik) * (yukseklik - 4) + 2:.1f}"
        for i, v in enumerate(degerler)
    )
    return {"noktalar": noktalar, "artis": degerler[-1] >= degerler[0]}


def _gram_altin(fiyatlar):
    """Gram altının TL fiyatı ve değişimleri: ons altın × dolar/TL ÷ 31,10."""
    altin, kur = fiyatlar.get("GC=F"), fiyatlar.get(GOSTERGELER["usdtry"]["yahoo"])
    if not (altin and kur):
        return None
    degisimler = []
    for d in altin["degisimler"]:
        k = _degisim(kur, d["anahtar"])
        oran = None if d["oran"] is None or k is None else (1 + d["oran"]) * (1 + k) - 1
        degisimler.append({"anahtar": d["anahtar"], "etiket": d["etiket"], "oran": oran})
    return {"fiyat": altin["fiyat"] * kur["fiyat"] / ONS_GRAM, "kur": kur["fiyat"],
            "degisimler": degisimler}


@emtia.route("/emtialar")
def liste():
    kodlar = [e["yahoo"] for e in EMTIALAR] + [g["yahoo"] for g in GOSTERGELER.values()]
    fiyatlar = _fiyatlar(kodlar)

    kartlar = {grup: [] for grup in GRUPLAR}
    for e in EMTIALAR:
        bilgi = fiyatlar.get(e["yahoo"])
        kartlar[e["grup"]].append({
            "emtia": e,
            "fiyat": bilgi["fiyat"] if bilgi else None,
            "g1": _degisim(bilgi, "1g"),
            "a1": _degisim(bilgi, "1a"),
            "y1": _degisim(bilgi, "1y"),
            "hacim": bilgi.get("hacim") if bilgi else None,
            "grafik": _kucuk_grafik(bilgi),
        })

    altin, gumus = fiyatlar.get("GC=F"), fiyatlar.get("SI=F")
    dolar = fiyatlar.get(GOSTERGELER["dolar_endeksi"]["yahoo"])

    return render_template(
        "emtialar.html",
        aktif="emtia",
        gruplar=[(g, kartlar[g]) for g in GRUPLAR if kartlar[g]],
        faiz=sorgular.faiz_kararlari(),
        dolar=dolar,
        dolar_1a=_degisim(dolar, "1a"),
        gram_altin=_gram_altin(fiyatlar),
        altin_gumus=(altin["fiyat"] / gumus["fiyat"]) if altin and gumus else None,
        fonlar=sorgular.cot_tablosu(EMTIALAR),
        karar_haberleri=haberler.karar_haberleri(10),
        guncelleme=sorgular.son_guncelleme(),
    )


@emtia.route("/emtia/<slug>")
def detay(slug):
    e = EMTIA.get(slug)
    if e is None:
        abort(404)

    gram_altin = None
    if slug == "altin":
        gram_altin = _gram_altin(_fiyatlar(["GC=F", GOSTERGELER["usdtry"]["yahoo"]]))

    return render_template(
        "emtia.html",
        aktif="emtia",
        e=e,
        cot=sorgular.cot(slug) if e["cot"] else None,
        eia=sorgular.eia(e["eia"]) if e["eia"] else None,
        faiz=sorgular.faiz_kararlari(),
        gram_altin=gram_altin,
        haberler=haberler.haberler(e["haber"], 12),
        guncelleme=sorgular.son_guncelleme(),
        diger=[x for x in EMTIALAR if x["slug"] != slug],
    )


@emtia.route("/api/emtia/<slug>/fiyat")
def fiyat_api(slug):
    e = EMTIA.get(slug)
    bilgi = fiyat.fiyat_bilgisi(e["yahoo"], ham=True) if e else None
    if bilgi is None:
        return jsonify({"hata": "Bu emtia için güncel fiyat bulunamadı."}), 404
    return jsonify(bilgi)
