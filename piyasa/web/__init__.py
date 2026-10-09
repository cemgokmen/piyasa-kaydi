"""
Piyasa Kaydı web sitesi.

    from piyasa.web import create_app
    create_app().run(port=5001)
"""

from pathlib import Path

from flask import Flask, redirect, request
from flask_compress import Compress

STATIK = Path(__file__).parent / "static"
# Cloudflare'in (paylaşılan önbellek, s-maxage) başarılı cevapları tutma süresi. Aynı sayfayı
# isteyen sonraki ziyaretçiye cevap Cloudflare'den gider, Mac'in internetinden çıkmaz.
# Tarayıcı her seferinde sorar (max-age=0); sayfalar zaten sunucuda 2 dakika önbellekte.
CDN_SAYFA = 120
CDN_API = 30


def onbellek_basligi(istek, cevap):
    if istek.method not in ("GET", "HEAD") or cevap.status_code != 200 or "Set-Cookie" in cevap.headers:
        return "no-cache"
    sure = CDN_API if istek.path.startswith("/api/") else CDN_SAYFA
    return f"public, max-age=0, s-maxage={sure}"


# Statik dosyalar adresine sürüm eklendiği için tarayıcıda ve Cloudflare'de
# uzun süre tutulabilir; dosya değişince adres de değişir
STATIK_SURESI = 365 * 24 * 3600


def create_app(vekil_arkasinda=False):
    """vekil_arkasinda: Cloudflare gibi bir vekil sunucunun arkasında yayın (gerçek adres ve https)."""
    app = Flask(__name__)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = STATIK_SURESI
    app.config["COMPRESS_MIMETYPES"] = ["text/html", "text/css", "application/javascript",
                                        "text/javascript", "application/json", "image/svg+xml"]
    Compress(app)
    if vekil_arkasinda:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.url_defaults
    def statik_surum(endpoint, degerler):
        if endpoint == "static" and "v" not in degerler:
            dosya = STATIK / degerler.get("filename", "")
            if dosya.is_file():
                degerler["v"] = int(dosya.stat().st_mtime)

    @app.before_request
    def www_olmadan():
        # Tek adres: www.piyasakaydi.com → piyasakaydi.com (arama motorları aynı sayfayı iki kez saymasın)
        if request.host.startswith("www."):
            return redirect(request.url.replace("://www.", "://", 1), code=301)
        return None

    @app.after_request
    def guvenlik_basliklari(cevap):
        cevap.headers.setdefault("X-Content-Type-Options", "nosniff")
        cevap.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        cevap.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if request.endpoint != "static" and "Cache-Control" not in cevap.headers:
            cevap.headers["Cache-Control"] = onbellek_basligi(request, cevap)
        return cevap

    from piyasa.web import sayfa_onbellegi
    from piyasa.web.analiz_rotalari import analiz
    from piyasa.web.bicim import sablonlara_kaydet
    from piyasa.web.bist_rotalari import bist, fiyatlari_isit
    from piyasa.web.canli_rotalari import canli
    from piyasa.web.emtia_rotalari import emtia
    from piyasa.web.karsilastir_rotalari import isit as karsilastirmayi_isit
    from piyasa.web.karsilastir_rotalari import karsilastir
    from piyasa.web.kripto_rotalari import kripto
    from piyasa.web.rotalar import site
    from piyasa.web.seo_rotalari import seo

    sablonlara_kaydet(app)
    # Compress'ten sonra kaydedilir: after_request ters sırayla çalıştığı için
    # sayfa sıkıştırılmadan önce önbelleğe yazılır
    sayfa_onbellegi.kaydet(app)
    app.register_blueprint(site)
    app.register_blueprint(emtia)
    app.register_blueprint(analiz)
    app.register_blueprint(kripto)
    app.register_blueprint(bist)
    app.register_blueprint(seo)
    app.register_blueprint(canli)
    app.register_blueprint(karsilastir)
    if vekil_arkasinda:
        # Yalnızca yayındaki sitede: BIST 100 fiyatları arka planda hazır tutulur
        fiyatlari_isit()
        karsilastirmayi_isit()
    return app
