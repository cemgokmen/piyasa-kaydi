from datetime import date, timedelta

import numpy as np
from flask import Flask, abort, redirect, render_template, request, url_for

from piyasa.veritabani import get_connection
from piyasa.slug import slugify

app = Flask(__name__)

SAYFA_BOYUTU = 50

DONEMLER = {
    "7": ("7 gün", 7),
    "30": ("30 gün", 30),
    "90": ("3 ay", 90),
    "365": ("1 yıl", 365),
}

SIRALAMALAR = {
    "yeni": ("En yeni", "disclosed_date DESC, id DESC"),
    "tutar": ("En büyük tutar", "amount_max DESC, id DESC"),
    "gecikme": ("En geç bildirilen",
                "julianday(disclosed_date) - julianday(transaction_date) DESC, id DESC"),
}

# Kaynak: şirket içinden bildirenler (Form 4) ya da Kongre üyeleri (STOCK Act).
# Kongre kayıtlarında chamber dolu, Form 4 kayıtlarında boş.
KAYNAKLAR = {
    "hepsi": ("Tümü", None),
    "yonetici": ("Şirket yöneticileri", "chamber IS NULL"),
    "siyasetci": ("Siyasetçiler", "chamber IS NOT NULL"),
}

PARTILER = {
    "D": ("Demokrat", "dem"),
    "R": ("Cumhuriyetçi", "rep"),
    "I": ("Bağımsız", "ind"),
}

VARSAYILAN_DONEM = "7"
VARSAYILAN_SIRA = "yeni"

# Yasal bildirim süreleri. Form 4: işlemden sonra 2 iş günü.
# STOCK Act: işlemden sonra en geç 45 gün.
FORM4_IS_GUNU = 2
STOCK_ACT_GUN = 45

TEMIZ = "(suspect IS NULL OR suspect = 0)"

# Borsa kodu olmayan ihraççılar Form 4'te 'NONE' gibi yer tutucularla gelir
GECERLI_TICKER = "ticker NOT IN ('NONE', 'N/A', 'NA', '')"


# ---------------------------------------------------------------------------
# VERİ
# ---------------------------------------------------------------------------

def filtre_kur(arama, islem, donem, kaynak="hepsi"):
    """WHERE cümlesini ve parametrelerini üretir."""
    kosullar = [TEMIZ]   # anormal fiyatlı kayıtları hiçbir zaman gösterme
    parametreler = []

    if islem in ("buy", "sell"):
        kosullar.append("action = ?")
        parametreler.append(islem)

    kaynak_kosulu = KAYNAKLAR.get(kaynak, KAYNAKLAR["hepsi"])[1]
    if kaynak_kosulu:
        kosullar.append(kaynak_kosulu)

    gun_sayisi = DONEMLER.get(donem, DONEMLER[VARSAYILAN_DONEM])[1]
    kosullar.append("disclosed_date >= ?")
    parametreler.append((date.today() - timedelta(days=gun_sayisi)).isoformat())

    if arama:
        kosullar.append(
            "(ticker LIKE ? OR person LIKE ? OR company LIKE ? OR asset_name LIKE ?)"
        )
        desen = f"%{arama}%"
        parametreler.extend([desen, desen, desen, desen])

    return " WHERE " + " AND ".join(kosullar), parametreler


OZET_SUTUNLARI = """
    COUNT(*) AS adet,
    SUM(CASE WHEN action='buy' THEN 1 ELSE 0 END) AS alim,
    SUM(CASE WHEN action='sell' THEN 1 ELSE 0 END) AS satim,
    SUM(CASE WHEN action='buy' THEN amount_max ELSE 0 END) AS alim_tutar,
    SUM(CASE WHEN action='sell' THEN amount_max ELSE 0 END) AS satim_tutar,
    SUM(CASE WHEN action='buy' THEN amount_min ELSE 0 END) AS alim_alt,
    SUM(CASE WHEN action='sell' THEN amount_min ELSE 0 END) AS satim_alt
"""


