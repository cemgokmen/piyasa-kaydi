"""
Olası çıkar çatışmaları: bir Kongre üyesinin, üyesi olduğu komitenin
yasama ve denetim alanına giren sektörden hisse alması ya da satması.

Örnek: Silahlı Kuvvetler Komitesi üyesinin bir savunma şirketinin hissesini
alması. Bu bir suçlama değildir; komitelerin yetki alanı geniştir ve işlemi
üyenin eşi ya da bir varlık yöneticisi yapmış olabilir. Yalnızca dikkat
çekilmesi gereken bir örüntüdür.

Not: Komite üyelikleri günceldir; geçmişteki bir işlemin yapıldığı gün üye
farklı bir komitede olabilir.
"""

from contextlib import closing

from piyasa.analiz.sektorler import KOMITE_ADLARI, KOMITE_SEKTORLERI
from piyasa.bicim import kisa_aralik, sirket_kisa_ad
from piyasa.kayitlar import islem_hazirla
from piyasa.kurallar import parti_bilgisi
from piyasa.onbellek import sureli
from piyasa.veritabani import get_connection


def _hesapla():
    with closing(get_connection()) as conn:
        satirlar = conn.execute(
            """SELECT t.id, t.person_slug, s.sektor, k.komite, k.unvan
               FROM transactions t
               JOIN uye u ON u.slug = t.person_slug
               JOIN komite_uyeligi k ON k.bioguide = u.bioguide
               JOIN sirket s ON s.ticker = t.ticker
               WHERE t.chamber IS NOT NULL AND s.sektor IS NOT NULL"""
        ).fetchall()

    islemler = {}
    for s in satirlar:
        if s["sektor"] in KOMITE_SEKTORLERI.get(s["komite"], ()):
            kayit = islemler.setdefault(s["id"], {"sektor": s["sektor"], "komiteler": []})
            ad = KOMITE_ADLARI[s["komite"]]
            if s["unvan"]:
                ad += f" ({'Başkan' if 'Chair' in s['unvan'] else 'Kıdemli üye' if 'Ranking' in s['unvan'] else s['unvan']})"
            if ad not in kayit["komiteler"]:
                kayit["komiteler"].append(ad)
    return islemler


@sureli(5 * 60)
def cakisan_islemler():
    """{işlem id: {'sektor': ..., 'komiteler': [...]}} — 5 dakika önbellekli."""
    return _hesapla()


def onbellegi_temizle():
    cakisan_islemler.temizle()


def isaretle(islemler):
    """Şablona giden işlem listesine 'cakisma' alanını ekler."""
    cakisanlar = cakisan_islemler()
    for k in islemler:
        k["cakisma"] = cakisanlar.get(k["id"])
    return islemler


def uye_komiteleri(slug):
    """Bir üyenin komiteleri ve denetledikleri sektörler."""
    with closing(get_connection()) as conn:
        satirlar = conn.execute(
            """SELECT k.komite, k.unvan FROM uye u
               JOIN komite_uyeligi k ON k.bioguide = u.bioguide
               WHERE u.slug = ? ORDER BY k.komite""",
            (slug,),
        ).fetchall()
    return [
        {"ad": KOMITE_ADLARI.get(s["komite"], s["komite"]), "unvan": s["unvan"],
         "sektorler": KOMITE_SEKTORLERI.get(s["komite"], [])}
        for s in satirlar
    ]


def _sektor_hisseleri(sektorler):
    """Sektör başına işlem yapılan hisseler (çok işlem görenden aza): [{'sektor', 'hisseler'}]"""
    return [
        {"sektor": sektor,
         "hisseler": sorted(hisseler.values(), key=lambda h: (h["alim"] + h["satim"], h["ust"]), reverse=True)}
        for sektor, hisseler in sorted(sektorler.items())
    ]


def rapor(limit=100):
    """Çıkar çatışması sayfası: üye bazında özet ve son işlemler."""
    cakisanlar = cakisan_islemler()
    if not cakisanlar:
        return {"uyeler": [], "islemler": [], "toplam": 0}

    idler = list(cakisanlar)
    with closing(get_connection()) as conn:
        yer = ",".join("?" * len(idler))
        satirlar = conn.execute(
            f"SELECT * FROM transactions WHERE id IN ({yer}) ORDER BY disclosed_date DESC, amount_max DESC",
            idler,
        ).fetchall()
        toplamlar = {s["person_slug"]: s["n"] for s in conn.execute(
            "SELECT person_slug, COUNT(*) AS n FROM transactions WHERE chamber IS NOT NULL GROUP BY person_slug")}

    uyeler = {}
    for s in satirlar:
        u = uyeler.setdefault(s["person_slug"], {
            "slug": s["person_slug"], "ad": s["person"], "party": s["party"], "bolge": s["state"],
            "adet": 0, "alim": 0, "alt": 0, "ust": 0, "komiteler": set(), "sektorler": set(),
            "hisseler": {},
        })
        c = cakisanlar[s["id"]]
        u["adet"] += 1
        u["alim"] += s["action"] == "buy"
        u["alt"] += s["amount_min"] or 0
        u["ust"] += s["amount_max"] or 0
        u["komiteler"].update(c["komiteler"])
        u["sektorler"].add(c["sektor"])
        h = u["hisseler"].setdefault(c["sektor"], {}).setdefault(s["ticker"], {
            "ticker": s["ticker"], "ad": sirket_kisa_ad(s["asset_name"] or s["company"]),
            "alim": 0, "satim": 0, "ust": 0,
        })
        h["alim" if s["action"] == "buy" else "satim"] += 1
        h["ust"] += s["amount_max"] or 0

    liste = []
    for u in uyeler.values():
        toplam = toplamlar.get(u["slug"], u["adet"])
        liste.append({**u, "parti": parti_bilgisi(u["party"]), "toplam": toplam,
                      "oran": u["adet"] / toplam if toplam else 0,
                      "hacim": kisa_aralik(u["alt"], u["ust"]),
                      "komiteler": sorted(u["komiteler"]), "sektorler": sorted(u["sektorler"]),
                      "hisseler": _sektor_hisseleri(u["hisseler"])})
    liste.sort(key=lambda u: (u["ust"], u["adet"]), reverse=True)

    islemler = isaretle([islem_hazirla(s) for s in satirlar[:limit]])
    return {"uyeler": liste, "islemler": islemler, "toplam": len(satirlar)}
