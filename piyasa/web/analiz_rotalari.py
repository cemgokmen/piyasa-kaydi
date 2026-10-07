"""
Analiz sayfaları: siyasetçi performansı, çıkar çatışmaları, sinyaller
(üçlü onay ve geçmiş başarı) ve günlük özet.
"""

import re

from flask import Blueprint, abort, render_template, request

from piyasa.analiz import cakisma, ihale, ozet, performans, sektor_haritasi, sinyaller
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
    if gun is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", gun):
        abort(404)
    veri = ozet.gunluk_ozet(gun)
    if veri is None or (gun is not None and veri["gun"] != gun):
        abort(404)
    return render_template("ozet.html", aktif="ozet", **veri)
