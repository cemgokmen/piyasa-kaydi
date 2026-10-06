"""
Sitenin veritabanı sorguları, sayfalara göre modüllere ayrılmıştır.

Sayfa fonksiyonları (rotalar.py) SQL bilmez; ihtiyaç duydukları veriyi
buradan alır. Her fonksiyon kendi bağlantısını açıp kapatır.

    ortak     sabitler, bağlantı, ortak SQL parçaları
    islemler  işlem listesi
    genel     ana sayfa ve alt bilgi
    siyaset   siyasetçiler
    hisse     hisse sayfası
    kisi      kişi sayfası
    fonlar    fon listesi ve fon sayfası
"""

from piyasa.web.sorgular.fonlar import (  # noqa: F401
    DILIM_RENKLERI,
    fon,
    fonlar,
    pasta_dilimleri,
)
from piyasa.web.sorgular.genel import (  # noqa: F401
    genel_bakis,
    siyasetcilerin_yuklu_alimlari,
    veri_guncelligi,
    yoneticilerin_toplu_alimlari,
)
from piyasa.web.sorgular.hisse import (  # noqa: F401
    hisse,
)
from piyasa.web.sorgular.islemler import (  # noqa: F401
    islem_listesi,
)
from piyasa.web.sorgular.kisi import (  # noqa: F401
    kisi,
)
from piyasa.web.sorgular.ortak import (  # noqa: F401
    DONEMLER,
    FON_SON_DONEM,
    KAYNAKLAR,
    OZET_SUTUNLARI,
    SAYFA_BOYUTU,
    SIRALAMALAR,
    baglanti,
    gun_once,
)
from piyasa.web.sorgular.siyaset import (  # noqa: F401
    siyasetciler,
)
