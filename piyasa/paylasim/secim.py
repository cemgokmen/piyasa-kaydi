"""
Paylaşılacak bildirimlerin seçimi. Her aday: {anahtar, tur, onem, metin}. Önem, işlemin dolar
karşılığıdır (KAP için TL ÷ dolar kuru); tanınmış siyasetçilerin işlemleri öne alınır.

Eşikler gürültüyü ayıklar: küçük işlemler, fonların eşik bildirimleri ve kapalı uçlu fonlarda
her gün işlem yapan büyük ortaklar paylaşılmaz.
"""

from datetime import date, datetime, timedelta

from piyasa.bicim import sirket_gorunen_ad, tr_baslik, tr_cumle, unvan
from piyasa.bist.sorgular import kisa_unvan
from piyasa.kurallar import GECERLI_KOD, TEMIZ
from piyasa.paylasim import metin

KAP_ESIK = 5_000_000            # TL
GERI_ALIM_ESIK = 20_000_000     # TL
FORM4_ALIM_ESIK = 1_000_000     # dolar
FORM4_SATIS_ESIK = 25_000_000   # dolar: satışlar çoğunlukla planlı, yalnızca çok büyükleri haber
ORTAK_ESIK = 10_000_000         # dolar: yönetici olmayan %10 ortakların işlemleri
KONGRE_ESIK = 250_000           # dolar (bildirilen aralığın üst sınırı)
# İşlemleri en çok takip edilen üyeler: tutardan bağımsız paylaşılır
UNLU_SIYASETCILER = ("Nancy Pelosi", "Marjorie Taylor Greene", "Ro Khanna", "Josh Gottheimer", "Dan Crenshaw",
                     "Tommy Tuberville", "Mark Warner", "Rand Paul", "Sheldon Whitehouse")
UST_YONETIM = ("CEO", "CFO", "Yönetim kurulu başkanı", "Başkan", "Kurucu")
TR_UNVANLAR = {"Yönetim kurulu üyesi", "%10 üzeri ortak", "Bildirim yükümlüsü", "Üst düzey yönetici"}


def _rol(ham):
    """Form 4 unvanı → kısa Türkçe rol ('CEO', 'CFO', 'Yönetim kurulu üyesi', ...)."""
    if not ham:
        return ""
    if ham in TR_UNVANLAR:
        return ham
    tr = unvan(ham) or ""
    for oncelik in ("CEO", "CFO", "Yönetim kurulu başkanı"):
        if oncelik in tr:
            return oncelik
    return tr.split(",")[0].strip()


def _bist_fiyatlari():
    """Son BIST kapanışları (sitenin paylaşılan fiyat dosyasından; indirme yapmaz)."""
    try:
        from piyasa.bist import piyasa
        piyasa._dosyadan_oku()
        return piyasa._durum["veri"]
    except Exception:
        return {}


def _fiyat_tutarli(kod, fiyat):
    """
    Bildirimdeki fiyat bugünkü fiyattan 5 kattan fazla sapıyorsa veri okuma hatası say ve paylaşma
    (ör. '45.221' ondalığı binlik sanılırsa). Fiyat bilinmiyorsa engelleme.
    """
    guncel = (_bist_fiyatlari().get(kod) or {}).get("fiyat")
    if not fiyat or not guncel:
        return True
    return 0.2 <= fiyat / guncel <= 5


def kap_islemleri(conn, bas, kur):
    satirlar = conn.execute(
        """SELECT p.indeks, p.kod, p.kisi, p.kisi_turu, p.islem, p.tutar, p.nominal, p.fiyat, p.gorev,
                  p.oran_sonra, p.islem_tarihi, b.yayin, s.unvan
           FROM kap_pay_islem p JOIN kap_bildirim b USING (indeks) LEFT JOIN bist_sirket s ON s.kod = p.kod
           WHERE b.yayin >= ? AND p.islem IN ('buy', 'sell') AND p.kisi_turu != 'fon' AND p.tutar >= ?""",
        (bas, KAP_ESIK)).fetchall()
    sonuc = []
    for r in satirlar:
        x = dict(r)
        x["sirket"] = tr_baslik(kisa_unvan(x["unvan"])) if x["unvan"] else x["kod"]
        ham = x["kisi"]
        x["kisi"] = tr_baslik(ham) if ham else x["sirket"]
        x["kisi_kisa"] = tr_baslik(kisa_unvan(ham)) if ham else x["sirket"]
        if not _fiyat_tutarli(x["kod"], x.get("fiyat")):
            continue
        x["gorev"] = tr_cumle(x["gorev"]) if x.get("gorev") else None
        x["islem_tarihi"] = x["islem_tarihi"] or x["yayin"][:10]
        sonuc.append({"anahtar": f"kap:{x['indeks']}", "tur": "KAP içeriden", "onem": x["tutar"] / kur,
                      "metin": metin.kap_islem(x), "kaynak": x})
    return sonuc


