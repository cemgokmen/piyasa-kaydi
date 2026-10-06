"""
Siyasetçilerin yatırım performansı: aldıkları hisseler sonrasında S&P 500'ü
yendi mi, sattıkları hisseler sonrasında endeksin gerisinde mi kaldı?

Aynı gün aynı hissede bölünmüş bildirimler (birden fazla lot) tek işlem
sayılır; her işlem eşit ağırlıklıdır (tutarlar zaten yalnızca aralık olarak
bilinir).
"""

from contextlib import closing

from piyasa.analiz import istatistik
from piyasa.veritabani import get_connection
from piyasa.web.bicim import parti_bilgisi

STANDART_UFUK = "90"
ASGARI_ALIM = 10      # sıralamaya girmek için en az bu kadar ölçülebilir alım


def _islem_getirileri(conn, kosul="", parametreler=(), ufuk=STANDART_UFUK):
    """
    Siyasetçi işlemleri ve getirileri, tekilleştirilmiş.
    Her satır: kişi, hisse, işlem, işlem ve bildirim bazlı fark.
    """
    return conn.execute(
        f"""SELECT t.person_slug, MAX(t.person) AS person, MAX(t.party) AS party,
                  MAX(t.state) AS state, t.ticker, t.action, t.transaction_date,
                  MAX(t.amount_max) AS tutar,
                  MAX(CASE WHEN g.baz = 'islem' THEN g.getiri - g.endeks END) AS fark_islem,
                  MAX(CASE WHEN g.baz = 'bildirim' THEN g.getiri - g.endeks END) AS fark_bildirim,
                  MAX(CASE WHEN g.baz = 'islem' THEN g.getiri END) AS getiri
           FROM transactions t
           JOIN islem_getirisi g ON g.islem_id = t.id AND g.ufuk = ?
           WHERE t.chamber IS NOT NULL {kosul}
           GROUP BY t.person_slug, t.ticker, t.action, t.transaction_date""",
        (ufuk, *parametreler),
    ).fetchall()


def siralama(ufuk=STANDART_UFUK):
    """Her siyasetçinin alım ve satım isabeti; en iyi alımcıdan en kötüye."""
    with closing(get_connection()) as conn:
        satirlar = _islem_getirileri(conn, ufuk=ufuk)

    kisiler = {}
    for s in satirlar:
        k = kisiler.setdefault(s["person_slug"], {
            "slug": s["person_slug"], "ad": s["person"], "parti": parti_bilgisi(s["party"]),
            "bolge": s["state"], "alim": [], "alim_bildirim": [], "satim": [],
        })
        if s["action"] == "buy":
            k["alim"].append(s["fark_islem"])
            k["alim_bildirim"].append(s["fark_bildirim"])
        else:
            k["satim"].append(s["fark_islem"])

    liste = []
    for k in kisiler.values():
        alim = istatistik.ozet(k["alim"])
        if alim["n"] < ASGARI_ALIM:
            continue
        satim = istatistik.ozet(k["satim"])
        liste.append({
            **{a: k[a] for a in ("slug", "ad", "parti", "bolge")},
            "alim": alim,
            "takipci": istatistik.ozet(k["alim_bildirim"]),
            # Satıştan sonra hisse endeksin gerisinde kaldıysa satış isabetli
            "satim_n": satim["n"],
            "satim_isabet": (1 - satim["yenme"]) if satim["n"] else None,
        })
    # Onlarca kişi aynı anda test ediliyor: tek tek "anlamlı" görünenlerin bir kısmı şanstır
    istatistik.holm([k["alim"] for k in liste])
    liste.sort(key=lambda k: k["alim"]["ortalama"], reverse=True)
    for i, k in enumerate(liste, start=1):
        k["sira"] = i
    return liste


def genel(ufuk=STANDART_UFUK):
    """Bütün siyasetçi alımlarının toplu sonucu (işlem ve bildirim bazlı)."""
    with closing(get_connection()) as conn:
        satirlar = _islem_getirileri(conn, "AND t.action = 'buy'", ufuk=ufuk)
    return {
        "islem": istatistik.ozet([s["fark_islem"] for s in satirlar]),
        "bildirim": istatistik.ozet([s["fark_bildirim"] for s in satirlar]),
    }


def kisi(slug):
    """Bir siyasetçinin performans özeti ve en iyi / en kötü alımları."""
    with closing(get_connection()) as conn:
        satirlar = [dict(s) for s in _islem_getirileri(conn, "AND t.person_slug = ?", (slug,))]
        bugune = [dict(s) for s in _islem_getirileri(conn, "AND t.person_slug = ? AND t.action = 'buy'",
                                                     (slug,), ufuk="bugun")]
    alimlar = [s for s in satirlar if s["action"] == "buy"]
    satimlar = [s for s in satirlar if s["action"] == "sell"]
    if not (alimlar or satimlar):
        return None
    sirali = sorted(bugune, key=lambda s: s["fark_islem"] or 0, reverse=True)
    satim = istatistik.ozet([s["fark_islem"] for s in satimlar])
    return {
        "alim": istatistik.ozet([s["fark_islem"] for s in alimlar]),
        "takipci": istatistik.ozet([s["fark_bildirim"] for s in alimlar]),
        "satim_n": satim["n"],
        "satim_isabet": (1 - satim["yenme"]) if satim["n"] else None,
        "en_iyi": sirali[:5],
        "en_kotu": list(reversed(sirali[-5:])) if len(sirali) > 5 else [],
    }
