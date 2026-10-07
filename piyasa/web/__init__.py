"""
Piyasa Kaydı web sitesi.

    from piyasa.web import create_app
    create_app().run(port=5001)
"""

from pathlib import Path

from flask import Flask, request
from flask_compress import Compress

STATIK = Path(__file__).parent / "static"
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

    @app.after_request
    def guvenlik_basliklari(cevap):
        cevap.headers.setdefault("X-Content-Type-Options", "nosniff")
        cevap.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        cevap.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        if request.endpoint != "static" and "Cache-Control" not in cevap.headers:
            cevap.headers["Cache-Control"] = "no-cache"
        return cevap

    from piyasa.web import sayfa_onbellegi
    from piyasa.web.analiz_rotalari import analiz
    from piyasa.web.bicim import sablonlara_kaydet
    from piyasa.web.emtia_rotalari import emtia
    from piyasa.web.kripto_rotalari import kripto
    from piyasa.web.rotalar import site

    sablonlara_kaydet(app)
    # Compress'ten sonra kaydedilir: after_request ters sırayla çalıştığı için
    # sayfa sıkıştırılmadan önce önbelleğe yazılır
    sayfa_onbellegi.kaydet(app)
    app.register_blueprint(site)
    app.register_blueprint(emtia)
    app.register_blueprint(analiz)
    app.register_blueprint(kripto)
    return app
