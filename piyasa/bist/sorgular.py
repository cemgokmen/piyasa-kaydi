"""
Borsa İstanbul sayfalarının veritabanı sorguları (KAP bildirimlerinden):

  sirketler()             BIST 100 şirketleri
  sirket(kod)             tek şirket (BIST 100 dışındakiler KAP kayıtlarından)
  pay_islemleri()         pay alım satım bildirimleri: yöneticiler, büyük ortaklar ve fonlar
  geri_alim_ozeti()       son günlerde payını geri alan şirketler
  geri_alimlar(kod)       bir şirketin geri alım işlemleri
  ozel_aciklamalar(kod)   bir şirketin son özel durum açıklamaları (başlıklar)
"""

import re
from contextlib import closing
from datetime import date, timedelta

from piyasa.bicim import tr_baslik, tr_cumle
from piyasa.veritabani import get_connection

KAP_BILDIRIM = "https://www.kap.org.tr/tr/Bildirim/{indeks}"
KISI_TURLERI = {"kisi": "Kişi", "sirket": "Şirket", "fon": "Fon kurucusu"}


# Unvanın sonundaki hukuki ve genel ekler: 'Aselsan Elektronik Sanayi ve Ticaret A.Ş.' -> 'Aselsan Elektronik'
_UNVAN_EKLERI = re.compile(
    r"(\s+(ve|ile))?\s+(Sanayi|Sanayii|Ticaret|Anonim|Şirketi|A\.Ş\.?|A\.O\.?|T\.A\.Ş\.?|T\.A\.O\.?|Ltd\.?|Şti\.?)\.?$",
    re.I)


def kisa_unvan(unvan):
    """Haber araması ve başlıklar için kısa ad."""
    if not unvan:
        return unvan
    onceki = None
    while onceki != unvan:
        onceki, unvan = unvan, _UNVAN_EKLERI.sub("", unvan).strip(" ,.")
    return unvan


def baglanti():
    return closing(get_connection())


def _unvan(unvan):
    return tr_baslik(unvan) if unvan else unvan


LISTELER = {"tum": "Bütün hisseler", "xu100": "BIST 100", "xu030": "BIST 30"}


def _sektor_adi(ad):
    return tr_cumle(ad) if ad else None


def sirketler(liste="tum", sektor=None):
    """
    Pay piyasasında işlem gören şirketler (KAP sektör listesinde olanlar; yalnızca tahvil
    ihraç edenler hariç). liste: tum | xu100 | xu030; sektor: ana sektör adı (KAP'taki haliyle).
    """
    kosullar = ["ana_sektor IS NOT NULL OR xu100 = 1"]
    parametre = []
    if liste in ("xu100", "xu030"):
        kosullar.append(f"{liste} = 1")
    if sektor:
        kosullar.append("ana_sektor = ?")
        parametre.append(sektor)
    nerede = " AND ".join(f"({k})" for k in kosullar)
    with baglanti() as conn:
        return [dict(r, unvan=_unvan(r["unvan"]), sektor_adi=_sektor_adi(r["sektor"]),
                     ana_sektor_adi=_sektor_adi(r["ana_sektor"]))
                for r in conn.execute(
                    f"SELECT kod, unvan, xu100, xu030, sehir, ana_sektor, sektor FROM bist_sirket WHERE {nerede} "
                    "ORDER BY kod", parametre)]


def sektorler():
    """[(ana sektör, görünen ad, şirket sayısı)] — büyükten küçüğe."""
    with baglanti() as conn:
        return [(r["ana_sektor"], _sektor_adi(r["ana_sektor"]), r["n"]) for r in conn.execute(
            """SELECT ana_sektor, COUNT(*) AS n FROM bist_sirket WHERE ana_sektor IS NOT NULL
               GROUP BY ana_sektor ORDER BY n DESC""")]


def benzerler(kod, sektor, ana_sektor, adet=12):
    """Aynı alt sektördeki (yetmezse ana sektördeki) diğer şirketler; BIST 100 önce."""
    if not ana_sektor:
        return []
    with baglanti() as conn:
        satirlar = [dict(r) for r in conn.execute(
            """SELECT kod, unvan, xu100 FROM bist_sirket WHERE kod != ? AND (sektor = ? OR ana_sektor = ?)
               ORDER BY (sektor = ?) DESC, xu100 DESC, kod LIMIT ?""",
            (kod, sektor, ana_sektor, sektor, adet))]
    return [dict(r, unvan=_unvan(r["unvan"])) for r in satirlar]


