"""
Başkan ve Başkan Yardımcısının yıllık bildiriminden ayıklanan hisse
portföyü ve işlemleri (bkz. piyasa/toplama/oge_yillik.py).
"""

from contextlib import closing

from piyasa.veritabani import get_connection


def portfoy(kisi):
    """Hisse/fon pozisyonları (bildirilen değer aralığıyla) ve elenen kalemlerin özeti."""
    with closing(get_connection()) as conn:
        pozisyonlar = [dict(s) for s in conn.execute(
            """SELECT ticker, MAX(COALESCE(sirket, ad)) AS ad, COUNT(*) AS kalem, COUNT(DISTINCT hesap) AS hesap,
                      SUM(alt) AS alt, SUM(ust) AS ust
               FROM yurutme_varlik WHERE kisi = ? AND ticker IS NOT NULL
               GROUP BY ticker ORDER BY SUM(alt + ust) DESC""",
            (kisi,),
        )]
        elenen = dict(conn.execute(
            """SELECT COUNT(*) AS kalem, SUM(alt) AS alt, SUM(ust) AS ust,
                      SUM(eslesme = 'tahvil_hesabi') AS tahvil_hesabi
               FROM yurutme_varlik WHERE kisi = ? AND ticker IS NULL""",
            (kisi,),
        ).fetchone())
        rapor = conn.execute(
            "SELECT r.adres, r.sayfa, b.tarih FROM yurutme_rapor r "
            "JOIN yurutme_bildirimi b ON b.adres = r.adres WHERE r.kisi = ?",
            (kisi,),
        ).fetchone()

    if not pozisyonlar:
        return None

    toplam = sum((p["alt"] + p["ust"]) / 2 for p in pozisyonlar)
    for p in pozisyonlar:
        p["deger"] = (p["alt"] + p["ust"]) / 2          # pasta grafiği için aralık ortası
        p["pay"] = p["deger"] / toplam if toplam else 0
    return {
        "pozisyonlar": pozisyonlar,
        "sayi": len(pozisyonlar),
        "alt": sum(p["alt"] for p in pozisyonlar),
        "ust": sum(p["ust"] for p in pozisyonlar),
        "elenen": elenen,
        "rapor": dict(rapor) if rapor else None,
    }


def islemler(kisi, limit=150):
    """Yılın hisse/fon işlemleri: özet, en çok alınan/satılanlar, son işlemler."""
    with closing(get_connection()) as conn:
        ozet = dict(conn.execute(
            """SELECT COUNT(*) AS toplam, SUM(ticker IS NOT NULL) AS hisse,
                      SUM(ticker IS NOT NULL AND islem = 'buy') AS alim,
                      SUM(ticker IS NOT NULL AND islem = 'sell') AS satim,
                      SUM(CASE WHEN ticker IS NOT NULL AND islem = 'buy' THEN alt END) AS alim_alt,
                      SUM(CASE WHEN ticker IS NOT NULL AND islem = 'buy' THEN ust END) AS alim_ust,
                      SUM(CASE WHEN ticker IS NOT NULL AND islem = 'sell' THEN alt END) AS satim_alt,
                      SUM(CASE WHEN ticker IS NOT NULL AND islem = 'sell' THEN ust END) AS satim_ust,
                      MIN(tarih) AS ilk, MAX(tarih) AS son
               FROM yurutme_islem WHERE kisi = ?""",
            (kisi,),
        ).fetchone())
        if not ozet["toplam"]:
            return None

        def en_cok(islem):
            return [dict(s) for s in conn.execute(
                """SELECT ticker, MAX(COALESCE(sirket, ad)) AS ad, COUNT(*) AS adet, SUM(alt) AS alt, SUM(ust) AS ust
                   FROM yurutme_islem WHERE kisi = ? AND ticker IS NOT NULL AND islem = ?
                   GROUP BY ticker ORDER BY SUM(alt + ust) DESC, adet DESC LIMIT 10""",
                (kisi, islem),
            )]

        son = [dict(s) for s in conn.execute(
            """SELECT ticker, COALESCE(sirket, ad) AS ad, islem, tarih, alt, ust, hesap FROM yurutme_islem
               WHERE kisi = ? AND ticker IS NOT NULL ORDER BY tarih DESC, ust DESC LIMIT ?""",
            (kisi, limit),
        )]
        return {"ozet": ozet, "en_cok_alinan": en_cok("buy"), "en_cok_satilan": en_cok("sell"), "son": son}
