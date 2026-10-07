"""
Kripto sayfalarının veritabanı sorguları:

  cot(slug)               büyük fonların vadeli işlemlerdeki konumu (CFTC, haftalık)
  etf_kurumlari(slug)     takip edilen büyük kurumların kripto fonu (ETF) pozisyonları (13F)
  siyasetci_islemleri()   Kongre üyelerinin kripto para ve kripto fonu işlemleri
"""

from contextlib import closing

from piyasa.kripto.tanimlar import KRIPTO, KRIPTOLAR
from piyasa.kurallar import parti_bilgisi
from piyasa.veritabani import get_connection


def baglanti():
    return closing(get_connection())


def _yuzdelik(deger, liste):
    """Değer listenin neresinde: 0 en düşük, 100 en yüksek."""
    if not liste:
        return None
    return round(sum(1 for v in liste if v < deger) / max(len(liste) - 1, 1) * 100)


# ---------------------------------------------------------------------------
# CFTC: vadeli işlemlerde kurumlar ve hedge fonları
# ---------------------------------------------------------------------------

def _cot_yorumu(konum, degisim):
    if konum is None:
        return ""
    if konum >= 85:
        durum = "Kurumsal yatırımcıların alım pozisyonu son bir yılın en yüksek seviyesine yakın."
    elif konum >= 60:
        durum = "Kurumsal yatırımcılar son bir yılın ortalamasından daha iyimser."
    elif konum <= 15:
        durum = "Kurumsal yatırımcıların alım pozisyonu son bir yılın en düşük seviyesine yakın."
    elif konum <= 40:
        durum = "Kurumsal yatırımcılar son bir yılın ortalamasından daha temkinli."
    else:
        durum = "Kurumsal yatırımcıların konumu son bir yılın ortalaması civarında."
    yon = "artırdılar" if degisim > 0 else "azalttılar" if degisim < 0 else "değiştirmediler"
    return f"{durum} Geçen hafta net alım pozisyonlarını {yon}."


def cot(slug, hafta=104):
    """Haftalık seri ve son durum; veri yoksa None."""
    with baglanti() as conn:
        satirlar = [dict(s) for s in conn.execute(
            "SELECT * FROM kripto_cot WHERE coin = ? ORDER BY tarih DESC LIMIT ?", (slug, hafta)
        )]
    if not satirlar:
        return None
    satirlar.reverse()
    for s in satirlar:
        s["kurum_net"] = s["kurum_uzun"] - s["kurum_kisa"]
        s["hedge_net"] = s["hedge_uzun"] - s["hedge_kisa"]
    son = satirlar[-1]
    onceki = satirlar[-2] if len(satirlar) > 1 else son
    dort_once = satirlar[-5] if len(satirlar) > 4 else satirlar[0]
    konum = _yuzdelik(son["kurum_net"], [s["kurum_net"] for s in satirlar[-52:]])
    degisim = son["kurum_net"] - onceki["kurum_net"]
    return {
        "tarih": son["tarih"],
        "kurum_net": son["kurum_net"],
        "kurum_uzun": son["kurum_uzun"],
        "kurum_kisa": son["kurum_kisa"],
        "hedge_net": son["hedge_net"],
        "hedge_uzun": son["hedge_uzun"],
        "hedge_kisa": son["hedge_kisa"],
        "acik_pozisyon": son["acik_pozisyon"],
        "haftalik_degisim": degisim,
        "dort_haftalik_degisim": son["kurum_net"] - dort_once["kurum_net"],
        "konum": konum,
        "yorum": _cot_yorumu(konum, degisim),
        "seri": [[s["tarih"], s["kurum_net"]] for s in satirlar],
        "hedge_seri": [[s["tarih"], s["hedge_net"]] for s in satirlar],
    }


# ---------------------------------------------------------------------------
# 13F: büyük kurumların kripto fonu pozisyonları
# ---------------------------------------------------------------------------

def _donemler(conn, kodlar):
    yer = ", ".join("?" for _ in kodlar)
    return [r[0] for r in conn.execute(
        f"SELECT DISTINCT donem FROM holdings WHERE ticker IN ({yer}) ORDER BY donem DESC LIMIT 2", kodlar
    )]


def _pozisyonlar(conn, kodlar, donem):
    yer = ", ".join("?" for _ in kodlar)
    sonuc = {}
    for r in conn.execute(
        f"""SELECT fon_adi, fon_slug, ticker, SUM(deger) AS deger, SUM(adet) AS adet
            FROM holdings WHERE donem = ? AND ticker IN ({yer})
            GROUP BY fon_slug, ticker""",
        [donem, *kodlar],
    ):
        f = sonuc.setdefault(r["fon_slug"], {"fon_adi": r["fon_adi"], "fon_slug": r["fon_slug"], "fonlar": {}})
        f["fonlar"][r["ticker"]] = {"deger": r["deger"] or 0, "adet": r["adet"] or 0}
    return sonuc


