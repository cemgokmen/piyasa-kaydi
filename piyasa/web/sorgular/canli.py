"""
Canlı akış: ABD yöneticileri (Form 4), Kongre üyeleri ve KAP bildirimleri tek
zaman sırasında. Bildirimler 15 dakikada bir toplanır (bkz. piyasa/zamanlama.py).
"""

from datetime import UTC, date, datetime, timedelta, timezone

from piyasa.bicim import kisa_aralik, kisa_tutar, sirket_gorunen_ad, tr_baslik, tr_cumle, unvan
from piyasa.bist.sorgular import KAP_BILDIRIM, kisa_unvan
from piyasa.kurallar import GECERLI_KOD, TEMIZ, parti_bilgisi
from piyasa.web.sorgular.ortak import baglanti

TURKIYE = timezone(timedelta(hours=3))
KAYNAKLAR = {"abd": "ABD yöneticileri", "siyaset": "Siyasetçiler", "bist": "Borsa İstanbul"}
YONETICI_GUN = 4            # Form 4: son 4 günün bildirimleri (hafta sonunu da kapsasın)
SIYASET_GUN = 14            # Kongre bildirimleri seyrek gelir
KAP_GUN = 4
EN_FAZLA = 150


def _tr_saat(utc_metni):
    """UTC ISO zamanını Türkiye saatine çevirir: (gün, 'SS:DD')."""
    try:
        z = datetime.fromisoformat(utc_metni)
    except (TypeError, ValueError):
        return None, ""
    if z.tzinfo is None:
        z = z.replace(tzinfo=UTC)
    z = z.astimezone(TURKIYE)
    return z.date().isoformat(), z.strftime("%H:%M")


def _tl(n):
    return kisa_tutar(n)[:-2] + " ₺"


def _yoneticiler(conn):
    satirlar = conn.execute(
        f"""SELECT person, MAX(person_slug) AS slug, MAX(job_title) AS gorev, ticker,
                   MAX(COALESCE(company, asset_name)) AS sirket, action,
                   SUM(amount_max) AS tutar, COUNT(*) AS adet,
                   disclosed_date, MIN(fetched_at) AS alindi, MAX(source_url) AS kaynak
            FROM transactions
            WHERE chamber IS NULL AND {TEMIZ} AND {GECERLI_KOD} AND disclosed_date >= ?
              AND action IN ('buy', 'sell') AND amount_max > 0
            GROUP BY person, ticker, action, disclosed_date
            ORDER BY disclosed_date DESC, alindi DESC LIMIT ?""",
        ((date.today() - timedelta(days=YONETICI_GUN)).isoformat(), EN_FAZLA),
    ).fetchall()
    sonuc = []
    for r in satirlar:
        gun, saat = _tr_saat(r["alindi"])
        # Saat yalnızca bildirimi gün içinde aldıysak gösterilir; günlük dizinden gelenlerde
        # alınma zamanı ertesi sabahtır, yayın saatini yansıtmaz
        saat = saat if gun == r["disclosed_date"] else ""
        sonuc.append({
            "kaynak": "abd", "gun": r["disclosed_date"], "saat": saat,
            "islem": r["action"], "tutar": kisa_tutar(r["tutar"]), "tutar_ham": r["tutar"],
            "kod": r["ticker"], "kod_adres": f"/hisse/{r['ticker']}",
            "sirket": sirket_gorunen_ad(r["sirket"]) if r["sirket"] else r["ticker"],
            "kisi": r["person"], "kisi_adres": f"/kisi/{r['slug']}" if r["slug"] else None,
            "rol": unvan(r["gorev"]) if r["gorev"] else "Yönetici",
            "not": f"{r['adet']} işlem" if r["adet"] > 1 else "",
            "dis_adres": r["kaynak"], "dis_ad": "SEC",
        })
    return sonuc


def _siyasetciler(conn):
    satirlar = conn.execute(
        """SELECT person, MAX(person_slug) AS slug, MAX(party) AS parti, MAX(chamber) AS meclis, ticker,
                  MAX(asset_name) AS sirket, action, SUM(amount_min) AS alt, SUM(amount_max) AS ust,
                  COUNT(*) AS adet, disclosed_date, MAX(source_url) AS kaynak
           FROM transactions
           WHERE chamber IS NOT NULL AND disclosed_date >= ? AND action IN ('buy', 'sell')
           GROUP BY person, ticker, action, disclosed_date
           ORDER BY disclosed_date DESC LIMIT ?""",
        ((date.today() - timedelta(days=SIYASET_GUN)).isoformat(), EN_FAZLA),
    ).fetchall()
    return [{
        "kaynak": "siyaset", "gun": r["disclosed_date"], "saat": "",
        "islem": r["action"], "tutar": kisa_aralik(r["alt"], r["ust"]), "tutar_ham": r["ust"],
        "kod": r["ticker"], "kod_adres": f"/hisse/{r['ticker']}",
        "sirket": sirket_gorunen_ad(r["sirket"]) if r["sirket"] else r["ticker"],
        "kisi": r["person"], "kisi_adres": f"/kisi/{r['slug']}" if r["slug"] else None,
        "rol": "Senatör" if r["meclis"] == "senate" else "Temsilci",
        "parti": parti_bilgisi(r["parti"]),
        "not": f"{r['adet']} işlem" if r["adet"] > 1 else "",
        "dis_adres": r["kaynak"], "dis_ad": "Bildirim",
    } for r in satirlar]