def ozet_getir(conn, where, parametreler):
    """Filtreye uyan kayıtların özet sayıları."""
    satir = conn.execute(
        f"SELECT {OZET_SUTUNLARI}, COUNT(DISTINCT person) AS kisi "
        f"FROM transactions{where}",
        parametreler,
    ).fetchone()
    return dict(satir)


def kayitlari_getir(arama="", islem="hepsi", donem=VARSAYILAN_DONEM,
                    sira=VARSAYILAN_SIRA, sayfa=1, kaynak="hepsi"):
    where, parametreler = filtre_kur(arama, islem, donem, kaynak)
    order = SIRALAMALAR.get(sira, SIRALAMALAR[VARSAYILAN_SIRA])[1]

    conn = get_connection()
    ozet = ozet_getir(conn, where, parametreler)

    rows = conn.execute(
        f"SELECT * FROM transactions{where} ORDER BY {order} LIMIT ? OFFSET ?",
        parametreler + [SAYFA_BOYUTU, (sayfa - 1) * SAYFA_BOYUTU],
    ).fetchall()

    conn.close()
    return rows, ozet


def son_veri_tarihi(conn):
    return conn.execute(
        f"SELECT MAX(disclosed_date) FROM transactions WHERE {TEMIZ}"
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# BİÇİMLENDİRME
# ---------------------------------------------------------------------------

AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
         "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
AYLAR_UZUN = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
              "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]


def sayi_bicimle(n):
    return f"{int(n):,}".replace(",", ".")


def format_amount(low, high):
    if low is None:
        return "—"
    if low == high:
        return f"{sayi_bicimle(low)} $"
    return f"{sayi_bicimle(low)} – {sayi_bicimle(high)} $"


def kisa_tutar(n):
    """1250000 -> '1,3 mn $'"""
    if not n:
        return "0 $"
    if n >= 1_000_000_000_000:
        return f"{n / 1_000_000_000_000:.1f}".replace(".", ",") + " trl $"
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}".replace(".", ",") + " mr $"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".replace(".", ",") + " mn $"
    if n >= 1_000:
        return f"{n / 1_000:.0f} bin $"
    return f"{sayi_bicimle(n)} $"


def kisa_aralik(low, high):
    """Kongre bildirimleri aralık verir: '1 bin – 15 bin $'"""
    if low is None:
        return "—"
    if low == high:
        return kisa_tutar(low)
    return f"{kisa_tutar(low)[:-2]} – {kisa_tutar(high)}"


@app.template_global("aralik")
def aralik_global(alt, ust):
    return kisa_aralik(alt or 0, ust or 0)


def tarih_bicimle(iso):
    """'2026-08-18' -> '18 Ağu'"""
    d = date.fromisoformat(iso)
    return f"{d.day} {AYLAR[d.month - 1]}"


def uzun_tarih(iso):
    """'2026-08-18' -> '18 Ağustos 2026'"""
    if not iso:
        return ""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {AYLAR_UZUN[d.month - 1]} {d.year}"


def parti_bilgisi(kod):
    ad, sinif = PARTILER.get(kod or "", ("", ""))
    return {"kod": kod, "ad": ad, "sinif": sinif} if kod else None


def build_role(row):
    if row.get("chamber"):
        parts = [row["chamber"], row.get("state"), row.get("party")]
        return " · ".join(p for p in parts if p)
    return row.get("job_title") or "Bildirim yükümlüsü"


def tarih_temizle(ham):
    """Saat dilimi ekli tarihleri temizler: '2026-06-12-05:00' -> '2026-06-12'"""
    return ham[:10] if ham and len(ham) >= 10 else ham


def gec_mi(row):
    """Bildirim yasal süreden sonra mı yapılmış?"""
    if row.get("chamber"):
        return row["delay_days"] > STOCK_ACT_GUN
    is_gunu = int(np.busday_count(row["transaction_date"], row["disclosed_date"]))
    return is_gunu > FORM4_IS_GUNU


