"""
Sitenin sayfaları. Her fonksiyon isteği okur, sorgular.py'den veriyi alır
ve şablonu çizer; SQL burada yazılmaz.
"""

from flask import Blueprint, abort, jsonify, redirect, render_template, request, url_for

from piyasa import fiyat, hisse_haberleri, sirket_profili, temel, uyeler
from piyasa.analiz import cakisma, ihale, performans, portfoy, sinyaller
from piyasa.analiz import yurutme as yurutme_analizi
from piyasa.bist import sorgular as bist_sorgulari
from piyasa.emtia.tanimlar import EMTIALAR
from piyasa.kripto.tanimlar import KRIPTOLAR
from piyasa.kurallar import PARTILER, parti_bilgisi
from piyasa.web import arama, sorgular
from piyasa.web.karsilastir_rotalari import ana_sayfa_ozeti
from piyasa.web.sorgular import canli as canli_akisi

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
    son_dakika = canli_akisi.son_dakika()
    return render_template("anasayfa.html", aktif="anasayfa", emtia_sayisi=len(EMTIALAR),
                           kripto_sayisi=_kripto_sayisi(), bist_sayisi=len(bist_sorgulari.sirketler()),
                           son_dakika=son_dakika, karsilastirma=ana_sayfa_ozeti(), **sorgular.genel_bakis())


def _kripto_sayisi():
    try:
        from piyasa.kripto import piyasa as kripto_piyasa
        return len(kripto_piyasa.liste()) or len(KRIPTOLAR)
    except Exception:
        return len(KRIPTOLAR)


@site.route("/islemler")
def islemler():
    kaynak = _secenek("kaynak", sorgular.KAYNAKLAR, "hepsi")
    # Kongre bildirimleri seyrek ve geç geldiği için varsayılan dönem daha uzun
    varsayilan_donem = "365" if kaynak in sorgular.SIYASET_KAYNAKLARI else "30"
    donem = _secenek("donem", sorgular.DONEMLER, varsayilan_donem)
    sira = _secenek("sira", sorgular.SIRALAMALAR, "yeni")
    islem = _secenek("islem", ("hepsi", "buy", "sell"), "hepsi")
    # Rol süzgeci yalnızca yönetici işlemlerinde anlamlı
    rol = _secenek("rol", sorgular.ROLLER, "hepsi") if kaynak in ("yonetici", "hepsi") else "hepsi"
    arama = request.args.get("q", "").strip()[:80]
    try:
        sayfa = max(1, int(request.args.get("sayfa", 1)))
    except ValueError:
        sayfa = 1

    satirlar, ozet = sorgular.islem_listesi(arama, islem, donem, kaynak, sira, sayfa, rol)
    toplam = ozet["adet"] or 0

    return render_template(
        "islemler.html",
        aktif="siyasetci" if kaynak in sorgular.SIYASET_KAYNAKLARI
        else {"yonetici": "yonetici"}.get(kaynak, "islemler"),
        satirlar=satirlar,
        ozet=ozet,
        toplam=toplam,
        son_sayfa=max(1, -(-toplam // sorgular.SAYFA_BOYUTU)),
        sayfa=sayfa,
        filtre={"q": arama, "islem": islem, "kaynak": kaynak, "donem": donem, "sira": sira, "rol": rol},
        kaynaklar=sorgular.KAYNAKLAR,
        roller=sorgular.ROLLER,
        donemler=sorgular.DONEMLER,
        siralamalar=sorgular.SIRALAMALAR,
    )


@site.route("/siyasetciler")
def siyasetciler():
    parti = _secenek("parti", PARTILER, "")
    meclis = _secenek("meclis", sorgular.MECLISLER, "")
    return render_template(
        "siyasetciler.html", aktif="siyasetci", parti=parti, meclis=meclis,
        meclisler=sorgular.MECLISLER, **sorgular.siyasetciler(parti, meclis)
    )


@site.route("/hisse/<ticker>")
def hisse(ticker):
    veri = sorgular.hisse(ticker.upper())
    if veri is None:
        abort(404)
    onay = next((h for h in sinyaller.uclu_onay()["liste"] if h["ticker"] == veri["ticker"]), None)
    profil = sirket_profili.kayitli(veri["ticker"])
    return render_template("hisse.html", aktif=None, onay=onay, profil=profil,
                           ihaleler=ihale.hisse_ihaleleri(veri["ticker"]), **veri)


@site.route("/hisse/<ticker>/hakkinda")
def hisse_hakkinda(ticker):
    """Profili henüz kaydedilmemiş hissede kutu sayfa açıldıktan sonra buradan dolar."""
    profil = sirket_profili.profil(ticker)
    if not profil or not profil.get("ozet"):
        return "", 204
    return render_template("_sirket_hakkinda.html", profil=profil)


@site.route("/api/fiyat/<ticker>")
def fiyat_api(ticker):
    """Hisse sayfası fiyat kutusunu ve grafiğini bu adresten doldurur."""
    bilgi = fiyat.fiyat_bilgisi(ticker)
    if bilgi is None:
        return jsonify({"hata": "Bu hisse için güncel fiyat bulunamadı."}), 404
    return jsonify(bilgi)


@site.route("/hisse/<ticker>/rakamlar")
def hisse_rakamlari(ticker):
    """Şirketin rakamları: sayfa açıldıktan sonra yüklenir (Yahoo yavaş olabilir)."""
    bilgiler = temel.temel_bilgiler(ticker)
    if not bilgiler:
        return "", 204
    return render_template("_temel.html", t=bilgiler)


@site.route("/hisse/<ticker>/haberler")
def hisse_haberleri_parcasi(ticker):
    """Hisse sayfasının en altındaki güncel haberler (sayfa açıldıktan sonra yüklenir)."""
    veri = sorgular.hisse(ticker.upper())
    liste = hisse_haberleri.hisse_haberleri(ticker, veri["sirket"]) if veri else []
    return render_template("_hisse_haberleri.html", haberler=liste,
                           sirket=veri["sirket"] if veri else ticker.upper())


@site.route("/api/anlik/<ticker>")
def anlik_api(ticker):
    """Hisse sayfasındaki fiyatı sayfa açıkken dakikada bir tazeler."""
    bilgi = fiyat.anlik_fiyat(ticker)
    if bilgi is None:
        return jsonify({"hata": "Anlık fiyat alınamadı."}), 404
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
    portfoy_verisi = yurutme_analizi.portfoy(slug)
    return render_template(
        "yurutme.html", aktif="siyasetci", kisi=kisi, parti=parti_bilgisi(kisi["parti"]),
        bildirimler=uyeler.yurutme_bildirimleri(slug),
        portfoy=portfoy_verisi,
        portfoy_dilimleri=sorgular.pasta_dilimleri(portfoy_verisi["pozisyonlar"], adet=10) if portfoy_verisi else [],
        islemler=yurutme_analizi.islemler(slug),
    )


@site.route("/fonlar")
def fonlar():
    return render_template("fonlar.html", aktif="fonlar", konsensus=sorgular.fon_konsensusu(),
                           **sorgular.fonlar())


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
