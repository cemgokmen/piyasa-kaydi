"""
Sitenin veritabanı sorguları.

Sayfa fonksiyonları (rotalar.py) SQL bilmez; ihtiyaç duydukları veriyi
buradaki fonksiyonlardan alır. Her fonksiyon kendi bağlantısını açıp kapatır.
"""

from contextlib import closing
from datetime import date, timedelta

from piyasa.analiz import cakisma
from piyasa.bicim import AYLAR, donem_metni, kisa_aralik, kisa_tutar
from piyasa.kayitlar import islem_hazirla
from piyasa.kurallar import GECERLI_KOD as GECERLI_TICKER
from piyasa.kurallar import STOCK_ACT_GUN, TEMIZ, YUKLU_ALIM_ALT_SINIR, parti_bilgisi
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
}

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


def gun_once(gun):
    return (date.today() - timedelta(days=gun)).isoformat()


# ---------------------------------------------------------------------------
# İŞLEM LİSTESİ
# ---------------------------------------------------------------------------

def _filtre(arama, islem, donem, kaynak):
    kosullar = [TEMIZ]
    parametreler = []

    if islem in ("buy", "sell"):
        kosullar.append("action = ?")
        parametreler.append(islem)

    kaynak_kosulu = KAYNAKLAR[kaynak][1]
    if kaynak_kosulu:
        kosullar.append(kaynak_kosulu)

    kosullar.append("disclosed_date >= ?")
    parametreler.append(gun_once(DONEMLER[donem][1]))

    if arama:
        kosullar.append(
            "(ticker LIKE ? OR person LIKE ? OR company LIKE ? OR asset_name LIKE ?)"
        )
        parametreler.extend([f"%{arama}%"] * 4)

    return " WHERE " + " AND ".join(kosullar), parametreler


def islem_listesi(arama, islem, donem, kaynak, sira, sayfa):
    """Filtreli, sayfalı işlem listesi ve filtrenin özeti."""
    where, parametreler = _filtre(arama, islem, donem, kaynak)
    with baglanti() as conn:
        ozet = dict(conn.execute(
            f"SELECT {OZET_SUTUNLARI} FROM transactions{where}", parametreler
        ).fetchone())
        satirlar = conn.execute(
            f"SELECT * FROM transactions{where} ORDER BY {SIRALAMALAR[sira][1]} "
            "LIMIT ? OFFSET ?",
            parametreler + [SAYFA_BOYUTU, (sayfa - 1) * SAYFA_BOYUTU],
        ).fetchall()
    return cakisma.isaretle([islem_hazirla(s) for s in satirlar]), ozet


# ---------------------------------------------------------------------------
# GENEL BAKIŞ
# ---------------------------------------------------------------------------

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
        fon_sayisi = conn.execute(
            "SELECT COUNT(DISTINCT fon_slug) FROM holdings WHERE donem = ?", (son_donem,)
        ).fetchone()[0] if son_donem else 0

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


# ---------------------------------------------------------------------------
# SİYASETÇİLER
# ---------------------------------------------------------------------------

