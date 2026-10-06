"""Piyasa Kaydı web sitesi."""


def create_app():
    from piyasa.web.rotalar import app
    return app
