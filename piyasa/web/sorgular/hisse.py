"""Hisse sayfası: yönetici, siyasetçi, fon ve Başkan pozisyonları; aylık işlem grafiği."""

from datetime import date

from piyasa import uyeler
from piyasa.analiz import cakisma
from piyasa.bicim import AYLAR, donem_metni, kisa_tutar
from piyasa.kayitlar import islem_hazirla
from piyasa.kurallar import TEMIZ
from piyasa.web.sorgular.ortak import FON_SON_DONEM, OZET_SUTUNLARI, baglanti


def _aylik_dagilim(conn, ticker, ay_sayisi=12):
    """Son ay_sayisi ayın alım/satım adetleri (grafik için)."""
    bugun = date.today()
    aylar = []
    y, m = bugun.year, bugun.month
    for _ in range(ay_sayisi):
        aylar.append(f"{y}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    aylar.reverse()

    sayilar = {
        (s["ay"], s["action"]): s["n"]
        for s in conn.execute(
            f"""SELECT substr(transaction_date, 1, 7) AS ay, action, COUNT(*) AS n
               FROM transactions WHERE ticker = ? AND {TEMIZ}
                 AND substr(transaction_date, 1, 7) >= ?
               GROUP BY ay, action""",
            (ticker, aylar[0]),
        )
    }
    cubuklar = [
        {"ay": AYLAR[int(a[5:]) - 1], "yil": a[:4],
         "alim": sayilar.get((a, "buy"), 0), "satim": sayilar.get((a, "sell"), 0)}
        for a in aylar
    ]
    en_cok = max([c["alim"] for c in cubuklar] + [c["satim"] for c in cubuklar] + [1])
    for c in cubuklar:
        c["alim_oran"] = c["alim"] / en_cok
        c["satim_oran"] = c["satim"] / en_cok
    return cubuklar if any(c["alim"] or c["satim"] for c in cubuklar) else []


def hisse(ticker):
    """Hisse sayfasının verisi; hiç kayıt yoksa None."""
    with baglanti() as conn:
        def ozet_al(kaynak):
            return dict(conn.execute(
                f"SELECT {OZET_SUTUNLARI} FROM transactions "
                f"WHERE ticker = ? AND {TEMIZ} AND {kaynak}",
                (ticker,),
            ).fetchone())

        yonetici = ozet_al("chamber IS NULL")
        siyaset = ozet_al("chamber IS NOT NULL")

        son_donem = conn.execute("SELECT MAX(donem) FROM holdings").fetchone()[0]
        fonlar = [
            dict(s, deger_kisa=kisa_tutar(s["deger"]))
            for s in conn.execute(
                f"""SELECT h.fon_adi, h.fon_slug, h.deger, h.adet, h.sirket_adi, h.donem
                   FROM holdings h JOIN ({FON_SON_DONEM}) s
                     ON s.fon_slug = h.fon_slug AND s.donem = h.donem
                   WHERE h.ticker = ? ORDER BY h.deger DESC""",
                (ticker,),
            )
        ]

        # Fonun önceki çeyrekte çıktığı hisseler de bağlantı alır; o yüzden
        # yalnız son çeyrek değil, herhangi bir 13F kaydı yeterli
        fon_kaydi = conn.execute(
            "SELECT sirket_adi FROM holdings WHERE ticker = ? ORDER BY donem DESC LIMIT 1",
            (ticker,),
        ).fetchone()

        # Başkan / Başkan Yardımcısının yıllık bildirimindeki pozisyonlar
        yurutme = [dict(s) for s in conn.execute(
            """SELECT kisi, SUM(alt) AS alt, SUM(ust) AS ust, MAX(COALESCE(sirket, ad)) AS ad
               FROM yurutme_varlik WHERE ticker = ? GROUP BY kisi""",
            (ticker,),
        )]

        if not (yonetici["adet"] or siyaset["adet"] or fon_kaydi or yurutme):
            return None

        sirket = conn.execute(
            "SELECT asset_name FROM transactions WHERE ticker = ? "
            "ORDER BY chamber IS NOT NULL LIMIT 1",
            (ticker,),
        ).fetchone()
        sirket_adi = (sirket["asset_name"] if sirket
                      else fon_kaydi["sirket_adi"] if fon_kaydi
                      else yurutme[0]["ad"] if yurutme else ticker)

        def islemler(kaynak):
            return cakisma.isaretle([islem_hazirla(s) for s in conn.execute(
                f"SELECT * FROM transactions WHERE ticker = ? AND {TEMIZ} AND {kaynak} "
                "ORDER BY disclosed_date DESC, id DESC LIMIT 100",
                (ticker,),
            )])

        return {
            "ticker": ticker,
            "sirket": sirket_adi,
            "yonetici": yonetici,
            "siyaset": siyaset,
            "yonetici_islemleri": islemler("chamber IS NULL"),
            "siyaset_islemleri": islemler("chamber IS NOT NULL"),
            "fonlar": fonlar[:15],
            "fon_sayisi": len(fonlar),
            "fon_toplam": kisa_tutar(sum(f["deger"] or 0 for f in fonlar)),
            "fon_donemi": donem_metni(son_donem) if son_donem else "",
            "cubuklar": _aylik_dagilim(conn, ticker),
            "yurutme": [dict(y, kisi_bilgi=uyeler.YURUTME_SLUG.get(y["kisi"])) for y in yurutme],
            "sektor": _sektor(conn, ticker),
            "benzerler": _benzerler(conn, ticker),
        }


def _sektor(conn, ticker):
    r = conn.execute("SELECT sektor, sic_aciklama FROM sirket WHERE ticker = ?", (ticker,)).fetchone()
    return dict(r) if r and r["sektor"] else None


def _benzerler(conn, ticker, adet=8):
    """Aynı sektörde son bir yılda en çok işlem bildirilen diğer hisseler."""
    sektor = _sektor(conn, ticker)
    if not sektor:
        return []
    return [dict(r) for r in conn.execute(
        f"""SELECT t.ticker, MAX(t.asset_name) AS sirket, COUNT(*) AS adet,
                   SUM(t.action = 'buy') AS alim, SUM(t.action = 'sell') AS satim
            FROM transactions t JOIN sirket s ON s.ticker = t.ticker
            WHERE s.sektor = ? AND t.ticker != ? AND {TEMIZ} AND t.disclosed_date >= date('now', '-365 day')
            GROUP BY t.ticker ORDER BY adet DESC LIMIT ?""",
        (sektor["sektor"], ticker, adet),
    )]
