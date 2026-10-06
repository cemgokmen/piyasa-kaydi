"""Kişi (yönetici ya da siyasetçi) sayfası."""

from piyasa import uyeler
from piyasa.analiz import cakisma
from piyasa.bicim import kisa_aralik, kisa_tutar
from piyasa.kayitlar import islem_hazirla
from piyasa.kurallar import TEMIZ, parti_bilgisi
from piyasa.web.sorgular.ortak import OZET_SUTUNLARI, baglanti


def kisi(slug):
    """Kişi sayfasının verisi; kayıt yoksa None."""
    with baglanti() as conn:
        ozet = dict(conn.execute(
            f"""SELECT {OZET_SUTUNLARI},
                 COUNT(DISTINCT ticker) AS hisse_adet,
                 AVG(julianday(disclosed_date) - julianday(transaction_date)) AS ort_gecikme,
                 MAX(julianday(disclosed_date) - julianday(transaction_date)) AS max_gecikme
               FROM transactions WHERE person_slug = ? AND {TEMIZ}""",
            (slug,),
        ).fetchone())
        if not ozet["adet"]:
            return None

        kimlik = dict(conn.execute(
            "SELECT person, job_title, company, chamber, state, party "
            "FROM transactions WHERE person_slug = ? ORDER BY disclosed_date DESC LIMIT 1",
            (slug,),
        ).fetchone())

        hisseler = [
            dict(s, hacim=kisa_aralik(s["alt"], s["ust"]))
            for s in conn.execute(
                f"""SELECT ticker, COUNT(*) AS adet,
                          SUM(amount_min) AS alt, SUM(amount_max) AS ust,
                          SUM(CASE WHEN action='buy' THEN 1 ELSE 0 END) AS alim,
                          SUM(CASE WHEN action='sell' THEN 1 ELSE 0 END) AS satim
                   FROM transactions WHERE person_slug = ? AND {TEMIZ}
                   GROUP BY ticker ORDER BY ust DESC, adet DESC LIMIT 12""",
                (slug,),
            )
        ]

        islemler = cakisma.isaretle([islem_hazirla(s) for s in conn.execute(
            f"SELECT * FROM transactions WHERE person_slug = ? AND {TEMIZ} "
            "ORDER BY disclosed_date DESC, id DESC LIMIT 200",
            (slug,),
        )])

    siyasetci = bool(kimlik.get("chamber"))
    return {
        "kimlik": kimlik,
        "foto": uyeler.foto(slug) if siyasetci else None,
        "gorev": uyeler.gorev(slug) if siyasetci else None,
        "siyasetci": siyasetci,
        "parti": parti_bilgisi(kimlik.get("party")),
        "ozet": ozet,
        "ort_gecikme": round(ozet["ort_gecikme"] or 0),
        "max_gecikme": round(ozet["max_gecikme"] or 0),
        "gec_sayisi": sum(1 for i in islemler if i["gec"]),
        "alim_tutar": (kisa_aralik(ozet["alim_alt"], ozet["alim_tutar"]) if siyasetci
                       else kisa_tutar(ozet["alim_tutar"])),
        "satim_tutar": (kisa_aralik(ozet["satim_alt"], ozet["satim_tutar"]) if siyasetci
                        else kisa_tutar(ozet["satim_tutar"])),
        "hisseler": hisseler,
        "islemler": islemler,
    }
