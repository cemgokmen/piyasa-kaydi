"""
Paylaşım kartları (/paylasim): X'te elle paylaşmak için hazır görsel kartlar ve haber metinleri.
Yalnızca sitenin çalıştığı bilgisayardan açılır (http://127.0.0.1:5001/paylasim); Cloudflare
üzerinden gelen her istek 404 alır. Sayfa önbelleğe alınmaz.
"""

from contextlib import closing
from datetime import datetime
from functools import wraps

from flask import Blueprint, abort, jsonify, render_template, request

from piyasa.paylasim import calistir
from piyasa.veritabani import get_connection, init_db

paylasim = Blueprint("paylasim", __name__)
YEREL = ("127.0.0.1", "::1")
SURELER = {36: "Son 36 saat", 72: "Son 3 gün", 168: "Son 1 hafta", 240: "Son 10 gün"}


def yerel_mi():
    """İstek bu bilgisayardan mı? Tünelden gelenlerde Cloudflare başlıkları bulunur."""
    return (request.remote_addr in YEREL and "CF-Connecting-IP" not in request.headers
            and "CF-Ray" not in request.headers)


def yalnizca_yerel(fonksiyon):
    @wraps(fonksiyon)
    def sarili(*args, **kwargs):
        if not yerel_mi():
            abort(404)
        cevap = fonksiyon(*args, **kwargs)
        if not isinstance(cevap, tuple):
            from flask import make_response
            cevap = make_response(cevap)
            cevap.headers["Cache-Control"] = "no-store"
            cevap.headers["X-Robots-Tag"] = "noindex"
        return cevap
    return sarili


@paylasim.route("/paylasim")
@yalnizca_yerel
def sayfa():
    init_db()
    saat = request.args.get("saat", 36, type=int)
    saat = saat if saat in SURELER else 36
    with closing(get_connection()) as conn:
        adaylar = calistir.bekleyenler(conn, saat=saat)
        paylasilanlar = [dict(r) for r in conn.execute(
            "SELECT anahtar, metin, zaman FROM paylasim ORDER BY zaman DESC LIMIT 15")]
    return render_template("paylasim.html", aktif="paylasim", adaylar=adaylar, paylasilanlar=paylasilanlar,
                           saat=saat, sureler=SURELER)


@paylasim.route("/paylasim/isaretle", methods=["POST"])
@yalnizca_yerel
def isaretle():
    """Kart paylaşıldı (ya da istenmiyor): bir daha önerilmez."""
    veri = request.get_json(silent=True) or {}
    anahtar, metin_, durum = veri.get("anahtar"), veri.get("metin", ""), veri.get("durum", "elle")
    if not anahtar or durum not in ("elle", "atlandi"):
        abort(400)
    with closing(get_connection()) as conn:
        conn.execute("INSERT OR REPLACE INTO paylasim (anahtar, platform, metin, durum, zaman) VALUES (?, 'x', ?, ?, ?)",
                     (anahtar, metin_[:2000], durum, datetime.now().isoformat(timespec="seconds")))
        conn.commit()
    return jsonify({"tamam": True})
