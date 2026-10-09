"""Sorguların ortak parçaları: sabitler, bağlantı, sık kullanılan SQL."""

from contextlib import closing
from datetime import date, timedelta

from piyasa.veritabani import get_connection

SAYFA_BOYUTU = 50


DONEMLER = {
    "7": ("Son 7 gün", 7),
    "30": ("Son 30 gün", 30),
    "90": ("Son 3 ay", 90),
    "365": ("Son 1 yıl", 365),
}


SIRALAMALAR = {
    "yeni": ("En yeni bildirim", "disclosed_date DESC, id DESC"),
    "tutar": ("En büyük tutar", "amount_max DESC, id DESC"),
    "gecikme": ("En geç bildirilen",
                "julianday(disclosed_date) - julianday(transaction_date) DESC, id DESC"),
}


# Kongre kayıtlarında chamber dolu, Form 4 kayıtlarında boş.
KAYNAKLAR = {
    "hepsi": ("Herkes", None),
    "yonetici": ("Şirket yöneticileri", "chamber IS NULL"),
    "siyasetci": ("Siyasetçiler", "chamber IS NOT NULL"),
    "meclis": ("Temsilciler Meclisi", "chamber = 'Temsilciler Meclisi'"),
    "senato": ("Senato", "chamber = 'Senato'"),
}
SIYASET_KAYNAKLARI = ("siyasetci", "meclis", "senato")

# Yönetici işlemlerinde role göre süzgeç. Unvanlar Form 4'teki İngilizce haliyle saklanır.
_UNVAN = "LOWER(COALESCE(job_title, ''))"
UST_YONETIM = (
    f"({_UNVAN} LIKE '%ceo%' OR {_UNVAN} LIKE '%chief executive%' OR {_UNVAN} LIKE '%cfo%' "
    f"OR {_UNVAN} LIKE '%chief financial%' OR {_UNVAN} LIKE '%coo%' OR {_UNVAN} LIKE '%chief operating%' "
    f"OR {_UNVAN} LIKE '%chair%' OR ({_UNVAN} LIKE '%president%' AND {_UNVAN} NOT LIKE '%vice%'))"
)
ROLLER = {
    "hepsi": ("Bütün roller", None),
    "ust": ("Üst yönetim (CEO, CFO, başkan)", f"chamber IS NULL AND {UST_YONETIM}"),
    "kurul": ("Yönetim kurulu üyeleri", f"chamber IS NULL AND NOT {UST_YONETIM} AND "
                                        f"({_UNVAN} = 'yönetim kurulu üyesi' OR {_UNVAN} LIKE '%director%')"),
    "ortak": ("Büyük ortaklar (%10 üzeri)", "chamber IS NULL AND job_title = '%10 üzeri ortak'"),
}

# Siyasetçiler sayfasındaki meclis seçimi
MECLISLER = {"meclis": "Temsilciler Meclisi", "senato": "Senato"}


OZET_SUTUNLARI = """
    COUNT(*) AS adet,
    COUNT(DISTINCT person_slug) AS kisi,
    SUM(CASE WHEN action='buy' THEN 1 ELSE 0 END) AS alim,
    SUM(CASE WHEN action='sell' THEN 1 ELSE 0 END) AS satim,
    SUM(CASE WHEN action='buy' THEN amount_max ELSE 0 END) AS alim_tutar,
    SUM(CASE WHEN action='sell' THEN amount_max ELSE 0 END) AS satim_tutar,
    SUM(CASE WHEN action='buy' THEN amount_min ELSE 0 END) AS alim_alt,
    SUM(CASE WHEN action='sell' THEN amount_min ELSE 0 END) AS satim_alt
"""


def baglanti():
    return closing(get_connection())


# Her fonun kendi son çeyreği. Fonlar bildirimlerini farklı günlerde yapar;
# tek bir "en son çeyrek" ile süzmek, geciken fonları listeden düşürür.
FON_SON_DONEM = "SELECT fon_slug, MAX(donem) AS donem FROM holdings GROUP BY fon_slug"


def gun_once(gun):
    return (date.today() - timedelta(days=gun)).isoformat()
