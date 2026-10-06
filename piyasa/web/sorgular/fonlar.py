"""Fon listesi ve fon sayfası: portföy, çeyrekler arası değişim, pasta grafiği."""

from piyasa.bicim import donem_metni, kisa_tutar
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


def fonlar():
    """Her fon kendi son çeyreğiyle; daha eski çeyrekte kalan fon da listelenir."""
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
