"""
Sinyaller.

Üçlü onay: Aynı hisseyi şirket yöneticileri alıyor, Kongre üyeleri alıyor ve
takip edilen büyük fonlar pozisyonunu artırıyor mu? Üç kaynağı birlikte
tutan bir site olduğumuz için bu kesişimi gösterebiliyoruz.

Sinyal başarısı: Geçmişte bu sinyallerin ardından hisseler S&P 500'ü yendi
mi? Giriş, bildirimin kamuya açıklandığı gündür — sinyali izleyen birinin
gerçekte yakalayabileceği getiri.
"""

import threading
import time
from collections import defaultdict
from contextlib import closing
from datetime import date, timedelta

from piyasa.analiz import cakisma, istatistik
from piyasa.analiz.getiri import UFUKLAR
from piyasa.veritabani import get_connection
from piyasa.web.bicim import YUKLU_ALIM_ALT_SINIR, kisa_aralik, kisa_tutar, parti_bilgisi

TEMIZ = "(t.suspect IS NULL OR t.suspect = 0)"
GECERLI = "t.ticker NOT IN ('NONE', 'N/A', 'NA', '')"

YONETICI_PENCERE = 90      # gün: yönetici alımları
SIYASET_PENCERE = 180      # gün: siyasetçi alımları
KUME_PENCERE = 30          # gün: küme alımında alımlar arası en fazla süre

_kilit = threading.Lock()


def gun_once(gun):
    return (date.today() - timedelta(days=gun)).isoformat()


# ---------------------------------------------------------------------------
# ÜÇLÜ ONAY
# ---------------------------------------------------------------------------

def _fon_degisimleri(conn):
    """Son iki çeyrekte, aynı fonlar içinde hisse başına adet değişimi."""
    donemler = [s[0] for s in conn.execute(
        "SELECT DISTINCT donem FROM holdings ORDER BY donem DESC LIMIT 2")]
    if len(donemler) < 2:
        return {}, None
    son, onceki = donemler
    satirlar = conn.execute(
        """SELECT ticker, fon_slug,
                  SUM(CASE WHEN donem = ? THEN adet ELSE 0 END) AS simdi,
                  SUM(CASE WHEN donem = ? THEN adet ELSE 0 END) AS once
           FROM holdings
           WHERE donem IN (?, ?) AND ticker IS NOT NULL
             AND fon_slug IN (SELECT fon_slug FROM holdings WHERE donem = ?
                              INTERSECT SELECT fon_slug FROM holdings WHERE donem = ?)
           GROUP BY ticker, fon_slug""",
        (son, onceki, son, onceki, son, onceki),
    ).fetchall()

    fonlar = defaultdict(lambda: {"artiran": 0, "azaltan": 0, "deger": 0})
    for s in satirlar:
        if s["simdi"] > s["once"] * 1.001:
            fonlar[s["ticker"]]["artiran"] += 1
        elif s["simdi"] < s["once"] * 0.999:
            fonlar[s["ticker"]]["azaltan"] += 1
    return fonlar, son


_onay_onbellek = {"zaman": 0, "veri": None}


def uclu_onay():
    """Kaynak sayısına göre sıralı hisse listesi (en az iki kaynak). 10 dk önbellekli."""
    with _kilit:
        if _onay_onbellek["veri"] and time.time() - _onay_onbellek["zaman"] < 600:
            return _onay_onbellek["veri"]
    veri = _uclu_onay_hesapla()
    with _kilit:
        _onay_onbellek.update(zaman=time.time(), veri=veri)
    return veri


def _uclu_onay_hesapla():
    with closing(get_connection()) as conn:
        yonetici = {s["ticker"]: dict(s) for s in conn.execute(
            f"""SELECT t.ticker, MAX(t.asset_name) AS sirket, COUNT(DISTINCT t.person_slug) AS kisi,
                      SUM(t.amount_max) AS tutar, MAX(t.disclosed_date) AS son
               FROM transactions t
               WHERE t.chamber IS NULL AND t.action = 'buy' AND {TEMIZ} AND {GECERLI}
                 AND t.disclosed_date >= ?
               GROUP BY t.ticker""",
            (gun_once(YONETICI_PENCERE),),
        )}
        siyaset = {s["ticker"]: dict(s) for s in conn.execute(
            f"""SELECT t.ticker, MAX(t.asset_name) AS sirket, COUNT(DISTINCT t.person_slug) AS kisi,
                      SUM(t.amount_min) AS alt, SUM(t.amount_max) AS ust,
                      GROUP_CONCAT(DISTINCT t.party) AS partiler, MAX(t.transaction_date) AS son
               FROM transactions t
               WHERE t.chamber IS NOT NULL AND t.action = 'buy' AND {GECERLI}
                 AND t.transaction_date >= ?
               GROUP BY t.ticker""",
            (gun_once(SIYASET_PENCERE),),
        )}
        fonlar, fon_donemi = _fon_degisimleri(conn)

    hisseler = set(yonetici) | set(siyaset) | {t for t, f in fonlar.items() if f["artiran"] > f["azaltan"]}
    liste = []
    for t in hisseler:
        y, s, f = yonetici.get(t), siyaset.get(t), fonlar.get(t)
        fon_artis = bool(f and f["artiran"] > f["azaltan"])
        kaynak = bool(y) + bool(s) + fon_artis
        if kaynak < 2:
            continue
        liste.append({
            "ticker": t,
            "sirket": (y or s or {}).get("sirket") or "",
            "kaynak": kaynak,
            "yonetici": y and {"kisi": y["kisi"], "tutar": kisa_tutar(y["tutar"]), "son": y["son"]},
            "siyaset": s and {"kisi": s["kisi"], "tutar": kisa_aralik(s["alt"], s["ust"]), "son": s["son"],
                              "partiler": [parti_bilgisi(p) for p in sorted((s["partiler"] or "").split(",")) if p]},
            "fon": f if fon_artis else None,
        })
    liste.sort(key=lambda h: (h["kaynak"], (h["yonetici"] or {}).get("kisi", 0) + (h["siyaset"] or {}).get("kisi", 0)),
               reverse=True)
    return {"liste": liste, "fon_donemi": fon_donemi,
            "pencereler": {"yonetici": YONETICI_PENCERE, "siyaset": SIYASET_PENCERE}}


