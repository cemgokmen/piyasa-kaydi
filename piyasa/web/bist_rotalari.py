"""
Borsa İstanbul sayfaları: BIST 100 ve KAP bildirimleri (/bist) ve şirket sayfası (/bist/<kod>).
"""

import re
import threading
import time

from flask import Blueprint, abort, jsonify, render_template, request

from piyasa import fiyat, hisse_haberleri, sirket_profili, temel
from piyasa.bist import hareket, piyasa, sorgular
from piyasa.web.grafik import kucuk_grafik
from piyasa.web.sorgular.fonlar import pasta_dilimleri

bist = Blueprint("bist", __name__)

KOD = re.compile(r"^[A-Z0-9]{3,6}$")
# Tanıtım metninin başındaki tam unvan: '... Anonim Ortakligi', '... A.S.', '... Sanayi ve Ticaret A.Ş.'
TR_UNVAN = re.compile(r"^[^,.]{3,120}?\b(Anonim\s+(Ortakligi|Ortaklığı|Sirketi|Şirketi)|A\.\s?[SŞ]\.?|T\.A\.[SŞO]\.?)",
                      re.IGNORECASE)


def _fiyat_ekle(sirketler, fiyatlar):
    """Liste satırlarına fiyat ve küçük grafik."""
    for s in hareket.fiyat_ekle(sirketler, fiyatlar):
        s["grafik"] = kucuk_grafik(s["f"]["seri"], 100, 30, nokta=32) if s["f"] else None
    return sirketler


@bist.route("/bist")
def liste():
    liste_ = request.args.get("liste", "tum")
    liste_ = liste_ if liste_ in sorgular.LISTELER else "tum"
    sektorler = sorgular.sektorler()
    sektor = request.args.get("sektor") or None
    sektor = sektor if sektor in {s[0] for s in sektorler} else None

    fiyatlar = piyasa.fiyatlar(hareket.tum_kodlar())
    sirketler = _fiyat_ekle(sorgular.sirketler(liste_, sektor), fiyatlar)
    son = sorgular.son_islem_tarihleri([s["kod"] for s in sirketler])
    for s in sirketler:
        s["iceriden"] = son.get(s["kod"])

    return render_template(
        "bist.html",
        aktif="bist",
        sirketler=sirketler,
        liste=liste_,
        listeler=sorgular.LISTELER,
        sektor=sektor,
        sektorler=sektorler,
        endeks=fiyatlar.get("XU100"),
        endeks30=fiyatlar.get("XU030"),
        **hareket.gunun_hareketi(fiyatlar),
        pay_ozeti=sorgular.pay_ozeti(30),
        iceriden=sorgular.pay_islemleri(gun=60, limit=150),
        geri_alim=sorgular.geri_alim_ozeti(30),
        ortaklar=sorgular.buyuk_ortaklar(),
    )


def _ortaklik(kod):
    o = sorgular.ortaklik(kod)
    if o:
        o["dilimler"] = pasta_dilimleri(o["dilimler"], adet=8)
    return o


@bist.route("/bist/ortak/<slug>")
def ortak(slug):
    veri = sorgular.ortak(slug)
    if veri is None:
        abort(404)
    return render_template("bist_ortak.html", aktif="bist", **veri)


@bist.route("/bist/<kod>")
def sirket(kod):
    kod = kod.upper()
    if not KOD.match(kod):
        abort(404)
    s = sorgular.sirket(kod)
    if s is None:
        abort(404)
    islemler = sorgular.pay_islemleri(kod=kod, limit=100)
    fiyatlar = piyasa.fiyatlar(hareket.tum_kodlar())
    benzerler = _fiyat_ekle(sorgular.benzerler(kod, s.get("sektor"), s.get("ana_sektor")), fiyatlar)
    return render_template(
        "bist_sirket.html",
        aktif="bist",
        s=s,
        f=hareket.gecerli(fiyatlar.get(kod)),
        ortaklik=_ortaklik(kod),
        endeks=fiyatlar.get("XU100"),
        benzerler=benzerler,
        kisa_ad=sorgular.kisa_unvan(s["unvan"]),
        islemler=[i for i in islemler if i["kisi_turu"] != "fon"],
        fon_bildirimleri=[i for i in islemler if i["kisi_turu"] == "fon"],
        geri=sorgular.geri_alimlar(kod),
        aciklamalar=sorgular.ozel_aciklamalar(kod),
    )


@bist.route("/bist/<kod>/hakkinda")
def hakkinda(kod):
    kod = kod.upper()
    if not KOD.match(kod):
        abort(404)
    profil = sirket_profili.profil(piyasa.yahoo_kodu(kod), yahoo=piyasa.yahoo_kodu(kod))
    if not profil or not profil.get("ozet"):
        return "", 204
    s = sorgular.sirket(kod)
    if s:
        # Yahoo'nun Türkçe karaktersiz unvanı ('Türk Hava Yollari Anonim Ortakligi') yerine KAP'taki ad
        ozet = TR_UNVAN.sub(sorgular.kisa_unvan(s["unvan"]), profil["ozet"], count=1)
        profil = {**profil, "ozet": ozet, "merkez": s.get("sehir") or profil.get("merkez")}
    return render_template("_sirket_hakkinda.html", profil=profil)


@bist.route("/bist/<kod>/rakamlar")
def rakamlar(kod):
    kod = kod.upper()
    if not KOD.match(kod):
        abort(404)
    bilgiler = temel.temel_bilgiler(piyasa.yahoo_kodu(kod), ham=True)
    if not bilgiler:
        return "", 204
    return render_template("_temel.html", t=bilgiler)


@bist.route("/bist/<kod>/haberler")
def haberler(kod):
    kod = kod.upper()
    s = sorgular.sirket(kod) if KOD.match(kod) else None
    if not s:
        return "", 204
    ad = sorgular.kisa_unvan(s["unvan"])
    return render_template("_hisse_haberleri.html", haberler=hisse_haberleri.hisse_haberleri(kod, ad), sirket=ad)


@bist.route("/api/bist/<kod>/fiyat")
def fiyat_api(kod):
    kod = kod.upper()
    bilgi = fiyat.fiyat_bilgisi(piyasa.yahoo_kodu(kod), ham=True) if KOD.match(kod) else None
    if bilgi is None:
        return jsonify({"hata": "Bu hisse için güncel fiyat bulunamadı."}), 404
    return jsonify(bilgi)


@bist.route("/api/bist/<kod>/anlik")
def anlik_api(kod):
    kod = kod.upper()
    bilgi = fiyat.anlik_fiyat(piyasa.yahoo_kodu(kod), ham=True) if KOD.match(kod) else None
    if bilgi is None:
        return jsonify({"hata": "Anlık fiyat alınamadı."}), 404
    return jsonify(bilgi)


def fiyatlari_isit(aralik=5 * 60):
    """
    Yayındaki sitede BIST fiyatlarını arka planda tazeler: yüzlerce hissenin toplu indirilmesi
    dakikaları bulabiliyor, ziyaretçi beklemesin. Beş dakikada bir yalnızca kontrol edilir;
    indirme borsa açıkken 20 dakikada bir ve kapanıştan sonra bir kez yapılır (bkz. bist/piyasa.py).
    """
    def dongu():
        time.sleep(5)
        while True:
            try:
                piyasa.tazele(hareket.tum_kodlar())
            except Exception:
                pass
            time.sleep(aralik)

    threading.Thread(target=dongu, name="bist-fiyat-isitma", daemon=True).start()
