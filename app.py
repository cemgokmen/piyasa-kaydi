from datetime import date, timedelta

from flask import Flask, render_template, request

from database import get_connection

app = Flask(__name__)

SAYFA_BOYUTU = 50

DONEMLER = {
    "7": ("Son 7 gün", 7),
    "30": ("Son 30 gün", 30),
    "90": ("Son 3 ay", 90),
}

SIRALAMALAR = {
    "yeni": ("En yeni", "disclosed_date DESC, id DESC"),
    "tutar": ("En büyük tutar", "amount_max DESC, id DESC"),
}

VARSAYILAN_DONEM = "7"
VARSAYILAN_SIRA = "yeni"


# ---------------------------------------------------------------------------
# VERİ
# ---------------------------------------------------------------------------

def filtre_kur(arama, islem, donem):
    """WHERE cümlesini ve parametrelerini üretir."""
    kosullar = []
    parametreler = []

    if islem in ("buy", "sell"):
        kosullar.append("action = ?")
        parametreler.append(islem)

    gun_sayisi = DONEMLER.get(donem, DONEMLER[VARSAYILAN_DONEM])[1]
    if gun_sayisi is not None:
        sinir = (date.today() - timedelta(days=gun_sayisi)).isoformat()
        kosullar.append("disclosed_date >= ?")
        parametreler.append(sinir)

    if arama:
        kosullar.append(
            "(ticker LIKE ? OR person LIKE ? OR company LIKE ? OR asset_name LIKE ?)"
        )
        desen = f"%{arama}%"
        parametreler.extend([desen, desen, desen, desen])
        

    # Anormal fiyatlı kayıtları hiçbir zaman gösterme
    kosullar.append("(suspect IS NULL OR suspect = 0)")

    where = " WHERE " + " AND ".join(kosullar) if kosullar else ""
    return where, parametreler


def ozet_getir(conn, where, parametreler):
    """Filtreye uyan kayıtların özet sayıları."""
    satir = conn.execute(
        f"""SELECT
              COUNT(*) AS adet,
              SUM(CASE WHEN action='buy' THEN 1 ELSE 0 END) AS alim,
              SUM(CASE WHEN action='sell' THEN 1 ELSE 0 END) AS satim,
              SUM(CASE WHEN action='buy' THEN amount_max ELSE 0 END) AS alim_tutar,
              SUM(CASE WHEN action='sell' THEN amount_max ELSE 0 END) AS satim_tutar
            FROM transactions{where}""",
        parametreler,
    ).fetchone()
    return dict(satir)


def kayitlari_getir(arama="", islem="hepsi", donem=VARSAYILAN_DONEM,
                    sira=VARSAYILAN_SIRA, sayfa=1):
    where, parametreler = filtre_kur(arama, islem, donem)
    order = SIRALAMALAR.get(sira, SIRALAMALAR[VARSAYILAN_SIRA])[1]

    conn = get_connection()
    ozet = ozet_getir(conn, where, parametreler)

    rows = conn.execute(
        f"SELECT * FROM transactions{where} ORDER BY {order} LIMIT ? OFFSET ?",
        parametreler + [SAYFA_BOYUTU, (sayfa - 1) * SAYFA_BOYUTU],
    ).fetchall()

    conn.close()
    return rows, ozet


# ---------------------------------------------------------------------------
# BİÇİMLENDİRME
# ---------------------------------------------------------------------------

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
        return f"{n / 1_000:.0f} b $"
    return f"{sayi_bicimle(n)} $"