# ---------------------------------------------------------------------------
# SİNYAL BAŞARISI
# ---------------------------------------------------------------------------

SINYALLER = [
    ("siyaset", "Siyasetçi alımları", "Bir Kongre üyesinin bildirdiği her hisse alımı."),
    ("yuklu", "Yüklü siyasetçi alımları", "Alt sınırı 50.000 doları aşan siyasetçi alımları."),
    ("cakisma", "Çıkar çatışmalı alımlar", "Üyenin komitesinin denetlediği sektörden yaptığı alımlar."),
    ("yonetici", "Yönetici alımları", "Şirket yöneticilerinin kendi şirketlerinden açık piyasada yaptığı alımlar."),
    ("kume", "Küme alımları", f"Aynı hisseyi {KUME_PENCERE} gün içinde en az iki farklı yöneticinin alması."),
]


def _olaylar(conn):
    """Her sinyal için (işlem id) listesi; aynı kişi-hisse-gün tek olay sayılır."""
    siyaset = conn.execute(
        f"""SELECT MIN(t.id) AS id, MAX(t.amount_min) AS alt FROM transactions t
           WHERE t.chamber IS NOT NULL AND t.action = 'buy' AND {GECERLI}
           GROUP BY t.person_slug, t.ticker, t.disclosed_date"""
    ).fetchall()
    cakisanlar = cakisma.cakisan_islemler()

    yonetici = conn.execute(
        f"""SELECT MIN(t.id) AS id, t.ticker, t.person_slug, t.disclosed_date
           FROM transactions t
           WHERE t.chamber IS NULL AND t.action = 'buy' AND {TEMIZ} AND {GECERLI}
           GROUP BY t.person_slug, t.ticker, t.disclosed_date
           ORDER BY t.ticker, t.disclosed_date"""
    ).fetchall()

    # Küme: hissede 30 gün içinde ikinci farklı alıcının bildirildiği gün bir olaydır;
    # aynı hissede sonraki 30 gün yeni olay sayılmaz
    kume = []
    hisseye_gore = defaultdict(list)
    for s in yonetici:
        hisseye_gore[s["ticker"]].append(s)
    for alimlar in hisseye_gore.values():
        son_olay = None
        for i, s in enumerate(alimlar):
            gun = date.fromisoformat(s["disclosed_date"][:10])
            if son_olay and (gun - son_olay).days < KUME_PENCERE:
                continue
            onceki_kisiler = {
                a["person_slug"] for a in alimlar[:i]
                if (gun - date.fromisoformat(a["disclosed_date"][:10])).days <= KUME_PENCERE
            }
            if onceki_kisiler - {s["person_slug"]}:
                kume.append(s["id"])
                son_olay = gun

    return {
        "siyaset": [s["id"] for s in siyaset],
        "yuklu": [s["id"] for s in siyaset if (s["alt"] or 0) >= YUKLU_ALIM_ALT_SINIR],
        "cakisma": [s["id"] for s in siyaset if s["id"] in cakisanlar],
        "yonetici": [s["id"] for s in yonetici],
        "kume": kume,
    }


_onbellek = {"zaman": 0, "veri": None}


def basari():
    """Her sinyal ve süre için istatistik özeti. 1 saat önbellekli."""
    with _kilit:
        if _onbellek["veri"] and time.time() - _onbellek["zaman"] < 3600:
            return _onbellek["veri"]

    with closing(get_connection()) as conn:
        olaylar = _olaylar(conn)
        farklar = defaultdict(dict)
        for s in conn.execute(
            "SELECT islem_id, ufuk, getiri - endeks AS fark FROM islem_getirisi WHERE baz = 'bildirim'"
        ):
            farklar[s["islem_id"]][s["ufuk"]] = s["fark"]

    tablo = []
    for kod, ad, aciklama in SINYALLER:
        idler = olaylar[kod]
        tablo.append({
            "kod": kod, "ad": ad, "aciklama": aciklama, "olay": len(idler),
            "ufuklar": {u: istatistik.ozet([farklar[i].get(u) for i in idler if u in farklar.get(i, {})])
                        for u in UFUKLAR},
        })

    # Sinyal × süre sayısı kadar test yapıldı: şans eseri anlamlı görünenleri ele
    istatistik.holm([o for satir in tablo for o in satir["ufuklar"].values()])

    with _kilit:
        _onbellek.update(zaman=time.time(), veri=tablo)
    return tablo
