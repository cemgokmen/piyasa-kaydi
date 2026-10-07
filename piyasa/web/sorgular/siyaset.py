"""Siyasetçiler sayfası: üyeler, parti dağılımı, öne çıkan alımlar."""

from piyasa import uyeler
from piyasa.bicim import kisa_aralik
from piyasa.kurallar import STOCK_ACT_GUN, YUKLU_ALIM_ALT_SINIR, parti_bilgisi
from piyasa.web.sorgular.genel import siyasetcilerin_yuklu_alimlari
from piyasa.web.sorgular.ortak import MECLISLER, OZET_SUTUNLARI, baglanti


def siyasetciler(parti="", meclis=""):
    kosul = "chamber IS NOT NULL" + (" AND party = ?" if parti else "") + (" AND chamber = ?" if meclis else "")
    parametreler = tuple(x for x in (parti, MECLISLER.get(meclis)) if x)

    with baglanti() as conn:
        kisiler = []
        for s in conn.execute(
            f"""SELECT person, person_slug, MAX(party) AS party, MAX(state) AS state, MAX(chamber) AS chamber,
                      COUNT(*) AS adet,
                      SUM(CASE WHEN action='buy' THEN 1 ELSE 0 END) AS alim,
                      SUM(CASE WHEN action='sell' THEN 1 ELSE 0 END) AS satim,
                      SUM(amount_min) AS alt, SUM(amount_max) AS ust,
                      SUM(CASE WHEN action='buy' AND amount_min >= ? THEN 1 ELSE 0 END) AS yuklu,
                      MAX(transaction_date) AS son_islem,
                      SUM(CASE WHEN julianday(disclosed_date) - julianday(transaction_date) > ?
                               THEN 1 ELSE 0 END) AS gec
               FROM transactions WHERE {kosul}
               GROUP BY person_slug ORDER BY ust DESC""",
            (YUKLU_ALIM_ALT_SINIR, STOCK_ACT_GUN, *parametreler),
        ):
            k = dict(s)
            k["parti"] = parti_bilgisi(k["party"])
            k["hacim"] = kisa_aralik(k["alt"], k["ust"])
            k["foto"] = uyeler.foto(k["person_slug"])
            kisiler.append(k)

        meclis_sayilari = {
            s["chamber"]: s["n"] for s in conn.execute(
                "SELECT chamber, COUNT(DISTINCT person_slug) AS n FROM transactions "
                "WHERE chamber IS NOT NULL GROUP BY chamber")
        }
        parti_sayilari = {
            s["party"]: s["n"] for s in conn.execute(
                "SELECT party, COUNT(DISTINCT person_slug) AS n FROM transactions "
                "WHERE chamber IS NOT NULL GROUP BY party"
            )
        }
        ozet = dict(conn.execute(
            f"SELECT {OZET_SUTUNLARI}, MIN(disclosed_date) AS ilk "
            "FROM transactions WHERE chamber IS NOT NULL"
        ).fetchone())

        yuklu = siyasetcilerin_yuklu_alimlari(conn, gun=365, limit=12)

    return {"kisiler": kisiler, "parti_sayilari": parti_sayilari,
            "meclis_sayilari": {k: meclis_sayilari.get(ad, 0) for k, ad in MECLISLER.items()},
            "ozet": ozet, "yuklu": yuklu,
            "onemliler": uyeler.onemli_siyasetciler(),
            "yurutme": [dict(y, parti_bilgisi=parti_bilgisi(y["parti"])) for y in uyeler.YURUTME]}
