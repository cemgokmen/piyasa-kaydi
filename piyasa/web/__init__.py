"""
Piyasa Kaydı web sitesi.

    from piyasa.web import create_app
    create_app().run(port=5001)
"""

from flask import Flask


def create_app():
    app = Flask(__name__)

    from piyasa.web.bicim import sablonlara_kaydet
    from piyasa.web.rotalar import site

    sablonlara_kaydet(app)
    app.register_blueprint(site)
    return app
