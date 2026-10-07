"""Fon listesi ve fon sayfası: portföy, çeyrekler arası değişim, pasta grafiği, fon konsensüsü."""

import statistics

from piyasa.bicim import donem_metni, kisa_tutar
from piyasa.onbellek import sureli
from piyasa.web.sorgular.ortak import FON_SON_DONEM, baglanti

# Pasta dilimi renkleri: ilk on pozisyon + diğerleri
DILIM_RENKLERI = [
    "#1B4DFF", "#00A76F", "#F2994A", "#9B51E0", "#EB5757",
    "#2D9CDB", "#219653", "#F2C94C", "#BB6BD9", "#E07A5F",
    "#C9CDD2",
]


def pasta_dilimleri(pozisyonlar, adet=10):
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


@sureli(10 * 60)
def fonlar():
    """Her fon kendi son çeyreğiyle; daha eski çeyrekte kalan fon da listelenir. 10 dk önbellekli
    (fon verisi çeyrekte bir değişir)."""
    with baglanti() as conn:
        son_donem = conn.execute("SELECT MAX(donem) FROM holdings").fetchone()[0]
        satirlar = conn.execute(
            f"""SELECT h.fon_slug, MAX(h.fon_adi) AS fon_adi, h.donem,
                      COUNT(*) AS pozisyon, SUM(h.deger) AS toplam
               FROM holdings h JOIN ({FON_SON_DONEM}) s
                 ON s.fon_slug = h.fon_slug AND s.donem = h.donem
               GROUP BY h.fon_slug ORDER BY toplam DESC"""
        ).fetchall()

    en_buyuk = (satirlar[0]["toplam"] if satirlar else 0) or 1
    return {
        "fonlar": [dict(s, toplam_kisa=kisa_tutar(s["toplam"]),
                        oran=(s["toplam"] or 0) / en_buyuk,
                        geride=s["donem"] != son_donem,
                        donem_adi=donem_metni(s["donem"])) for s in satirlar],
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
        "dilimler": pasta_dilimleri(list(su_an.values())),
        "portfoy": hazirla(list(su_an.values()))[:50],
    }


# ---------------------------------------------------------------------------
# Fon konsensüsü: büyük fonlar son çeyrekte hangi hisselere girdi, hangilerini
# artırdı, hangilerinden çıktı?
# ---------------------------------------------------------------------------

DEGISIM_ESIGI = 0.05      # adet en az %5 değişmediyse "değişmedi" sayılır


SIRKET_OLAYI_PAYI = 0.8   # önceki sahiplerin bu kadarı çıktıysa satın alma / iflas / borsadan çıkma


def _ilk_kelime(ad):
    kelimeler = (ad or "").upper().split()
    return kelimeler[0] if kelimeler else ""


def _ceyrek_getirileri(hisseler):
    """Son iki çeyrek sonu arasındaki gerçek (bölünmeye göre düzeltilmiş) fiyat değişimi."""
    with baglanti() as conn:
        donemler = [s[0] for s in conn.execute("SELECT DISTINCT donem FROM holdings ORDER BY donem DESC LIMIT 2")]
        if len(donemler) < 2:
            return {}
        getiriler = {}
        for s in conn.execute(
            """SELECT ticker,
                      (SELECT kapanis FROM fiyat_gecmisi f WHERE f.ticker = t.ticker AND f.tarih <= ?
                       ORDER BY tarih DESC LIMIT 1) AS son,
                      (SELECT kapanis FROM fiyat_gecmisi f WHERE f.ticker = t.ticker AND f.tarih <= ?
                       ORDER BY tarih DESC LIMIT 1) AS onceki
               FROM (SELECT DISTINCT ticker FROM fiyat_gecmisi) t""",
            (donemler[0], donemler[1]),
        ):
            if s["ticker"] in hisseler and s["son"] and s["onceki"]:
                getiriler[s["ticker"]] = s["son"] / s["onceki"]
    return getiriler