def enrich(row):
    row = dict(row)
    row["transaction_date"] = tarih_temizle(row["transaction_date"])
    row["disclosed_date"] = tarih_temizle(row["disclosed_date"])
    row["amount_text"] = format_amount(row["amount_min"], row["amount_max"])
    row["amount_kisa"] = kisa_aralik(row["amount_min"], row["amount_max"])
    row["delay_days"] = (
        date.fromisoformat(row["disclosed_date"])
        - date.fromisoformat(row["transaction_date"])
    ).days
    row["gec"] = gec_mi(row)
    row["action_text"] = "Alım" if row["action"] == "buy" else "Satım"
    row["role_text"] = build_role(row)
    row["siyasetci"] = bool(row.get("chamber"))
    row["parti"] = parti_bilgisi(row.get("party"))
    row["islem_tarih_kisa"] = tarih_bicimle(row["transaction_date"])
    row["bildirim_tarih_kisa"] = tarih_bicimle(row["disclosed_date"])
    if not row.get("person_slug"):
        row["person_slug"] = slugify(row["person"])
    return row


@app.context_processor
def ortak_degiskenler():
    return {"kaynaklar": KAYNAKLAR, "yasal_gun": STOCK_ACT_GUN}


@app.template_filter("tutar")
def tutar_filtresi(n):
    return kisa_tutar(n)


@app.template_filter("sayi")
def sayi_filtresi(n):
    return sayi_bicimle(n or 0)


@app.template_filter("uzun_tarih")
def uzun_tarih_filtresi(iso):
    return uzun_tarih(iso)


# ---------------------------------------------------------------------------
# SAYFALAR
# ---------------------------------------------------------------------------

def tarihten_once(gun):
    return (date.today() - timedelta(days=gun)).isoformat()


@app.route("/")
def anasayfa():
    # Eski sürümde liste ana sayfadaydı; filtreli eski bağlantılar listeye gitsin
    if request.args:
        return redirect(url_for("islemler", **request.args))

    conn = get_connection()
    son30 = tarihten_once(30)
    son365 = tarihten_once(365)

    yonetici = dict(conn.execute(
        f"SELECT {OZET_SUTUNLARI}, COUNT(DISTINCT person) AS kisi FROM transactions "
        f"WHERE chamber IS NULL AND {TEMIZ} AND disclosed_date >= ?",
        (son30,),
    ).fetchone())

    siyaset = dict(conn.execute(
        f"SELECT {OZET_SUTUNLARI}, COUNT(DISTINCT person) AS kisi FROM transactions "
        f"WHERE chamber IS NOT NULL AND disclosed_date >= ?",
        (son365,),
    ).fetchone())

    # Küme alımları: aynı hisseyi 30 gün içinde birden fazla yöneticinin
    # kendi parasıyla alması, tek bir alımdan daha anlamlı kabul edilir.
    kume = [
        dict(r, tutar_kisa=kisa_tutar(r["tutar"]))
        for r in conn.execute(
            f"""SELECT ticker, MAX(asset_name) AS sirket,
                      COUNT(DISTINCT person) AS kisi, COUNT(*) AS adet,
                      SUM(amount_max) AS tutar
               FROM transactions
               WHERE chamber IS NULL AND action = 'buy' AND {TEMIZ}
                 AND {GECERLI_TICKER} AND disclosed_date >= ?
               GROUP BY ticker HAVING kisi >= 2
               ORDER BY kisi DESC, tutar DESC LIMIT 8""",
            (son30,),
        )
    ]

    buyuk_alimlar = [
        enrich(r) for r in conn.execute(
            f"""SELECT * FROM transactions
               WHERE chamber IS NULL AND action = 'buy' AND {TEMIZ}
                 AND disclosed_date >= ?
               ORDER BY amount_max DESC LIMIT 6""",
            (son30,),
        )
    ]

    siyaset_son = [
        enrich(r) for r in conn.execute(
            """SELECT * FROM transactions WHERE chamber IS NOT NULL
               ORDER BY disclosed_date DESC, id DESC LIMIT 8"""
        )
    ]

    siyaset_hisse = [
        dict(r) for r in conn.execute(
            """SELECT ticker, MAX(asset_name) AS sirket,
                      SUM(CASE WHEN action='buy' THEN 1 ELSE 0 END) AS alim,
                      SUM(CASE WHEN action='sell' THEN 1 ELSE 0 END) AS satim,
                      COUNT(DISTINCT person) AS kisi
               FROM transactions
               WHERE chamber IS NOT NULL AND disclosed_date >= ?
               GROUP BY ticker ORDER BY kisi DESC, alim + satim DESC LIMIT 8""",
            (son365,),
        )
    ]

    son_donem = conn.execute("SELECT MAX(donem) FROM holdings").fetchone()[0]
    fon_sayisi = conn.execute(
        "SELECT COUNT(DISTINCT fon_slug) FROM holdings WHERE donem = ?", (son_donem,)
    ).fetchone()[0] if son_donem else 0

    guncel = son_veri_tarihi(conn)
    conn.close()

    return render_template(
        "anasayfa.html",
        aktif="anasayfa",
        yonetici=yonetici,
        siyaset=siyaset,
        kume=kume,
        buyuk_alimlar=buyuk_alimlar,
        siyaset_son=siyaset_son,
        siyaset_hisse=siyaset_hisse,
        fon_sayisi=fon_sayisi,
        donem_adi=donem_metni(son_donem) if son_donem else "",
        guncel=guncel,
    )


