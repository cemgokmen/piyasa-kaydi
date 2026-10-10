"""
Hazır sayfa önbelleği: aynı adres 2 dakika içinde yeniden istenirse sayfa
baştan hazırlanmaz, bellekteki HTML döner.

Sayfalar kişiye göre değişmez (tema seçimi tarayıcıda yapılır) ve veri günde
bir güncellenir; bu yüzden kısa süreli önbellek güvenlidir. Ani ziyaretçi
akınında (ör. bir paylaşım yayıldığında) sunucunun yükünü kat kat azaltır.

Önbellekte olmayan bir sayfaya aynı anda çok istek gelirse sayfayı yalnızca
ilk istek hazırlar, diğerleri onun sonucunu bekler (aynı sayfanın onlarca kez
birden hazırlanıp sunucuyu kilitlemesi önlenir).

Yalnızca başarılı (200) HTML GET cevapları tutulur. /api/ adresleri kendi
önbelleklerini kullanır, dahil edilmez. Arama gibi her adresin ayrı kaydı
olduğu için kayıt sayısı sınırlıdır; dolunca en eskisi silinir.
"""

import threading
import time
from collections import OrderedDict

from flask import g, request

SURE = 120
EN_COK = 500


def kaydet(app, sure=SURE, en_cok=EN_COK):
    kayitlar = OrderedDict()
    kilit = threading.Lock()
    hazirlananlar = {}           # adres → o sayfayı hazırlayan isteğin kilidi

    def uygun():
        return (request.method == "GET" and not app.config.get("TESTING")
                and request.endpoint not in (None, "static") and not request.path.startswith(("/api/", "/paylasim")))

    @app.before_request
    def onbellekten():
        if not uygun():
            return None
        anahtar = request.full_path

        def hazir():
            with kilit:
                kayit = kayitlar.get(anahtar)
                if kayit and time.monotonic() - kayit[0] < sure:
                    kayitlar.move_to_end(anahtar)
                    g.onbellekten = True
                    return app.response_class(kayit[1], status=200, mimetype="text/html",
                                              headers={"X-Onbellek": "hit"})
            return None

        cevap = hazir()
        if cevap:
            return cevap
        with kilit:
            sayfa_kilidi = hazirlananlar.setdefault(anahtar, threading.Lock())
        # Sayfayı başka bir istek hazırlıyorsa bitirmesini bekle (en çok 30 sn), sonra önbellekten ver
        if sayfa_kilidi.acquire(timeout=30):
            g.sayfa_kilidi = sayfa_kilidi
            return hazir()
        return None

    @app.teardown_request
    def kilidi_birak(_hata=None):
        sayfa_kilidi = g.pop("sayfa_kilidi", None)
        if sayfa_kilidi:
            with kilit:
                hazirlananlar.pop(request.full_path, None)
            sayfa_kilidi.release()

    @app.after_request
    def onbellege(cevap):
        if (uygun() and not g.get("onbellekten") and cevap.status_code == 200
                and cevap.mimetype == "text/html" and not cevap.direct_passthrough):
            with kilit:
                kayitlar[request.full_path] = (time.monotonic(), cevap.get_data())
                kayitlar.move_to_end(request.full_path)
                while len(kayitlar) > en_cok:
                    kayitlar.popitem(last=False)
        return cevap

    def temizle():
        with kilit:
            kayitlar.clear()

    app.extensions["sayfa_onbellegi"] = temizle
