"""
Süreli bellek önbelleği.

    @sureli(60 * 10)
    def pahali_hesap(a, b): ...

    pahali_hesap.temizle()      # bütün kayıtları siler

Aynı argümanlarla çağrı süre dolana kadar önbellekten döner (None dahil).
hatada_eskisi=True ise hesap hata verdiğinde, varsa süresi geçmiş son sonuç
döner; yoksa hata yükselir. İş parçacığı güvenlidir.
"""

import functools
import threading
import time


def sureli(saniye, hatada_eskisi=False):
    def sarmala(fonksiyon):
        kayitlar = {}
        kilit = threading.Lock()

        @functools.wraps(fonksiyon)
        def sarili(*args, **kwargs):
            anahtar = (args, tuple(sorted(kwargs.items())))
            simdi = time.monotonic()
            with kilit:
                kayit = kayitlar.get(anahtar)
            if kayit and simdi - kayit[0] < saniye:
                return kayit[1]
            try:
                sonuc = fonksiyon(*args, **kwargs)
            except Exception:
                if hatada_eskisi and kayit:
                    return kayit[1]
                raise
            with kilit:
                kayitlar[anahtar] = (simdi, sonuc)
            return sonuc

        def temizle():
            with kilit:
                kayitlar.clear()

        sarili.temizle = temizle
        return sarili

    return sarmala
