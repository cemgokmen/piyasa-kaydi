"""
Sitenin sayfaları. Her fonksiyon isteği okur, sorgular.py'den veriyi alır
ve şablonu çizer; SQL burada yazılmaz.
"""

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from piyasa import fiyat, uyeler
from piyasa.analiz import cakisma, performans, portfoy, sinyaller
from piyasa.emtia.tanimlar import EMTIALAR
from piyasa.kurallar import PARTILER, parti_bilgisi
from piyasa.web import arama, sorgular

site = Blueprint("site", __name__)


def _secenek(ad, gecerli, varsayilan):
    """Sorgu parametresini okur; geçersizse varsayılanı döndürür."""
    deger = request.args.get(ad, varsayilan)
    return deger if deger in gecerli else varsayilan


@site.route("/")
def anasayfa():
    # Eski sürümde liste ana sayfadaydı; filtreli eski bağlantılar listeye gitsin
    if request.args:
        return redirect(url_for("site.islemler", **request.args))
    return render_template("anasayfa.html", aktif="anasayfa", emtia_sayisi=len(EMTIALAR),
                           **sorgular.genel_bakis())


@site.route("/islemler")
def islemler():
    kaynak = _secenek("kaynak", sorgular.KAYNAKLAR, "hepsi")
    # Kongre bildirimleri seyrek ve geç geldiği için varsayılan dönem daha uzun
    varsayilan_donem = "365" if kaynak == "siyasetci" else "30"
    donem = _secenek("donem", sorgular.DONEMLER, varsayilan_donem)
    sira = _secenek("sira", sorgular.SIRALAMALAR, "yeni")
    islem = _secenek("islem", ("hepsi", "buy", "sell"), "hepsi")
    arama = request.args.get("q", "").strip()[:80]
    try:
        sayfa = max(1, int(request.args.get("sayfa", 1)))
    except ValueError:
        sayfa = 1

    satirlar, ozet = sorgular.islem_listesi(arama, islem, donem, kaynak, sira, sayfa)
    toplam = ozet["adet"] or 0

    return render_template(
        "islemler.html",
        aktif={"siyasetci": "siyasetci", "yonetici": "yonetici"}.get(kaynak, "islemler"),
        satirlar=satirlar,
        ozet=ozet,
        toplam=toplam,
        son_sayfa=max(1, -(-toplam // sorgular.SAYFA_BOYUTU)),
        sayfa=sayfa,
        filtre={"q": arama, "islem": islem, "kaynak": kaynak, "donem": donem, "sira": sira},
        kaynaklar=sorgular.KAYNAKLAR,
        donemler=sorgular.DONEMLER,
        siralamalar=sorgular.SIRALAMALAR,
    )


@site.route("/siyasetciler")
def siyasetciler():
    parti = _secenek("parti", PARTILER, "")
    return render_template(
        "siyasetciler.html", aktif="siyasetci", parti=parti, **sorgular.siyasetciler(parti)
    )


@site.route("/hisse/<ticker>")
def hisse(ticker):
    veri = sorgular.hisse(ticker.upper())
    if veri is None:
        abort(404)
    onay = next((h for h in sinyaller.uclu_onay()["liste"] if h["ticker"] == veri["ticker"]), None)
    return render_template("hisse.html", aktif=None, onay=onay, **veri)


@site.route("/api/fiyat/<ticker>")
def fiyat_api(ticker):
    """Hisse sayfası fiyat kutusunu ve grafiğini bu adresten doldurur."""
    bilgi = fiyat.fiyat_bilgisi(ticker)
    if bilgi is None:
        return jsonify({"hata": "Bu hisse için güncel fiyat bulunamadı."}), 404
    return jsonify(bilgi)


@site.route("/api/oneri")
def oneri_api():
    """Arama kutusunun altında açılan öneriler."""
    sorgu = request.args.get("q", "").strip()[:60]
    return jsonify({"sorgu": sorgu, "oneriler": arama.oneriler(sorgu)})


@site.route("/kisi/<slug>")
def kisi(slug):
    veri = sorgular.kisi(slug)
    if veri is None:
        abort(404)
    aktif = "siyasetci" if veri["siyasetci"] else "yonetici"
    if veri["siyasetci"]:
        veri["portfoy"] = portfoy.hesapla(slug)
        if veri["portfoy"] and veri["portfoy"]["pozisyonlar"]:
            veri["portfoy_dilimleri"] = sorgular.pasta_dilimleri(veri["portfoy"]["pozisyonlar"], adet=8)
        veri["performans"] = performans.kisi(slug)
        veri["komiteler"] = cakisma.uye_komiteleri(slug)
        veri["cakisma_sayisi"] = sum(1 for i in veri["islemler"] if i["cakisma"])
    return render_template("kisi.html", aktif=aktif, **veri)


@site.route("/yurutme/<slug>")
def yurutme(slug):
    kisi = uyeler.YURUTME_SLUG.get(slug)
    if kisi is None:
        abort(404)
    bildirimler = uyeler.yurutme_bildirimleri(slug)
    return render_template("yurutme.html", aktif="siyasetci", kisi=kisi, bildirimler=bildirimler,
                           parti=parti_bilgisi(kisi["parti"]))


@site.route("/fonlar")
def fonlar():
    return render_template("fonlar.html", aktif="fonlar", **sorgular.fonlar())


@site.route("/fon/<slug>")
def fon(slug):
    veri = sorgular.fon(slug)
    if veri is None:
        abort(404)
    return render_template("fon.html", aktif="fonlar", **veri)


FAVICON = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="7" fill="#1B4DFF"/>'
    '<path d="M7 22l6-7 5 4 7-9" stroke="white" stroke-width="3" fill="none" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)


@site.route("/favicon.ico")
def favicon():
    # Simge sayfalarda satır içi; tarayıcıların kendiliğinden istediği adres için
    return FAVICON, 200, {"Content-Type": "image/svg+xml",
                          "Cache-Control": "public, max-age=604800"}


@site.route("/hakkinda")
def hakkinda():
    return render_template("hakkinda.html", aktif="hakkinda")


@site.app_errorhandler(404)
def bulunamadi(_hata):
    return render_template("404.html", aktif=None), 404