def etf_kurumlari(slug):
    """
    Son çeyrekte coinin spot fonlarını (IBIT, FBTC...) tutan takip edilen kurumlar ve
    önceki çeyreğe göre değişim. Veri yoksa None.
    """
    k = KRIPTO.get(slug)
    kodlar = list(k["etfler"]) if k else []
    if not kodlar:
        return None
    with baglanti() as conn:
        donemler = _donemler(conn, kodlar)
        if not donemler:
            return None
        simdi = _pozisyonlar(conn, kodlar, donemler[0])
        once = _pozisyonlar(conn, kodlar, donemler[1]) if len(donemler) > 1 else {}

    kurumlar = []
    for fon_slug, f in simdi.items():
        deger = sum(x["deger"] for x in f["fonlar"].values())
        adet = sum(x["adet"] for x in f["fonlar"].values())
        onceki = once.get(fon_slug)
        onceki_adet = sum(x["adet"] for x in onceki["fonlar"].values()) if onceki else 0
        if not onceki:
            durum = "yeni"
        elif adet > onceki_adet * 1.05:
            durum = "artirdi"
        elif adet < onceki_adet * 0.95:
            durum = "azaltti"
        else:
            durum = "ayni"
        kurumlar.append({
            "fon_adi": f["fon_adi"], "fon_slug": fon_slug, "deger": deger, "durum": durum,
            "degisim": (adet / onceki_adet - 1) if onceki_adet else None,
            "fonlar": sorted(f["fonlar"], key=lambda t: -f["fonlar"][t]["deger"]),
        })
    kurumlar.sort(key=lambda x: -x["deger"])
    cikanlar = [{"fon_adi": f["fon_adi"], "fon_slug": s} for s, f in once.items() if s not in simdi]

    # Fon bazında: hangi kripto fonunu toplam ne kadar tutuyorlar
    fon_toplam = {}
    for f in simdi.values():
        for kod, x in f["fonlar"].items():
            fon_toplam[kod] = fon_toplam.get(kod, 0) + x["deger"]
    etfler = sorted(({"kod": kod, "ad": k["etfler"][kod], "deger": d} for kod, d in fon_toplam.items()),
                    key=lambda x: -x["deger"])

    return {
        "donem": donemler[0],
        "toplam": sum(x["deger"] for x in kurumlar),
        "kurumlar": kurumlar,
        "cikanlar": cikanlar,
        "etfler": etfler,
        "artiran": sum(1 for x in kurumlar if x["durum"] in ("yeni", "artirdi")),
        "azaltan": sum(1 for x in kurumlar if x["durum"] == "azaltti") + len(cikanlar),
    }


# ---------------------------------------------------------------------------
# Kongre üyelerinin kripto işlemleri
# ---------------------------------------------------------------------------

SAHIPLER = {"SP": "eşi adına", "JT": "ortak hesap", "DC": "çocuğu adına",
            "Spouse": "eşi adına", "Joint": "ortak hesap", "Child": "çocuğu adına"}


def siyasetci_islemleri(slug=None, limit=200):
    """Kripto para ve kripto fonu işlemleri, yeniden eskiye."""
    kosul, parametre = ("WHERE coin = ?", [slug]) if slug else ("", [])
    with baglanti() as conn:
        satirlar = [dict(s) for s in conn.execute(
            # Görevden ayrılan üyelerin partisi hisse kayıtlarından tamamlanır
            f"""SELECT k.*, COALESCE(k.party, (SELECT MAX(t.party) FROM transactions t
                                               WHERE t.person_slug = k.person_slug)) AS parti_kodu
                FROM kripto_islem k {kosul.replace('coin', 'k.coin')}
                ORDER BY transaction_date DESC, disclosed_date DESC LIMIT ?""",
            [*parametre, limit],
        )]
    for s in satirlar:
        s["parti_bilgisi"] = parti_bilgisi(s["parti_kodu"])
        s["kripto"] = KRIPTO.get(s["coin"])
        s["tur"] = "Fon (ETF)" if s["ticker"] else "Doğrudan"
        s["sahip"] = SAHIPLER.get(s["sahip"], s["sahip"])
    return satirlar


def siyasetci_ozeti(slug=None):
    """İşlem, kişi, alım/satım sayıları ve en çok işlem yapan üyeler."""
    kosul, parametre = ("WHERE coin = ?", [slug]) if slug else ("", [])
    with baglanti() as conn:
        o = dict(conn.execute(
            f"""SELECT COUNT(*) AS adet, COUNT(DISTINCT person_slug) AS kisi,
                       SUM(action = 'buy') AS alim, SUM(action = 'sell') AS satim,
                       SUM(CASE WHEN action = 'buy' THEN amount_min END) AS alim_alt,
                       SUM(CASE WHEN action = 'buy' THEN amount_max END) AS alim_ust,
                       SUM(CASE WHEN action = 'sell' THEN amount_min END) AS satim_alt,
                       SUM(CASE WHEN action = 'sell' THEN amount_max END) AS satim_ust
                FROM kripto_islem {kosul}""", parametre,
        ).fetchone())
        kisiler = [dict(s) for s in conn.execute(
            f"""SELECT person, person_slug,
                       COALESCE(MAX(party), (SELECT MAX(t.party) FROM transactions t
                                             WHERE t.person_slug = kripto_islem.person_slug)) AS party,
                       MAX(chamber) AS chamber, COUNT(*) AS adet,
                       SUM(action = 'buy') AS alim, SUM(action = 'sell') AS satim, MAX(transaction_date) AS son
                FROM kripto_islem {kosul} GROUP BY person_slug ORDER BY adet DESC LIMIT 10""", parametre,
        )]
        coinler = dict(conn.execute("SELECT coin, COUNT(*) FROM kripto_islem GROUP BY coin").fetchall())
    for k in kisiler:
        k["parti_bilgisi"] = parti_bilgisi(k["party"])
    o["kisiler"] = kisiler
    o["coinler"] = {k["slug"]: coinler.get(k["slug"], 0) for k in KRIPTOLAR}
    return o
