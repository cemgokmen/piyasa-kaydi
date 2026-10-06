"""Ana sayfa, siyasetçilerin yüklü alımları, yöneticilerin toplu alımları, veri güncelliği."""

from piyasa.bicim import donem_metni, kisa_aralik, kisa_tutar
from piyasa.kayitlar import islem_hazirla
from piyasa.kurallar import GECERLI_KOD as GECERLI_TICKER
from piyasa.kurallar import TEMIZ, YUKLU_ALIM_ALT_SINIR, parti_bilgisi
from piyasa.web.sorgular.ortak import OZET_SUTUNLARI, baglanti, gun_once


def siyasetcilerin_yuklu_alimlari(conn, gun=365, limit=10):
    """
    Kongre üyelerinin en çok para yatırdığı hisseler. Tutar, bildirim
    aralıklarının toplamıdır; sıralama üst sınıra göre.
    """
    satirlar = conn.execute(
        f"""SELECT ticker, MAX(asset_name) AS sirket,
                  COUNT(*) AS adet,
                  COUNT(DISTINCT person_slug) AS kisi,
                  SUM(amount_min) AS alt, SUM(amount_max) AS ust,
                  SUM(CASE WHEN amount_min >= ? THEN 1 ELSE 0 END) AS yuklu,
                  GROUP_CONCAT(DISTINCT party) AS partiler,
                  MAX(transaction_date) AS son
           FROM transactions
           WHERE chamber IS NOT NULL AND action = 'buy' AND {GECERLI_TICKER}
             AND transaction_date >= ?
           GROUP BY ticker
           ORDER BY ust DESC, kisi DESC LIMIT ?""",
        (YUKLU_ALIM_ALT_SINIR, gun_once(gun), limit),
    ).fetchall()

    sonuc = []
    for s in satirlar:
        k = dict(s)
        k["tutar"] = kisa_aralik(k["alt"], k["ust"])
        k["partiler"] = [parti_bilgisi(p) for p in sorted((k["partiler"] or "").split(",")) if p]
        sonuc.append(k)
    return sonuc


def yoneticilerin_toplu_alimlari(conn, gun=30, limit=8):
    """
    Aynı hisseyi birden fazla yöneticinin kendi parasıyla alması. Tek bir
    alımdan daha anlamlı bir işaret kabul edilir.
    """
    return [
        dict(s, tutar=kisa_tutar(s["tutar"]))
        for s in conn.execute(
            f"""SELECT ticker, MAX(asset_name) AS sirket,
                      COUNT(DISTINCT person_slug) AS kisi, COUNT(*) AS adet,
                      SUM(amount_max) AS tutar
               FROM transactions
               WHERE chamber IS NULL AND action = 'buy' AND {TEMIZ}
                 AND {GECERLI_TICKER} AND disclosed_date >= ?
               GROUP BY ticker HAVING kisi >= 2
               ORDER BY kisi DESC, tutar DESC LIMIT ?""",
            (gun_once(gun), limit),
        )
    ]


def genel_bakis():
    with baglanti() as conn:
        yonetici = dict(conn.execute(
            f"SELECT {OZET_SUTUNLARI} FROM transactions "
            f"WHERE chamber IS NULL AND {TEMIZ} AND disclosed_date >= ?",
            (gun_once(30),),
        ).fetchone())

        siyaset = dict(conn.execute(
            f"SELECT {OZET_SUTUNLARI} FROM transactions "
            "WHERE chamber IS NOT NULL AND disclosed_date >= ?",
            (gun_once(365),),
        ).fetchone())

        son_siyaset = [
            islem_hazirla(s) for s in conn.execute(
                "SELECT * FROM transactions WHERE chamber IS NOT NULL "
                "ORDER BY disclosed_date DESC, amount_max DESC, id DESC LIMIT 8"
            )
        ]

        buyuk_alimlar = [
            islem_hazirla(s) for s in conn.execute(
                f"""SELECT * FROM transactions
                   WHERE chamber IS NULL AND action = 'buy' AND {TEMIZ}
                     AND {GECERLI_TICKER} AND disclosed_date >= ?
                   ORDER BY amount_max DESC LIMIT 8""",
                (gun_once(30),),
            )
        ]

        son_donem = conn.execute("SELECT MAX(donem) FROM holdings").fetchone()[0]
        fon_sayisi = conn.execute("SELECT COUNT(DISTINCT fon_slug) FROM holdings").fetchone()[0]

        return {
            "yonetici": yonetici,
            "siyaset": siyaset,
            "siyaset_yuklu": siyasetcilerin_yuklu_alimlari(conn, gun=365, limit=10),
            "yonetici_toplu": yoneticilerin_toplu_alimlari(conn),
            "son_siyaset": son_siyaset,
            "buyuk_alimlar": buyuk_alimlar,
            "fon_sayisi": fon_sayisi,
            "fon_donemi": donem_metni(son_donem) if son_donem else "",
            "guncel": conn.execute(
                f"SELECT MAX(disclosed_date) FROM transactions WHERE {TEMIZ}"
            ).fetchone()[0],
        }


def veri_guncelligi():
    """Alt bilgide gösterilen: her kaynağın en son kaydı."""
    with baglanti() as conn:
        def tek(sorgu):
            try:
                return conn.execute(sorgu).fetchone()[0]
            except Exception:
                return None
        return [
            ("Yönetici bildirimleri", tek(f"SELECT MAX(disclosed_date) FROM transactions WHERE chamber IS NULL AND {TEMIZ}")),
            ("Kongre bildirimleri", tek("SELECT MAX(disclosed_date) FROM transactions WHERE chamber IS NOT NULL")),
            ("Fon bildirimleri", tek("SELECT MAX(bildirim_tarihi) FROM holdings")),
            ("Emtia verileri", (tek("SELECT zaman FROM emtia_guncelleme WHERE anahtar = 'son'") or "")[:10] or None),
        ]