@sureli(6 * 3600)
def fon_konsensusu(adet=12):
    """
    Her fonun kendi son çeyreği bir önceki çeyreğiyle karşılaştırılır (fonlar
    bildirimlerini farklı zamanlarda yaptığı için tek bir ortak çeyrek alınmaz).
    Hisse başına kaç fonun yeni girdiği, artırdığı (adet %5+), azalttığı ve
    tamamen çıktığı sayılır.

    Şirket olayları alım-satım sayılmaz:
      - Geçen çeyrek hiçbir fonun tutmadığı hisse halka arz ya da bölünmedir;
        "yeni listelenen" olarak ayrı verilir.
      - Önceki sahiplerinin çoğu birden çıktıysa ya da kodu iflas eki 'Q' ile
        bitiyorsa şirket satın alınmış, iflas etmiş ya da borsadan çıkmıştır.
      - Hisse bölündüyse ya da birleştirildiyse (fonların bildirdiği birim değer,
        bölünmeye göre düzeltilmiş gerçek fiyat değişiminden çok farklıysa) adet
        oranları bölünme oranıyla düzeltilir; adet değişimi alım-satım sanılmaz.
    """
    with baglanti() as conn:
        satirlar = conn.execute(
            """WITH d AS (
                   SELECT fon_slug, donem,
                          DENSE_RANK() OVER (PARTITION BY fon_slug ORDER BY donem DESC) AS sira
                   FROM (SELECT DISTINCT fon_slug, donem FROM holdings))
               SELECT h.fon_slug, d.sira, h.ticker, MAX(h.sirket_adi) AS sirket,
                      SUM(h.adet) AS adet, SUM(h.deger) AS deger
               FROM holdings h JOIN d ON d.fon_slug = h.fon_slug AND d.donem = h.donem
               WHERE d.sira <= 2 AND h.ticker IS NOT NULL AND h.ticker != ''
               GROUP BY h.fon_slug, d.sira, h.ticker"""
        ).fetchall()
        son_donem = conn.execute("SELECT MAX(donem) FROM holdings").fetchone()[0]

    karsilastirilan = {s["fon_slug"] for s in satirlar if s["sira"] == 2}
    simdi, once = {}, {}
    for s in satirlar:
        if s["fon_slug"] in karsilastirilan:
            (simdi if s["sira"] == 1 else once)[(s["fon_slug"], s["ticker"])] = s

    # Hisse başına: her iki çeyrekte de tutan fonların adet oranları ve
    # bildirilen birim değerin değişimi (bölünme varsa gerçek fiyat değişiminden sapar)
    oranlar, birim_oranlari = {}, {}
    for (fon, ticker), s in simdi.items():
        o = once.get((fon, ticker))
        if o and o["adet"] and s["adet"] and o["deger"] and s["deger"]:
            oranlar.setdefault(ticker, []).append(s["adet"] / o["adet"])
            birim_oranlari.setdefault(ticker, []).append((s["deger"] / s["adet"]) / (o["deger"] / o["adet"]))
    getiriler = _ceyrek_getirileri(set(oranlar))

    hisseler = {}
    for (fon, ticker), s in simdi.items():
        k = hisseler.setdefault(ticker, {"ticker": ticker, "sirket": s["sirket"], "yeni": 0, "artiran": 0,
                                         "azaltan": 0, "cikan": 0, "tutan": 0, "onceki": 0, "deger": 0})
        k["tutan"] += 1
        k["deger"] += s["deger"] or 0
        o = once.get((fon, ticker))
        if o is None or not o["adet"]:
            k["yeni"] += 1
    for (fon, ticker), o in once.items():
        k = hisseler.setdefault(ticker, {"ticker": ticker, "sirket": o["sirket"], "yeni": 0, "artiran": 0,
                                         "azaltan": 0, "cikan": 0, "tutan": 0, "onceki": 0, "deger": 0})
        k["onceki"] += 1
        if (fon, ticker) not in simdi:
            k["cikan"] += 1
    for ticker, liste in oranlar.items():
        bolunme = 1.0
        if ticker in getiriler:
            bolunme = statistics.median(birim_oranlari[ticker]) / getiriler[ticker]
            if abs(bolunme - 1) < 0.15:          # fark küçükse bölünme yok, fiyat oynaması
                bolunme = 1.0
        for oran in liste:
            duzeltilmis = oran * bolunme - 1
            if duzeltilmis >= DEGISIM_ESIGI:
                hisseler[ticker]["artiran"] += 1
            elif duzeltilmis <= -DEGISIM_ESIGI:
                hisseler[ticker]["azaltan"] += 1

    def sirket_olayi(k):
        return (k["onceki"] == 0                                   # halka arz / bölünme
                or k["tutan"] == 0                                 # artık kimse tutmuyor
                or k["ticker"].endswith("Q") and len(k["ticker"]) == 5
                or k["onceki"] >= 5 and k["cikan"] / k["onceki"] >= SIRKET_OLAYI_PAYI)

    for k in hisseler.values():
        k["alan"] = k["yeni"] + k["artiran"]
        k["satan"] = k["azaltan"] + k["cikan"]
        k["deger_kisa"] = kisa_tutar(k["deger"])
    yeni_listelenen = sorted([k for k in hisseler.values() if k["onceki"] == 0 and k["tutan"] >= 3],
                             key=lambda k: (k["tutan"], k["deger"]), reverse=True)
    # Bu çeyrek yan şirket ayıran ana şirket (Honeywell -> Honeywell Aerospace): pozisyonlar
    # ayrılan şirkete geçtiği için düşmüş görünür, satış sayılmaz
    ayrilan_kokler = {_ilk_kelime(k["sirket"]) for k in yeni_listelenen}
    liste = [k for k in hisseler.values()
             if not sirket_olayi(k) and _ilk_kelime(k["sirket"]) not in ayrilan_kokler]

    def sirala(secilen, anahtar):
        return sorted(secilen, key=anahtar, reverse=True)[:adet]

    return {
        "donem_adi": donem_metni(son_donem) if son_donem else "",
        "fon_sayisi": len(karsilastirilan),
        "yeni_listelenen": yeni_listelenen[:8],
        "yeni_girilen": sirala([k for k in liste if k["yeni"] > 0], lambda k: (k["yeni"], k["deger"])),
        "en_cok_alinan": sirala([k for k in liste if k["alan"] > k["satan"]],
                                lambda k: (k["alan"] - k["satan"], k["deger"])),
        "en_cok_satilan": sirala([k for k in liste if k["satan"] > k["alan"]],
                                 lambda k: (k["satan"] - k["alan"], k["deger"])),
    }