@app.route("/islemler")
def islemler():
    arama = request.args.get("q", "").strip()
    islem = request.args.get("islem", "hepsi")

    kaynak = request.args.get("kaynak", "hepsi")
    if kaynak not in KAYNAKLAR:
        kaynak = "hepsi"

    # Kongre bildirimleri seyrek ve geç geldiği için varsayılan dönem daha uzun
    varsayilan = "365" if kaynak == "siyasetci" else VARSAYILAN_DONEM
    donem = request.args.get("donem", varsayilan)
    if donem not in DONEMLER:
        donem = varsayilan

    sira = request.args.get("sira", VARSAYILAN_SIRA)
    if sira not in SIRALAMALAR:
        sira = VARSAYILAN_SIRA

    try:
        sayfa = max(1, int(request.args.get("sayfa", 1)))
    except ValueError:
        sayfa = 1

    rows, ozet = kayitlari_getir(arama, islem, donem, sira, sayfa, kaynak)
    toplam = ozet["adet"] or 0
    son_sayfa = max(1, -(-toplam // SAYFA_BOYUTU))

    return render_template(
        "islemler.html",
        aktif="siyasetci" if kaynak == "siyasetci" else "islemler",
        rows=[enrich(r) for r in rows],
        ozet=ozet,
        toplam=toplam,
        alim_tutar=kisa_tutar(ozet["alim_tutar"]),
        satim_tutar=kisa_tutar(ozet["satim_tutar"]),
        sayfa=sayfa,
        son_sayfa=son_sayfa,
        arama=arama,
        islem=islem,
        kaynak=kaynak,
        donem=donem,
        donemler=DONEMLER,
        sira=sira,
        siralamalar=SIRALAMALAR,
    )


@app.route("/siyasetciler")
def siyasetciler():
    parti = request.args.get("parti", "")
    if parti not in PARTILER:
        parti = ""

    conn = get_connection()
    kosul = "chamber IS NOT NULL" + (" AND party = ?" if parti else "")
    parametreler = (parti,) if parti else ()

    kisiler = []
    for r in conn.execute(
        f"""SELECT person, person_slug, MAX(party) AS party, MAX(state) AS state,
                  MAX(chamber) AS chamber,
                  COUNT(*) AS adet,
                  SUM(CASE WHEN action='buy' THEN 1 ELSE 0 END) AS alim,
                  SUM(CASE WHEN action='sell' THEN 1 ELSE 0 END) AS satim,
                  SUM(amount_max) AS ust_tutar,
                  SUM(amount_min) AS alt_tutar,
                  COUNT(DISTINCT ticker) AS hisse,
                  MAX(transaction_date) AS son_islem,
                  AVG(julianday(disclosed_date) - julianday(transaction_date)) AS ort_gecikme,
                  SUM(CASE WHEN julianday(disclosed_date) - julianday(transaction_date) > ?
                           THEN 1 ELSE 0 END) AS gec
           FROM transactions WHERE {kosul}
           GROUP BY person_slug ORDER BY adet DESC""",
        (STOCK_ACT_GUN, *parametreler),
    ):
        k = dict(r)
        k["parti"] = parti_bilgisi(k["party"])
        k["hacim_aralik"] = kisa_aralik(k["alt_tutar"], k["ust_tutar"])
        k["ort_gecikme"] = round(k["ort_gecikme"] or 0)
        kisiler.append(k)

    partiler = {
        r["party"]: r["n"] for r in conn.execute(
            "SELECT party, COUNT(DISTINCT person_slug) AS n FROM transactions "
            "WHERE chamber IS NOT NULL GROUP BY party"
        )
    }
    ozet = dict(conn.execute(
        f"SELECT {OZET_SUTUNLARI}, COUNT(DISTINCT person_slug) AS kisi, "
        f"MIN(disclosed_date) AS ilk, MAX(disclosed_date) AS son "
        f"FROM transactions WHERE chamber IS NOT NULL"
    ).fetchone())
    conn.close()

    return render_template(
        "siyasetciler.html",
        aktif="siyasetci",
        kisiler=kisiler,
        parti=parti,
        partiler=PARTILER,
        parti_sayilari=partiler,
        ozet=ozet,
    )


def aylik_dagilim(conn, ticker, ay_sayisi=12):
    """Son ay_sayisi ayın alım/satım adetleri (grafik için)."""
    bugun = date.today()
    aylar = []
    y, m = bugun.year, bugun.month
    for _ in range(ay_sayisi):
        aylar.append(f"{y}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    aylar.reverse()

    sayilar = {
        (r["ay"], r["action"]): r["n"]
        for r in conn.execute(
            f"""SELECT substr(transaction_date, 1, 7) AS ay, action, COUNT(*) AS n
               FROM transactions WHERE ticker = ? AND {TEMIZ}
                 AND substr(transaction_date, 1, 7) >= ?
               GROUP BY ay, action""",
            (ticker, aylar[0]),
        )
    }

    cubuklar = [
        {
            "ay": AYLAR[int(a[5:]) - 1],
            "alim": sayilar.get((a, "buy"), 0),
            "satim": sayilar.get((a, "sell"), 0),
        }
        for a in aylar
    ]
    en_cok = max([c["alim"] for c in cubuklar] + [c["satim"] for c in cubuklar] + [1])
    for c in cubuklar:
        c["alim_oran"] = c["alim"] / en_cok
        c["satim_oran"] = c["satim"] / en_cok
    return cubuklar if any(c["alim"] or c["satim"] for c in cubuklar) else []


@app.route("/hisse/<ticker>")
def hisse(ticker):
    ticker = ticker.upper()
    conn = get_connection()

    ozet = dict(conn.execute(
        f"""SELECT {OZET_SUTUNLARI},
             COUNT(DISTINCT person) AS kisi,
             SUM(CASE WHEN chamber IS NOT NULL THEN 1 ELSE 0 END) AS siyasetci
            FROM transactions WHERE ticker = ? AND {TEMIZ}""",
        (ticker,),
    ).fetchone())

    if not ozet["adet"]:
        # Yönetici işlemi yok ama fon pozisyonu olabilir
        fon_var = conn.execute(
            "SELECT COUNT(*) FROM holdings WHERE ticker = ?", (ticker,)
        ).fetchone()[0]
        if not fon_var:
            conn.close()
            abort(404)

    sirket = conn.execute(
        "SELECT asset_name FROM transactions WHERE ticker = ? AND chamber IS NULL LIMIT 1",
        (ticker,),
    ).fetchone() or conn.execute(
        "SELECT asset_name FROM transactions WHERE ticker = ? LIMIT 1",
        (ticker,),
    ).fetchone()
    if sirket is None:
        # Yalnızca fon pozisyonu olan hisselerde adı 13F'ten al
        sirket = conn.execute(
            "SELECT sirket_adi AS asset_name FROM holdings WHERE ticker = ? LIMIT 1",
            (ticker,),
        ).fetchone()

    rows = conn.execute(
        f"SELECT * FROM transactions WHERE ticker = ? AND {TEMIZ} "
        "ORDER BY disclosed_date DESC, id DESC LIMIT 100",
        (ticker,),
    ).fetchall()

    # Bu hisseyi tutan fonlar — en son çeyrek
    son_donem = conn.execute(
        "SELECT MAX(donem) FROM holdings"
    ).fetchone()[0]

    fonlar_listesi = []
    fon_ozet = None

    if son_donem:
        fonlar_listesi = [
            dict(r, deger_kisa=kisa_tutar(r["deger"]))
            for r in conn.execute(
                """SELECT fon_adi, fon_slug, deger, adet
                   FROM holdings
                   WHERE ticker = ? AND donem = ?
                   ORDER BY deger DESC LIMIT 15""",
                (ticker, son_donem),
            )
        ]

        satir = conn.execute(
            """SELECT COUNT(*) AS fon_sayisi, SUM(deger) AS toplam
               FROM holdings WHERE ticker = ? AND donem = ?""",
            (ticker, son_donem),
        ).fetchone()

        if satir["fon_sayisi"]:
            fon_ozet = {
                "sayi": satir["fon_sayisi"],
                "toplam_kisa": kisa_tutar(satir["toplam"]),
                "donem_adi": donem_metni(son_donem),
            }

    cubuklar = aylik_dagilim(conn, ticker)
    conn.close()

    return render_template(
        "hisse.html",
        aktif="islemler",
        ticker=ticker,
        sirket=sirket["asset_name"] if sirket else ticker,
        ozet=ozet,
        alim_tutar=kisa_tutar(ozet["alim_tutar"]),
        satim_tutar=kisa_tutar(ozet["satim_tutar"]),
        rows=[enrich(r) for r in rows],
        fonlar_listesi=fonlar_listesi,
        fon_ozet=fon_ozet,
        cubuklar=cubuklar,
    )


@app.route("/kisi/<slug>")
def kisi(slug):
    conn = get_connection()

    ozet = dict(conn.execute(
        f"""SELECT {OZET_SUTUNLARI},
             COUNT(DISTINCT ticker) AS hisse_adet,
             AVG(julianday(disclosed_date) - julianday(transaction_date)) AS ort_gecikme,
             MAX(julianday(disclosed_date) - julianday(transaction_date)) AS max_gecikme
           FROM transactions
           WHERE person_slug = ? AND {TEMIZ}""",
        (slug,),
    ).fetchone())

    if not ozet["adet"]:
        conn.close()
        abort(404)

    kimlik = dict(conn.execute(
        "SELECT person, job_title, company, chamber, state, party, committee "
        "FROM transactions WHERE person_slug = ? "
        "ORDER BY disclosed_date DESC LIMIT 1",
        (slug,),
    ).fetchone())

    hisseler = conn.execute(
        f"""SELECT ticker, COUNT(*) AS adet, SUM(amount_max) AS hacim,
                  SUM(CASE WHEN action='buy' THEN 1 ELSE 0 END) AS alim,
                  SUM(CASE WHEN action='sell' THEN 1 ELSE 0 END) AS satim
           FROM transactions
           WHERE person_slug = ? AND {TEMIZ}
           GROUP BY ticker ORDER BY adet DESC, hacim DESC LIMIT 12""",
        (slug,),
    ).fetchall()

    rows = [enrich(r) for r in conn.execute(
        f"SELECT * FROM transactions WHERE person_slug = ? AND {TEMIZ} "
        "ORDER BY disclosed_date DESC, id DESC LIMIT 200",
        (slug,),
    )]

    conn.close()

    siyasetci = bool(kimlik.get("chamber"))
    return render_template(
        "kisi.html",
        aktif="siyasetci" if siyasetci else "islemler",
        kimlik=kimlik,
        siyasetci=siyasetci,
        parti=parti_bilgisi(kimlik.get("party")),
        rol=build_role(kimlik),
        ozet=ozet,
        ort_gecikme=round(ozet["ort_gecikme"] or 0),
        max_gecikme=round(ozet["max_gecikme"] or 0),
        gec_sayisi=sum(1 for r in rows if r["gec"]),
        alim_tutar=(kisa_aralik(ozet["alim_alt"] or 0, ozet["alim_tutar"] or 0) if siyasetci
                    else kisa_tutar(ozet["alim_tutar"])),
        satim_tutar=(kisa_aralik(ozet["satim_alt"] or 0, ozet["satim_tutar"] or 0) if siyasetci
                     else kisa_tutar(ozet["satim_tutar"])),
        hisseler=[dict(h, hacim_kisa=kisa_tutar(h["hacim"])) for h in hisseler],
        rows=rows,
    )


@app.route("/hakkinda")
def hakkinda():
    return render_template("hakkinda.html", aktif="hakkinda",
                           form4_gun=FORM4_IS_GUNU)


@app.errorhandler(404)
def bulunamadi(_hata):
    return render_template("404.html", aktif=None), 404


# ---------------------------------------------------------------------------
# FONLAR
# ---------------------------------------------------------------------------

def donemleri_getir(conn):
    """Elimizdeki çeyrekleri yeniden eskiye sıralar."""
    return [
        r["donem"] for r in conn.execute(
            "SELECT DISTINCT donem FROM holdings ORDER BY donem DESC"
        )
    ]


# Pasta dilimi renkleri: ilk beş pozisyon + diğerleri
DILIM_RENKLERI = [
    "#1B4DFF", "#00A76F", "#F2994A", "#9B51E0", "#EB5757",
    "#2D9CDB", "#219653", "#F2C94C", "#BB6BD9", "#E07A5F",
    "#C9CDD2",
]


def pasta_dilimleri(pozisyonlar, adet=5):
    """
    En büyük pozisyonları pasta grafiği dilimlerine çevirir.
    Kalanlar tek bir 'Diğerleri' diliminde toplanır.
    """
    toplam = sum(p.get("deger") or 0 for p in pozisyonlar)
    if toplam <= 0:
        return []

    sirali = sorted(pozisyonlar, key=lambda p: p.get("deger") or 0, reverse=True)
    ilkler = sirali[:adet]
    kalan_deger = sum(p.get("deger") or 0 for p in sirali[adet:])

    parcalar = []
    for p in ilkler:
        parcalar.append({
            "ad": p.get("ticker") or (p.get("sirket_adi") or "")[:18],
            "deger": p.get("deger") or 0,
        })

    if kalan_deger > 0:
        parcalar.append({"ad": "Diğerleri", "deger": kalan_deger})

    # SVG çemberinde dilimleri konumlandırmak için
    # yarıçap 80 olan çemberin çevresi:
    cevre = 2 * 3.14159265 * 80

    dilimler = []
    kayma = 0.0
    for i, parca in enumerate(parcalar):
        oran = parca["deger"] / toplam
        uzunluk = oran * cevre

        dilimler.append({
            "ad": parca["ad"],
            "yuzde": round(oran * 100, 1),
            "deger_kisa": kisa_tutar(parca["deger"]),
            "uzunluk": round(uzunluk, 2),
            "bosluk": round(cevre - uzunluk, 2),
            "kayma": round(-kayma, 2),
            "renk": DILIM_RENKLERI[i % len(DILIM_RENKLERI)],
        })

        kayma += uzunluk

    return dilimler


def donem_metni(donem):
    """'2026-06-30' -> '2026 2. çeyrek'"""
    yil, ay, _ = donem.split("-")
    ceyrek = (int(ay) - 1) // 3 + 1
    return f"{yil} {ceyrek}. çeyrek"


@app.route("/fonlar")
def fonlar():
    conn = get_connection()
    donemler = donemleri_getir(conn)
    son_donem = donemler[0] if donemler else None

    rows = conn.execute(
        """SELECT fon_slug, fon_adi,
                  COUNT(*) AS pozisyon,
                  SUM(deger) AS toplam
           FROM holdings
           WHERE donem = ?
           GROUP BY fon_slug
           ORDER BY toplam DESC""",
        (son_donem,),
    ).fetchall()

    conn.close()

    genel_toplam = sum(r["toplam"] or 0 for r in rows) or 1
    liste = [
        dict(r, toplam_kisa=kisa_tutar(r["toplam"]),
             oran=(r["toplam"] or 0) / (rows[0]["toplam"] or 1),
             pay=round((r["toplam"] or 0) / genel_toplam * 100, 1))
        for r in rows
    ]

    return render_template(
        "fonlar.html",
        aktif="fonlar",
        rows=liste,
        donem=son_donem,
        donem_adi=donem_metni(son_donem) if son_donem else "",
        genel_toplam=kisa_tutar(genel_toplam),
    )


@app.route("/fon/<slug>")
def fon(slug):
    conn = get_connection()

    donemler = [
        r["donem"] for r in conn.execute(
            "SELECT DISTINCT donem FROM holdings WHERE fon_slug = ? "
            "ORDER BY donem DESC",
            (slug,),
        )
    ]

    if not donemler:
        conn.close()
        abort(404)

    fon_adi = conn.execute(
        "SELECT fon_adi FROM holdings WHERE fon_slug = ? LIMIT 1", (slug,)
    ).fetchone()["fon_adi"]

    simdi = donemler[0]
    onceki = donemler[1] if len(donemler) > 1 else None

    # Bu çeyreğin pozisyonları
    su_an = {
        r["cusip"]: dict(r)
        for r in conn.execute(
            "SELECT * FROM holdings WHERE fon_slug = ? AND donem = ?",
            (slug, simdi),
        )
    }

    # Önceki çeyreğin pozisyonları
    gecmis = {}
    if onceki:
        gecmis = {
            r["cusip"]: dict(r)
            for r in conn.execute(
                "SELECT * FROM holdings WHERE fon_slug = ? AND donem = ?",
                (slug, onceki),
            )
        }

    girisler, cikislar, artanlar, azalanlar = [], [], [], []

    for cusip, kayit in su_an.items():
        eski = gecmis.get(cusip)

        if eski is None:
            girisler.append(kayit)
            continue

        fark = (kayit["adet"] or 0) - (eski["adet"] or 0)
        if abs(fark) < 1:
            continue

        kayit = dict(kayit)
        kayit["fark_adet"] = fark
        kayit["eski_adet"] = eski["adet"]
        # Yüzde değişim
        if eski["adet"]:
            kayit["yuzde"] = round(fark / eski["adet"] * 100)
        else:
            kayit["yuzde"] = None

        (artanlar if fark > 0 else azalanlar).append(kayit)

    for cusip, eski in gecmis.items():
        if cusip not in su_an:
            cikislar.append(eski)

    conn.close()

    toplam = sum(k["deger"] or 0 for k in su_an.values())

    def hazirla(liste, anahtar="deger"):
        for k in liste:
            k["deger_kisa"] = kisa_tutar(k.get("deger") or 0)
            k["pay"] = round((k.get("deger") or 0) / toplam * 100, 2) if toplam else 0
        return sorted(liste, key=lambda k: abs(k.get(anahtar) or 0), reverse=True)

    return render_template(
        "fon.html",
        aktif="fonlar",
        fon_adi=fon_adi,
        slug=slug,
        donem=simdi,
        donem_adi=donem_metni(simdi),
        onceki_adi=donem_metni(onceki) if onceki else None,
        pozisyon_sayisi=len(su_an),
        toplam_kisa=kisa_tutar(toplam),
        sayilar={"giris": len(girisler), "cikis": len(cikislar),
                 "artan": len(artanlar), "azalan": len(azalanlar)},
        girisler=hazirla(girisler)[:20],
        cikislar=hazirla(cikislar)[:20],
        artanlar=hazirla(artanlar, "fark_adet")[:20],
        azalanlar=hazirla(azalanlar, "fark_adet")[:20],
        dilimler=pasta_dilimleri(list(su_an.values()), adet=10),
        portfoy=hazirla(list(su_an.values()))[:50],
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)