def sirket(kod):
    """Borsa İstanbul şirketi (KAP listesinden) ya da KAP'ta bildirimi olan şirket; yoksa None."""
    with baglanti() as conn:
        r = conn.execute("SELECT kod, unvan, xu100, xu030, sehir, ana_sektor, sektor FROM bist_sirket WHERE kod = ?",
                         (kod,)).fetchone()
        if r:
            return dict(r, unvan=_unvan(r["unvan"]), sehir=tr_baslik(r["sehir"]) if r["sehir"] else None,
                        sektor_adi=_sektor_adi(r["sektor"]), ana_sektor_adi=_sektor_adi(r["ana_sektor"]))
        # BIST 100 dışında: bildirimi olan şirket (unvanı şirketin kendi gönderdiği bildirimden)
        b = conn.execute(
            """SELECT kod, gonderen FROM kap_bildirim WHERE kod = ?
               ORDER BY (gonderen LIKE '%PORTFÖY%' OR gonderen LIKE '%KAMUYU%' OR gonderen LIKE '%EMEKLİLİK%'),
                        yayin DESC LIMIT 1""", (kod,)).fetchone()
    if not b:
        return None
    gonderen = b["gonderen"] or ""
    kendi = not any(k in gonderen.upper() for k in ("PORTFÖY", "KAMUYU", "EMEKLİLİK"))
    return {"kod": kod, "unvan": _unvan(gonderen) if kendi else kod, "xu100": 0, "xu030": 0, "sehir": None,
            "ana_sektor": None, "sektor": None, "sektor_adi": None, "ana_sektor_adi": None}


def _islem(r):
    k = dict(r)
    k["adres"] = KAP_BILDIRIM.format(indeks=k["indeks"])
    k["kisi_turu_ad"] = KISI_TURLERI.get(k["kisi_turu"], "")
    k["islem_metni"] = {"buy": "Alım", "sell": "Satım"}.get(k["islem"], "Bildirim")
    k["tarih"] = k["islem_tarihi"] or (k["yayin"] or "")[:10]
    k["gorev"] = tr_cumle(k.get("gorev"))
    k["kisi"] = tr_baslik(k["kisi"]) if k.get("kisi") else k.get("kisi")
    k["unvan"] = _unvan(k.get("unvan"))
    return k


def pay_islemleri(kod=None, gun=None, limit=200, sadece_cozulen=False, kisi_turu=None):
    kosullar, parametre = [], []
    if kod:
        kosullar.append("p.kod = ?")
        parametre.append(kod)
    if gun:
        kosullar.append("b.yayin >= ?")
        parametre.append((date.today() - timedelta(days=gun)).isoformat())
    if sadece_cozulen:
        kosullar.append("p.islem IS NOT NULL")
    if kisi_turu:
        kosullar.append("p.kisi_turu = ?")
        parametre.append(kisi_turu)
    nerede = ("WHERE " + " AND ".join(kosullar)) if kosullar else ""
    with baglanti() as conn:
        return [_islem(r) for r in conn.execute(
            f"""SELECT p.*, b.yayin, b.ozet, s.unvan, s.xu100
                FROM kap_pay_islem p JOIN kap_bildirim b USING (indeks)
                LEFT JOIN bist_sirket s ON s.kod = p.kod
                {nerede} ORDER BY b.yayin DESC LIMIT ?""",
            [*parametre, limit],
        )]