def siyasetciler(parti=""):
    kosul = "chamber IS NOT NULL" + (" AND party = ?" if parti else "")
    parametreler = (parti,) if parti else ()

    with baglanti() as conn:
        kisiler = []
        for s in conn.execute(
            f"""SELECT person, person_slug, MAX(party) AS party, MAX(state) AS state,
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
            kisiler.append(k)

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
            "ozet": ozet, "yuklu": yuklu}


# ---------------------------------------------------------------------------
# HİSSE
# ---------------------------------------------------------------------------

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
                "SELECT fon_adi, fon_slug, deger, adet, sirket_adi FROM holdings "
                "WHERE ticker = ? AND donem = ? ORDER BY deger DESC",
                (ticker, son_donem),
            )
        ] if son_donem else []

        # Fonun önceki çeyrekte çıktığı hisseler de bağlantı alır; o yüzden
        # yalnız son çeyrek değil, herhangi bir 13F kaydı yeterli
        fon_kaydi = conn.execute(
            "SELECT sirket_adi FROM holdings WHERE ticker = ? ORDER BY donem DESC LIMIT 1",
            (ticker,),
        ).fetchone()

        if not (yonetici["adet"] or siyaset["adet"] or fon_kaydi):
            return None

        sirket = conn.execute(
            "SELECT asset_name FROM transactions WHERE ticker = ? "
            "ORDER BY chamber IS NOT NULL LIMIT 1",
            (ticker,),
        ).fetchone()
        sirket_adi = (sirket["asset_name"] if sirket
                      else fon_kaydi["sirket_adi"] if fon_kaydi else ticker)

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
        }


# ---------------------------------------------------------------------------
# KİŞİ
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# FONLAR
# ---------------------------------------------------------------------------

# Pasta dilimi renkleri: ilk on pozisyon + diğerleri
DILIM_RENKLERI = [
    "#1B4DFF", "#00A76F", "#F2994A", "#9B51E0", "#EB5757",
    "#2D9CDB", "#219653", "#F2C94C", "#BB6BD9", "#E07A5F",
    "#C9CDD2",
]


def _pasta_dilimleri(pozisyonlar, adet=10):
    """En büyük pozisyonlar + 'Diğerleri' için SVG çember dilimleri."""
    toplam = sum(p.get("deger") or 0 for p in pozisyonlar)
    if toplam <= 0:
        return []

    sirali = sorted(pozisyonlar, key=lambda p: p.get("deger") or 0, reverse=True)
    parcalar = [
        {"ad": p.get("ticker") or (p.get("sirket_adi") or "")[:18], "deger": p.get("deger") or 0}
        for p in sirali[:adet]
    ]
    kalan = sum(p.get("deger") or 0 for p in sirali[adet:])
    if kalan > 0:
        parcalar.append({"ad": "Diğerleri", "deger": kalan})

    cevre = 2 * 3.14159265 * 80   # yarıçapı 80 olan çemberin çevresi
    dilimler, kayma = [], 0.0
    for i, p in enumerate(parcalar):
        uzunluk = p["deger"] / toplam * cevre
        dilimler.append({
            "ad": p["ad"],
            "yuzde": round(p["deger"] / toplam * 100, 1),
            "deger_kisa": kisa_tutar(p["deger"]),
            "uzunluk": round(uzunluk, 2),
            "bosluk": round(cevre - uzunluk, 2),
            "kayma": round(-kayma, 2),
            "renk": DILIM_RENKLERI[i % len(DILIM_RENKLERI)],
        })
        kayma += uzunluk
    return dilimler


def fonlar():
    with baglanti() as conn:
        son_donem = conn.execute("SELECT MAX(donem) FROM holdings").fetchone()[0]
        satirlar = conn.execute(
            """SELECT fon_slug, fon_adi, COUNT(*) AS pozisyon, SUM(deger) AS toplam
               FROM holdings WHERE donem = ? GROUP BY fon_slug ORDER BY toplam DESC""",
            (son_donem,),
        ).fetchall()

    en_buyuk = (satirlar[0]["toplam"] if satirlar else 0) or 1
    return {
        "fonlar": [dict(s, toplam_kisa=kisa_tutar(s["toplam"]),
                        oran=(s["toplam"] or 0) / en_buyuk) for s in satirlar],
        "donem_adi": donem_metni(son_donem) if son_donem else "",
        "genel_toplam": kisa_tutar(sum(s["toplam"] or 0 for s in satirlar)),
    }


def fon(slug):
    """Fon sayfasının verisi: son çeyrek ve bir önceki çeyrekle fark."""
    with baglanti() as conn:
        donemler = [s["donem"] for s in conn.execute(
            "SELECT DISTINCT donem FROM holdings WHERE fon_slug = ? ORDER BY donem DESC",
            (slug,),
        )]
        if not donemler:
            return None

        fon_adi = conn.execute(
            "SELECT fon_adi FROM holdings WHERE fon_slug = ? LIMIT 1", (slug,)
        ).fetchone()["fon_adi"]

        def pozisyonlar(donem):
            return {
                s["cusip"]: dict(s) for s in conn.execute(
                    "SELECT * FROM holdings WHERE fon_slug = ? AND donem = ?", (slug, donem)
                )
            }

        simdi, onceki = donemler[0], (donemler[1] if len(donemler) > 1 else None)
        su_an = pozisyonlar(simdi)
        gecmis = pozisyonlar(onceki) if onceki else {}

    girisler, cikislar, artanlar, azalanlar = [], [], [], []
    for cusip, kayit in su_an.items():
        eski = gecmis.get(cusip)
        if eski is None:
            if onceki:
                girisler.append(kayit)
            continue
        fark = (kayit["adet"] or 0) - (eski["adet"] or 0)
        if abs(fark) < 1:
            continue
        kayit = dict(kayit, fark_adet=fark,
                     yuzde=round(fark / eski["adet"] * 100) if eski["adet"] else None)
        (artanlar if fark > 0 else azalanlar).append(kayit)
    cikislar = [e for c, e in gecmis.items() if c not in su_an]

    toplam = sum(k["deger"] or 0 for k in su_an.values())

    def hazirla(liste, anahtar="deger"):
        for k in liste:
            k["deger_kisa"] = kisa_tutar(k.get("deger") or 0)
            k["pay"] = round((k.get("deger") or 0) / toplam * 100, 2) if toplam else 0
        return sorted(liste, key=lambda k: abs(k.get(anahtar) or 0), reverse=True)

    return {
        "fon_adi": fon_adi,
        "donem_adi": donem_metni(simdi),
        "onceki_adi": donem_metni(onceki) if onceki else None,
        "pozisyon_sayisi": len(su_an),
        "toplam_kisa": kisa_tutar(toplam),
        "sayilar": {"giris": len(girisler), "cikis": len(cikislar),
                    "artan": len(artanlar), "azalan": len(azalanlar)},
        "girisler": hazirla(girisler)[:20],
        "cikislar": hazirla(cikislar)[:20],
        "artanlar": hazirla(artanlar, "fark_adet")[:20],
        "azalanlar": hazirla(azalanlar, "fark_adet")[:20],
        "dilimler": _pasta_dilimleri(list(su_an.values())),
        "portfoy": hazirla(list(su_an.values()))[:50],
    }
