"""
Analiz sayfaları: siyasetçi performansı, çıkar çatışmaları, sinyaller
(üçlü onay ve geçmiş başarı) ve günlük özet.
"""

import re

from flask import Blueprint, abort, render_template

from piyasa.analiz import cakisma, ozet, performans, sinyaller
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
    return render_template("cakisma.html", aktif="siyasetci", sekme="cakisma", **cakisma.rapor())


@analiz.route("/sinyaller")
def sinyaller_sayfasi():
    return render_template(
        "sinyaller.html", aktif="sinyal",
        onay=sinyaller.uclu_onay(), basari=sinyaller.basari(), ufuklar=list(UFUKLAR),
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
