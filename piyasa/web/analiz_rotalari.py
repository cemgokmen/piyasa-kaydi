"""
Analiz sayfaları: siyasetçi performansı, çıkar çatışmaları, sinyaller
(üçlü onay ve geçmiş başarı), günlük özet ve teknik/temel analiz (/analiz).
"""


import json
import re

from flask import Blueprint, abort, make_response, redirect, render_template, request, url_for

from piyasa.analiz import cakisma, ihale, ozet, performans, rapor, sektor_haritasi, sinyaller, teknik
from piyasa.analiz.getiri import UFUKLAR

analiz = Blueprint("analiz", __name__)


@analiz.route("/siyasetciler/performans")
def performans_sayfasi():
    return render_template(
        "performans.html", aktif="siyasetci", sekme="performans",
        siralama=performans.siralama(), genel=performans.genel(),
        ufuk=performans.STANDART_UFUK, asgari=performans.ASGARI_ALIM,
    )


@analiz.route("/siyasetciler/cikar-catismasi")
def cakisma_sayfasi():
    return render_template("cakisma.html", aktif="siyasetci", sekme="cakisma",
                           ihale_sonrasi=ihale.islem_sonrasi(), ihale_penceresi=ihale.PENCERE,
                           ihale_kat=ihale.OLAGANDISI_KAT, **cakisma.rapor())


@analiz.route("/sinyaller")
def sinyaller_sayfasi():
    return render_template(
        "sinyaller.html", aktif="sinyal",
        onay=sinyaller.uclu_onay(), basari=sinyaller.basari(), ufuklar=list(UFUKLAR),
    )


@analiz.route("/sektorler")
def sektorler_sayfasi():
    gun = request.args.get("gun", 90, type=int)
    gun = gun if gun in sektor_haritasi.DONEMLER else 90
    grup = request.args.get("grup", "siyaset")
    grup = grup if grup in sektor_haritasi.GRUPLAR else "siyaset"
    return render_template(
        "sektorler.html", aktif="sinyal", gun=gun, grup=grup,
        donemler=sektor_haritasi.DONEMLER, gruplar=sektor_haritasi.GRUPLAR,
        harita=sektor_haritasi.sektor_haritasi(gun, grup),
    )


@analiz.route("/gunluk-ozet")
@analiz.route("/gunluk-ozet/<gun>")
def gunluk_ozet(gun=None):
    # Özet her zaman bugünündür; eski tarihli bağlantılar bugüne yönlenir
    if gun is not None:
        return redirect(url_for("analiz.gunluk_ozet"), code=301)
    return render_template("ozet.html", aktif="ozet", **ozet.gunluk_ozet())


# ---------------------------------------------------------------------------
# Teknik ve temel analiz (kişisel kullanım: arama motorlarına kapalı)
# ---------------------------------------------------------------------------

ANALIZ_KODU = re.compile(r"^[A-Z0-9][A-Z0-9.\-=^]{0,14}$")


def _dizinsiz(cevap):
    cevap = make_response(cevap)
    cevap.headers["X-Robots-Tag"] = "noindex, nofollow"
    return cevap


@analiz.route("/analiz")
def analiz_sayfasi():
    kod = (request.args.get("kod") or "").strip().upper()
    if kod:
        return redirect(url_for("analiz.analiz_hisse", kod=kod))
    return _dizinsiz(render_template("analiz.html", aktif="analiz", **rapor.genel_bakis()))


@analiz.route("/analiz/<kod>")
def analiz_hisse(kod):
    kod = kod.strip().upper()
    if not ANALIZ_KODU.match(kod):
        abort(404)
    try:
        r = rapor.rapor(kod)
    except rapor.Bulunamadi:
        abort(404)
    grafik = json.dumps(r.pop("grafik"), separators=(",", ":"))
    return _dizinsiz(render_template("analiz_hisse.html", aktif="analiz", r=r, grafik=grafik,
                                     agirliklar=teknik.AGIRLIKLAR))