def pay_ozeti(gun=30):
    """Son 'gun' günde içeriden (kişi ve şirket) alım ve satımlar; fon eşik bildirimleri ayrı sayılır."""
    bas = (date.today() - timedelta(days=gun)).isoformat()
    with baglanti() as conn:
        o = dict(conn.execute(
            """SELECT COUNT(*) AS adet, COUNT(DISTINCT p.kod) AS sirket,
                      SUM(p.islem = 'buy' AND p.kisi_turu != 'fon') AS alim,
                      SUM(p.islem = 'sell' AND p.kisi_turu != 'fon') AS satim,
                      SUM(CASE WHEN p.islem = 'buy' AND p.kisi_turu != 'fon' THEN p.tutar END) AS alim_tutar,
                      SUM(CASE WHEN p.islem = 'sell' AND p.kisi_turu != 'fon' THEN p.tutar END) AS satim_tutar,
                      SUM(p.kisi_turu = 'fon') AS fon
               FROM kap_pay_islem p JOIN kap_bildirim b USING (indeks) WHERE b.yayin >= ?""", (bas,),
        ).fetchone())
        # İçeriden en çok alınan şirketler (TL)
        o["en_cok_alinan"] = [dict(r, unvan=_unvan(r["unvan"])) for r in conn.execute(
            """SELECT p.kod, MAX(s.unvan) AS unvan, SUM(p.tutar) AS tutar, COUNT(*) AS adet,
                      COUNT(DISTINCT p.kisi) AS kisi
               FROM kap_pay_islem p JOIN kap_bildirim b USING (indeks) LEFT JOIN bist_sirket s ON s.kod = p.kod
               WHERE b.yayin >= ? AND p.islem = 'buy' AND p.kisi_turu != 'fon' AND p.tutar IS NOT NULL
               GROUP BY p.kod ORDER BY tutar DESC LIMIT 10""", (bas,))]
    return o


def geri_alim_ozeti(gun=30, limit=25):
    """Son 'gun' günde geri alım yapan şirketler, toplam tutara göre."""
    bas = (date.today() - timedelta(days=gun)).isoformat()
    with baglanti() as conn:
        satirlar = [dict(r) for r in conn.execute(
            """SELECT g.kod, MAX(s.unvan) AS unvan, MAX(s.xu100) AS xu100, SUM(g.nominal * g.fiyat) AS tutar,
                      SUM(g.nominal) AS nominal, SUM(g.oran) AS oran, COUNT(DISTINCT g.islem_tarihi) AS gun,
                      MAX(g.islem_tarihi) AS son
               FROM kap_geri_alim g LEFT JOIN bist_sirket s ON s.kod = g.kod
               WHERE g.islem_tarihi >= ? GROUP BY g.kod ORDER BY tutar DESC""", (bas,))]
    for r in satirlar:
        r["unvan"] = _unvan(r["unvan"])
    return {"sirketler": satirlar[:limit], "sirket_sayisi": len(satirlar),
            "toplam": sum(r["tutar"] or 0 for r in satirlar)}


def geri_alimlar(kod, limit=60):
    with baglanti() as conn:
        satirlar = [dict(r, tutar=r["nominal"] * r["fiyat"], adres=KAP_BILDIRIM.format(indeks=r["indeks"]))
                    for r in conn.execute(
                        """SELECT islem_tarihi, nominal, oran, fiyat, indeks FROM kap_geri_alim WHERE kod = ?
                           ORDER BY islem_tarihi DESC, fiyat LIMIT ?""", (kod, limit))]
        toplam = conn.execute(
            """SELECT SUM(nominal * fiyat) AS tutar, SUM(nominal) AS nominal, SUM(oran) AS oran,
                      MIN(islem_tarihi) AS ilk FROM kap_geri_alim WHERE kod = ? AND islem_tarihi >= ?""",
            (kod, (date.today() - timedelta(days=90)).isoformat())).fetchone()
    return {"satirlar": satirlar, "son_90": dict(toplam) if toplam and toplam["tutar"] else None}


def ozel_aciklamalar(kod, limit=15):
    with baglanti() as conn:
        return [dict(r, adres=KAP_BILDIRIM.format(indeks=r["indeks"])) for r in conn.execute(
            """SELECT indeks, baslik, ozet, yayin FROM kap_bildirim WHERE kod = ? AND tur = 'ozel'
               ORDER BY yayin DESC LIMIT ?""", (kod, limit))]


def son_islem_tarihleri(kodlar):
    """{kod: son içeriden işlem tarihi} — liste sayfasındaki sütun için."""
    if not kodlar:
        return {}
    yer = ", ".join("?" for _ in kodlar)
    with baglanti() as conn:
        return {r["kod"]: dict(r) for r in conn.execute(
            f"""SELECT p.kod, MAX(b.yayin) AS son, SUM(p.islem = 'buy') AS alim, SUM(p.islem = 'sell') AS satim,
                       COUNT(*) AS bildirim
                FROM kap_pay_islem p JOIN kap_bildirim b USING (indeks)
                WHERE p.kod IN ({yer}) AND b.yayin >= ? AND p.kisi_turu != 'fon' GROUP BY p.kod""",
            [*kodlar, (date.today() - timedelta(days=90)).isoformat()])}