def _kap(conn):
    satirlar = conn.execute(
        """SELECT b.indeks, b.kod, b.tur, b.baslik, b.ozet, b.yayin, s.unvan,
                  p.kisi, p.kisi_turu, p.islem, p.tutar, p.gorev,
                  (SELECT SUM(g.nominal * g.fiyat) FROM kap_geri_alim g WHERE g.indeks = b.indeks) AS geri_tutar
           FROM kap_bildirim b
           LEFT JOIN kap_pay_islem p USING (indeks)
           LEFT JOIN bist_sirket s ON s.kod = b.kod
           WHERE b.yayin >= ? AND b.tur IN ('pay', 'geri_alim', 'ozel') AND b.kod IS NOT NULL
           ORDER BY b.yayin DESC LIMIT ?""",
        ((date.today() - timedelta(days=KAP_GUN)).isoformat(), EN_FAZLA),
    ).fetchall()
    sonuc = []
    for r in satirlar:
        k = {
            "kaynak": "bist", "gun": r["yayin"][:10], "saat": r["yayin"][11:16],
            "kod": r["kod"], "kod_adres": f"/bist/{r['kod']}",
            "sirket": tr_baslik(kisa_unvan(r["unvan"])) if r["unvan"] else r["kod"],
            "dis_adres": KAP_BILDIRIM.format(indeks=r["indeks"]), "dis_ad": "KAP",
            "islem": None, "tutar": "", "tutar_ham": None, "kisi": None, "kisi_adres": None, "not": "",
        }
        if r["tur"] == "pay":
            fon = r["kisi_turu"] == "fon"
            k["islem"] = r["islem"]
            k["etiket"] = "Fon payı" if fon else "İçeriden işlem"
            k["kisi"] = tr_baslik(r["kisi"]) if r["kisi"] else None
            k["rol"] = tr_cumle(r["gorev"]) if r["gorev"] and not fon else ("Fon" if fon else "")
            k["tutar"] = _tl(r["tutar"]) if r["tutar"] else ""
            k["tutar_ham"] = r["tutar"]
            if not r["islem"]:
                k["not"] = tr_cumle(r["ozet"]) if r["ozet"] else "Pay alım satım bildirimi"
        elif r["tur"] == "geri_alim":
            k["etiket"] = "Geri alım"
            k["islem"] = "buy"
            k["kisi"] = "Şirketin kendisi"
            k["tutar"] = _tl(r["geri_tutar"]) if r["geri_tutar"] else ""
            k["tutar_ham"] = r["geri_tutar"]
        else:
            k["etiket"] = "Özel durum"
            k["not"] = tr_cumle(r["ozet"] or r["baslik"] or "")
        sonuc.append(k)
    return sonuc


def akis(kaynak=None):
    """Bütün kaynaklardan en yeni bildirimler, yeniden eskiye; gün başlıklarıyla gruplanmış."""
    with baglanti() as conn:
        ogeler = []
        if kaynak in (None, "abd"):
            ogeler += _yoneticiler(conn)
        if kaynak in (None, "siyaset"):
            ogeler += _siyasetciler(conn)
        if kaynak in (None, "bist"):
            ogeler += _kap(conn)
    # Saati olmayan (gün sonu dizininden gelen) kayıtlar o günün en sonuna değil, başına yakın
    # dursun diye boş saat '00:00' sayılır; aynı saatte büyük tutar önce
    ogeler.sort(key=lambda o: (o["gun"], o["saat"] or "00:00", o["tutar_ham"] or 0), reverse=True)
    ogeler = ogeler[:EN_FAZLA]

    bugun = date.today()
    gunler = []
    for o in ogeler:
        if not gunler or gunler[-1]["gun"] != o["gun"]:
            g = date.fromisoformat(o["gun"])
            ad = "Bugün" if g == bugun else "Dün" if g == bugun - timedelta(days=1) else None
            gunler.append({"gun": o["gun"], "ad": ad, "ogeler": []})
        gunler[-1]["ogeler"].append(o)
    return gunler


def son_dakika(adet=6):
    """Ana sayfa için: ABD, Borsa İstanbul ve Kongre'den en yeniler karışık (tek kaynak listeyi doldurmasın)."""
    ogeler = [o for g in akis() for o in g["ogeler"]]
    secilen = []
    for kaynak, n in (("abd", 3), ("bist", 3), ("siyaset", 1)):
        secilen += [o for o in ogeler if o["kaynak"] == kaynak][:n]
    secilen.sort(key=lambda o: (o["gun"], o["saat"] or "00:00"), reverse=True)
    return secilen[:adet]


def bugun_sayilari():
    """Üstteki özet: bugün ve dün gelen bildirim sayıları."""
    bugun = date.today().isoformat()
    with baglanti() as conn:
        def tek(sorgu, *p):
            return conn.execute(sorgu, p).fetchone()[0] or 0
        return {
            "abd": tek(f"SELECT COUNT(*) FROM transactions WHERE chamber IS NULL AND {TEMIZ} AND disclosed_date = ?",
                       bugun),
            "abd_alim": tek(f"""SELECT COUNT(*) FROM transactions WHERE chamber IS NULL AND {TEMIZ}
                               AND disclosed_date = ? AND action = 'buy' AND amount_max > 0""", bugun),
            "siyaset": tek("SELECT COUNT(*) FROM transactions WHERE chamber IS NOT NULL AND disclosed_date = ?", bugun),
            "kap": tek("SELECT COUNT(*) FROM kap_bildirim WHERE substr(yayin, 1, 10) = ?", bugun),
            "son_kap": tek("SELECT MAX(yayin) FROM kap_bildirim") or None,
        }
