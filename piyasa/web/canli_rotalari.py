"""
Canlı sayfa (/canli): piyasa göstergeleri, Borsa İstanbul'da günün hareketi ve bütün
kaynaklardan en yeni bildirimler tek akışta. Sayfa açıkken akış dakikada bir yenilenir.
"""

from flask import Blueprint, render_template, request

from piyasa.bist import hareket, piyasa
from piyasa.onbellek import sureli
from piyasa.web.sorgular import canli as sorgular

canli = Blueprint("canli", __name__)


def _kaynak():
    k = request.args.get("kaynak")
    return k if k in sorgular.KAYNAKLAR else None


@sureli(60)
def _akis(kaynak):
    return sorgular.akis(kaynak)


@canli.route("/canli")
def sayfa():
    kaynak = _kaynak()
    fiyatlar = piyasa.fiyatlar(hareket.tum_kodlar())
    return render_template(
        "canli.html", aktif="canli", kaynak=kaynak, kaynaklar=sorgular.KAYNAKLAR,
        gunler=_akis(kaynak), sayilar=sorgular.bugun_sayilari(),
        endeks=fiyatlar.get("XU100"), **hareket.gunun_hareketi(fiyatlar, adet=5),
    )


@canli.route("/api/canli/akis")
def akis_api():
    """Sayfadaki akışın yenilenen hali (HTML parçası)."""
    return render_template("_canli_akis.html", gunler=_akis(_kaynak()))