def tarih_bicimle(iso):
    """'2026-08-18' -> '18 Ağu'"""
    aylar = ["Oca", "Şub", "Mar", "Nis", "May", "Haz",
             "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
    d = date.fromisoformat(iso)
    return f"{d.day} {aylar[d.month - 1]}"


def build_role(row):
    if row.get("chamber"):
        parts = [row["chamber"], row.get("state"), row.get("party")]
        return " · ".join(p for p in parts if p)
    return row.get("job_title") or "Bildirim yükümlüsü"

def tarih_temizle(ham):
    """Saat dilimi ekli tarihleri temizler: '2026-06-12-05:00' -> '2026-06-12'"""
    return ham[:10] if ham and len(ham) >= 10 else ham

def enrich(row):
    row = dict(row)
    row["transaction_date"] = tarih_temizle(row["transaction_date"])
    row["disclosed_date"] = tarih_temizle(row["disclosed_date"])
    row["amount_text"] = format_amount(row["amount_min"], row["amount_max"])
    row["delay_days"] = (
        date.fromisoformat(row["disclosed_date"])
        - date.fromisoformat(row["transaction_date"])
    ).days
    row["action_text"] = "Alım" if row["action"] == "buy" else "Satım"
    row["role_text"] = build_role(row)
    row["islem_tarih_kisa"] = tarih_bicimle(row["transaction_date"])
    row["bildirim_tarih_kisa"] = tarih_bicimle(row["disclosed_date"])
    if not row.get("person_slug"):
        from slug import slugify
        row["person_slug"] = slugify(row["person"])
    return row


# ---------------------------------------------------------------------------
# SAYFALAR
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    arama = request.args.get("q", "").strip()
    islem = request.args.get("islem", "hepsi")

    donem = request.args.get("donem", VARSAYILAN_DONEM)
    if donem not in DONEMLER:
        donem = VARSAYILAN_DONEM

    sira = request.args.get("sira", VARSAYILAN_SIRA)
    if sira not in SIRALAMALAR:
        sira = VARSAYILAN_SIRA

    try:
        sayfa = max(1, int(request.args.get("sayfa", 1)))
    except ValueError:
        sayfa = 1

    rows, ozet = kayitlari_getir(arama, islem, donem, sira, sayfa)
    toplam = ozet["adet"] or 0
    son_sayfa = max(1, -(-toplam // SAYFA_BOYUTU))

    return render_template(
        "index.html",
        rows=[enrich(r) for r in rows],
        ozet=ozet,
        toplam=toplam,
        toplam_metin=sayi_bicimle(toplam),
        alim_tutar=kisa_tutar(ozet["alim_tutar"]),
        satim_tutar=kisa_tutar(ozet["satim_tutar"]),
        sayfa=sayfa,
        son_sayfa=son_sayfa,
        arama=arama,
        islem=islem,
        donem=donem,
        donemler=DONEMLER,
        sira=sira,
        siralamalar=SIRALAMALAR,
    )


@app.route("/hisse/<ticker>")
def hisse(ticker):
    ticker = ticker.upper()
    conn = get_connection()

    ozet = dict(conn.execute(
        """SELECT
             COUNT(*) AS adet,
             SUM(CASE WHEN action='buy' THEN 1 ELSE 0 END) AS alim,
             SUM(CASE WHEN action='sell' THEN 1 ELSE 0 END) AS satim,
             SUM(CASE WHEN action='buy' THEN amount_max ELSE 0 END) AS alim_tutar,
             SUM(CASE WHEN action='sell' THEN amount_max ELSE 0 END) AS satim_tutar,
             COUNT(DISTINCT person) AS kisi
            FROM transactions WHERE ticker = ? AND (suspect IS NULL OR suspect = 0)""",
        (ticker,),
    ).fetchone())

    if not ozet["adet"]:
        # Yönetici işlemi yok ama fon pozisyonu olabilir
        fon_var = conn.execute(
            "SELECT COUNT(*) FROM holdings WHERE ticker = ?", (ticker,)
        ).fetchone()[0]
        if not fon_var:
            conn.close()
            return "Bu hisse için kayıt yok.", 404

    sirket = conn.execute(
        "SELECT asset_name FROM transactions WHERE ticker = ? LIMIT 1",
        (ticker,),
    ).fetchone()

    rows = conn.execute(
        "SELECT * FROM transactions WHERE ticker = ? AND (suspect IS NULL OR suspect = 0) "
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

    conn.close()

    return render_template(
        "hisse.html",
        ticker=ticker,
        sirket=sirket["asset_name"] if sirket else ticker,
        ozet=ozet,
        alim_tutar=kisa_tutar(ozet["alim_tutar"]),
        satim_tutar=kisa_tutar(ozet["satim_tutar"]),
        rows=[enrich(r) for r in rows],
        fonlar_listesi=fonlar_listesi,
        fon_ozet=fon_ozet,
    )


@app.route("/kisi/<slug>")
def kisi(slug):
    conn = get_connection()

    ozet = dict(conn.execute(
        """SELECT
             COUNT(*) AS adet,
             SUM(CASE WHEN action='buy' THEN 1 ELSE 0 END) AS alim,
             SUM(CASE WHEN action='sell' THEN 1 ELSE 0 END) AS satim,
             SUM(CASE WHEN action='buy' THEN amount_max ELSE 0 END) AS alim_tutar,
             SUM(CASE WHEN action='sell' THEN amount_max ELSE 0 END) AS satim_tutar,
             COUNT(DISTINCT ticker) AS hisse_adet,
             AVG(julianday(disclosed_date) - julianday(transaction_date)) AS ort_gecikme,
             MAX(julianday(disclosed_date) - julianday(transaction_date)) AS max_gecikme
           FROM transactions
           WHERE person_slug = ? AND (suspect IS NULL OR suspect = 0)""",
        (slug,),
    ).fetchone())

    if not ozet["adet"]:
        conn.close()
        return "Bu kişi için kayıt yok.", 404

    kimlik = conn.execute(
        "SELECT person, job_title, company, chamber, state, party, committee "
        "FROM transactions WHERE person_slug = ? "
        "ORDER BY disclosed_date DESC LIMIT 1",
        (slug,),
    ).fetchone()

    hisseler = conn.execute(
        """SELECT ticker, COUNT(*) AS adet, SUM(amount_max) AS hacim
           FROM transactions
           WHERE person_slug = ? AND (suspect IS NULL OR suspect = 0)
           GROUP BY ticker ORDER BY hacim DESC LIMIT 10""",
        (slug,),
    ).fetchall()

    rows = conn.execute(
        "SELECT * FROM transactions "
        "WHERE person_slug = ? AND (suspect IS NULL OR suspect = 0) "
        "ORDER BY disclosed_date DESC, id DESC LIMIT 100",
        (slug,),
    ).fetchall()

    conn.close()

    return render_template(
        "kisi.html",
        kimlik=dict(kimlik),
        rol=build_role(dict(kimlik)),
        ozet=ozet,
        ort_gecikme=round(ozet["ort_gecikme"] or 0),
        max_gecikme=round(ozet["max_gecikme"] or 0),
        alim_tutar=kisa_tutar(ozet["alim_tutar"]),
        satim_tutar=kisa_tutar(ozet["satim_tutar"]),
        hisseler=[dict(h, hacim_kisa=kisa_tutar(h["hacim"])) for h in hisseler],
        rows=[enrich(r) for r in rows],
    )

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

    liste = [dict(r, toplam_kisa=kisa_tutar(r["toplam"])) for r in rows]

    return render_template(
        "fonlar.html",
        rows=liste,
        donem=son_donem,
        donem_adi=donem_metni(son_donem) if son_donem else "",
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
        return "Bu fon için kayıt yok.", 404

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

    def hazirla(liste, anahtar="deger"):
        for k in liste:
            k["deger_kisa"] = kisa_tutar(k.get("deger") or 0)
        return sorted(liste, key=lambda k: abs(k.get(anahtar) or 0), reverse=True)

    toplam = sum(k["deger"] or 0 for k in su_an.values())

    return render_template(
        "fon.html",
        fon_adi=fon_adi,
        slug=slug,
        donem=simdi,
        donem_adi=donem_metni(simdi),
        onceki_adi=donem_metni(onceki) if onceki else None,
        pozisyon_sayisi=len(su_an),
        toplam_kisa=kisa_tutar(toplam),
        girisler=hazirla(girisler)[:20],
        cikislar=hazirla(cikislar)[:20],
        artanlar=hazirla(artanlar, "fark_adet")[:20],
        azalanlar=hazirla(azalanlar, "fark_adet")[:20],
        dilimler=pasta_dilimleri(list(su_an.values()), adet=10),
        portfoy=hazirla(list(su_an.values()))[:50],
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)