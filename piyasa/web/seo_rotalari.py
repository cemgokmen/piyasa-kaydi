"""
Arama motorları ve rehberler: /robots.txt, /sitemap.xml, /rehber ve /rehber/<slug>.
"""

from contextlib import closing
from xml.sax.saxutils import escape

from flask import Blueprint, Response, abort, render_template, request, url_for

from piyasa.emtia.tanimlar import EMTIALAR
from piyasa.kripto.tanimlar import KRIPTOLAR
from piyasa.kurallar import GECERLI_KOD, TEMIZ
from piyasa.onbellek import sureli
from piyasa.veritabani import get_connection
from piyasa.web.rehberler import REHBER, REHBERLER

seo = Blueprint("seo", __name__)


@seo.route("/robots.txt")
def robots():
    kok = request.url_root.rstrip("/")
    metin = f"User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: {kok}/sitemap.xml\n"
    return Response(metin, mimetype="text/plain")


@sureli(3600)
def _dinamik_adresler():
    """Veritabanındaki sayfalar: hisseler, kişiler, fonlar, BIST şirketleri."""
    with closing(get_connection()) as conn:
        hisseler = [r[0] for r in conn.execute(
            f"SELECT DISTINCT ticker FROM transactions WHERE {TEMIZ} AND {GECERLI_KOD}")]
        kisiler = [r[0] for r in conn.execute(
            f"SELECT DISTINCT person_slug FROM transactions WHERE {TEMIZ} AND person_slug IS NOT NULL")]
        fonlar = [r[0] for r in conn.execute("SELECT DISTINCT fon_slug FROM holdings")]
        bist = [r[0] for r in conn.execute("SELECT kod FROM bist_sirket ORDER BY xu100 DESC, kod")]
    return hisseler, kisiler, fonlar, bist


@seo.route("/sitemap.xml")
def site_haritasi():
    kok = request.url_root.rstrip("/")
    sabit = ["/", "/gunluk-ozet", "/siyasetciler", "/islemler?kaynak=yonetici", "/fonlar", "/sinyaller",
             "/siyasetciler/performans", "/siyasetciler/cikar-catismasi", "/sektorler", "/emtialar", "/kripto",
             "/bist", "/rehber", "/hakkinda"]
    hisseler, kisiler, fonlar, bist = _dinamik_adresler()
    adresler = (
        [(a, "daily", "1.0" if a == "/" else "0.8") for a in sabit]
        + [(f"/rehber/{r['slug']}", "monthly", "0.7") for r in REHBERLER]
        + [(f"/emtia/{e['slug']}", "daily", "0.7") for e in EMTIALAR]
        + [(f"/kripto/{k['slug']}", "daily", "0.7") for k in KRIPTOLAR]
        + [(f"/bist/{k}", "daily", "0.6") for k in bist]
        + [(f"/hisse/{t}", "daily", "0.6") for t in hisseler]
        + [(f"/kisi/{k}", "weekly", "0.5") for k in kisiler]
        + [(f"/fon/{f}", "monthly", "0.4") for f in fonlar]
    )
    satirlar = "".join(
        f"<url><loc>{escape(kok + yol)}</loc><changefreq>{siklik}</changefreq><priority>{oncelik}</priority></url>"
        for yol, siklik, oncelik in adresler
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{satirlar}</urlset>')
    return Response(xml, mimetype="application/xml")


@seo.route("/rehber")
def rehberler():
    return render_template("rehberler.html", aktif="rehber", rehberler=REHBERLER)


@seo.route("/rehber/<slug>")
def rehber(slug):
    r = REHBER.get(slug)
    if r is None:
        abort(404)
    return render_template("rehber.html", aktif="rehber", r=r,
                           diger=[x for x in REHBERLER if x["slug"] != slug],
                           kanonik=url_for("seo.rehber", slug=slug, _external=True))