def geri_alimlar(conn, bas, kur):
    """Her şirketin son günlerdeki geri alımları (bildirim programın bütün geçmişini içerir; tarihe göre süzülür)."""
    gun_bas = (date.fromisoformat(bas[:10]) - timedelta(days=2)).isoformat()
    satirlar = conn.execute(
        """SELECT g.kod, SUM(g.nominal * g.fiyat) AS tutar, SUM(g.nominal * g.fiyat) / SUM(g.nominal) AS ortalama, MAX(g.islem_tarihi) AS son_tarih, s.unvan,
                  (SELECT SUM(x.nominal * x.fiyat) FROM kap_geri_alim x WHERE x.kod = g.kod AND x.islem_tarihi >= ?) AS toplam_90
           FROM kap_geri_alim g JOIN kap_bildirim b USING (indeks) LEFT JOIN bist_sirket s ON s.kod = g.kod
           WHERE b.yayin >= ? AND g.islem_tarihi >= ?
           GROUP BY g.kod HAVING tutar >= ?""",
        ((date.today() - timedelta(days=90)).isoformat(), bas, gun_bas, GERI_ALIM_ESIK)).fetchall()
    sonuc = []
    for r in satirlar:
        x = dict(r)
        x["sirket"] = tr_baslik(kisa_unvan(x["unvan"])) if x["unvan"] else x["kod"]
        if not _fiyat_tutarli(x["kod"], x["ortalama"]):
            continue
        sonuc.append({"anahtar": f"geri:{x['kod']}:{x['son_tarih']}", "tur": "Geri alım", "onem": x["tutar"] / kur,
                      "metin": metin.geri_alim(x), "kaynak": x})
    return sonuc


def form4_islemleri(conn, bas_gun):
    satirlar = conn.execute(
        f"""SELECT person, MAX(job_title) AS unvan, ticker, MAX(COALESCE(company, asset_name)) AS sirket, action,
                   SUM(amount_max) AS tutar, SUM(share_count) AS adet, disclosed_date, MIN(source_id) AS kaynak_no
            FROM transactions
            WHERE chamber IS NULL AND {TEMIZ} AND {GECERLI_KOD} AND disclosed_date >= ? AND action IN ('buy', 'sell')
            GROUP BY person, ticker, action, disclosed_date""",
        (bas_gun,)).fetchall()
    sonuc = []
    for r in satirlar:
        x = dict(r)
        x["rol"] = _rol(x["unvan"])
        ust = x["rol"] in UST_YONETIM
        ortak = x["rol"] == "%10 üzeri ortak"
        esik = (FORM4_ALIM_ESIK if x["action"] == "buy" else FORM4_SATIS_ESIK)
        if ortak:
            esik = max(esik, ORTAK_ESIK)
        if not x["tutar"] or x["tutar"] < esik or (x["action"] == "sell" and not ust):
            continue
        x["kisi"] = tr_baslik(x["person"]) if x["person"].isupper() else x["person"]
        x["sirket"] = sirket_gorunen_ad(x["sirket"]) if x["sirket"] else x["ticker"]
        x["fiyat"] = x["tutar"] / x["adet"] if x.get("adet") else None
        # Üst yönetimin alımı daha çok haber: önem iki katı
        onem = x["tutar"] * (2 if ust and x["action"] == "buy" else 1)
        sonuc.append({"anahtar": f"form4:{x['person']}:{x['ticker']}:{x['action']}:{x['disclosed_date']}",
                      "tur": "ABD yönetici", "onem": onem, "metin": metin.form4(x), "kaynak": x})
    return sonuc


def kongre_islemleri(conn, bas_gun):
    satirlar = conn.execute(
        """SELECT person, MAX(party) AS parti, MAX(state) AS eyalet, MAX(chamber) AS meclis, ticker,
                  MAX(asset_name) AS sirket, action, SUM(amount_min) AS alt, SUM(amount_max) AS ust,
                  MIN(transaction_date) AS islem_tarihi, disclosed_date
           FROM transactions
           WHERE chamber IS NOT NULL AND disclosed_date >= ? AND action IN ('buy', 'sell')
           GROUP BY person, ticker, action, disclosed_date""",
        (bas_gun,)).fetchall()
    sonuc = []
    for r in satirlar:
        x = dict(r)
        unlu = x["person"] in UNLU_SIYASETCILER
        if not x["ust"] or (x["ust"] < KONGRE_ESIK and not unlu):
            continue
        x["kisi"] = x["person"]
        x["alt"] = x["alt"] or 0
        x["sirket"] = sirket_gorunen_ad(x["sirket"]) if x["sirket"] else x["ticker"]
        onem = (x["alt"] + x["ust"]) / 2 * (5 if unlu else 1)
        sonuc.append({"anahtar": f"kongre:{x['person']}:{x['ticker']}:{x['action']}:{x['disclosed_date']}",
                      "tur": "Kongre", "onem": onem, "metin": metin.kongre(x), "kaynak": x})
    return sonuc


def adaylar(conn, simdi=None, kur=45.0, saat=36):
    """Son 'saat' saatte bildirilen, eşikleri aşan işlemler; önem sırasıyla."""
    simdi = simdi or datetime.now()
    bas = (simdi - timedelta(hours=saat)).strftime("%Y-%m-%d %H:%M:%S")
    bas_gun = (simdi - timedelta(hours=saat)).date().isoformat()
    hepsi = (kap_islemleri(conn, bas, kur) + geri_alimlar(conn, bas, kur)
             + form4_islemleri(conn, bas_gun) + kongre_islemleri(conn, bas_gun))
    return sorted(hepsi, key=lambda a: -a["onem"])
