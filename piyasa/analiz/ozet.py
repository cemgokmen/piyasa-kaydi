"""
Günlük özet: Bir günün bildirimlerinden ve piyasa verilerinden kısa,
Türkçe, paylaşılabilir bir özet üretir. Metinler kural tabanlıdır;
her cümle doğrudan veritabanındaki kayıtlara dayanır.
"""

from contextlib import closing
from datetime import date, timedelta

from piyasa import fiyat
from piyasa.analiz import cakisma
from piyasa.bicim import kisa_aralik, kisa_tutar, sayi, sirket_kisa_ad, uzun_tarih, yuzde
from piyasa.emtia import sorgular as emtia_sorgulari
from piyasa.emtia.tanimlar import EMTIALAR
from piyasa.kurallar import GECERLI_KOD as GECERLI
from piyasa.kurallar import TEMIZ, YUKLU_ALIM_ALT_SINIR, parti_bilgisi
from piyasa.veritabani import get_connection

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def ozet_gunleri(conn, adet=60):
    """Bildirim olan son günler (en yeni önce)."""
    return [s[0] for s in conn.execute(
        f"""SELECT DISTINCT disclosed_date FROM transactions
           WHERE {TEMIZ} AND disclosed_date <= ? ORDER BY disclosed_date DESC LIMIT ?""",
        (date.today().isoformat(), adet),
    )]


def _madde(metin, adres=None, vurgu=None):
    return {"metin": metin, "adres": adres, "vurgu": vurgu}


def _yoneticiler(conn, gun):
    o = conn.execute(
        f"""SELECT SUM(action='buy') AS alim, SUM(action='sell') AS satim,
                  SUM(CASE WHEN action='buy' THEN amount_max END) AS alim_tutar,
                  SUM(CASE WHEN action='sell' THEN amount_max END) AS satim_tutar,
                  COUNT(DISTINCT person_slug) AS kisi
           FROM transactions WHERE chamber IS NULL AND {TEMIZ} AND disclosed_date = ?""",
        (gun,),
    ).fetchone()
    if not (o["alim"] or o["satim"]):
        return []

    maddeler = [_madde(
        f"{sayi(o['kisi'])} yönetici {sayi(o['alim'] or 0)} alım ({kisa_tutar(o['alim_tutar'])}) ve "
        f"{sayi(o['satim'] or 0)} satım ({kisa_tutar(o['satim_tutar'])}) bildirdi."
    )]

    for s in conn.execute(
        f"""SELECT ticker, MAX(asset_name) AS sirket, MAX(person) AS kisi, MAX(job_title) AS unvan,
                  SUM(amount_max) AS tutar
           FROM transactions WHERE chamber IS NULL AND action = 'buy' AND {TEMIZ} AND {GECERLI}
             AND disclosed_date = ?
           GROUP BY ticker, person_slug ORDER BY tutar DESC LIMIT 3""",
        (gun,),
    ):
        maddeler.append(_madde(
            f"En büyük alımlardan: {s['kisi']} ({s['unvan'] or 'yönetici'}), {sirket_kisa_ad(s['sirket']) or s['ticker']} "
            f"hissesinden {kisa_tutar(s['tutar'])} aldı.",
            f"/hisse/{s['ticker']}", s["ticker"],
        ))

    # Bu gün, son 30 günde ikinci bir yöneticinin de aldığı hisseler
    for s in conn.execute(
        f"""SELECT ticker, MAX(asset_name) AS sirket, COUNT(DISTINCT person_slug) AS kisi
           FROM transactions WHERE chamber IS NULL AND action = 'buy' AND {TEMIZ} AND {GECERLI}
             AND disclosed_date BETWEEN ? AND ?
             AND ticker IN (SELECT ticker FROM transactions WHERE chamber IS NULL AND action = 'buy'
                            AND disclosed_date = ?)
           GROUP BY ticker HAVING kisi >= 2 ORDER BY kisi DESC LIMIT 3""",
        ((date.fromisoformat(gun) - timedelta(days=30)).isoformat(), gun, gun),
    ):
        maddeler.append(_madde(
            f"Küme alımı: {sirket_kisa_ad(s['sirket']) or s['ticker']} hissesini son 30 günde {s['kisi']} farklı yönetici aldı.",
            f"/hisse/{s['ticker']}", s["ticker"],
        ))
    return maddeler


def _siyasetciler(conn, gun):
    satirlar = [dict(s) for s in conn.execute(
        """SELECT id, person, person_slug, party, ticker, asset_name, action, amount_min, amount_max,
                  transaction_date
           FROM transactions WHERE chamber IS NOT NULL AND disclosed_date = ?
           ORDER BY amount_max DESC""",
        (gun,),
    )]
    if not satirlar:
        return []

    kisiler = {s["person_slug"] for s in satirlar}
    alim = [s for s in satirlar if s["action"] == "buy"]
    maddeler = [_madde(
        f"{len(kisiler)} Kongre üyesi {len(satirlar)} hisse işlemi bildirdi "
        f"({len(alim)} alım, {len(satirlar) - len(alim)} satım)."
    )]

    for s in [s for s in alim if (s["amount_min"] or 0) >= YUKLU_ALIM_ALT_SINIR][:3]:
        p = parti_bilgisi(s["party"])
        parti = f" ({p['ad']})" if p else ""
        maddeler.append(_madde(
            f"Yüklü alım: {s['person']}{parti}, {sirket_kisa_ad(s['asset_name']) or s['ticker']} "
            f"hissesinden {kisa_aralik(s['amount_min'], s['amount_max'])} aldı "
            f"(işlem {uzun_tarih(s['transaction_date'])}).",
            f"/kisi/{s['person_slug']}", s["ticker"],
        ))

    cakisanlar = cakisma.cakisan_islemler()
    for s in [s for s in satirlar if s["id"] in cakisanlar][:3]:
        c = cakisanlar[s["id"]]
        maddeler.append(_madde(
            f"Olası çıkar çatışması: {s['person']} ({', '.join(c['komiteler'])}), "
            f"{c['sektor'].lower()} sektöründen {sirket_kisa_ad(s['asset_name']) or s['ticker']} hissesinde "
            f"{'alım' if s['action'] == 'buy' else 'satım'} yaptı.",
            f"/kisi/{s['person_slug']}", s["ticker"],
        ))
    return maddeler


def _emtialar():
    maddeler = []
    parcalar = []
    bilgiler = fiyat.toplu_fiyat_bilgisi([e["yahoo"] for e in EMTIALAR])
    for e in EMTIALAR:
        bilgi = bilgiler.get(e["yahoo"])
        if not bilgi:
            continue
        g1 = next((d["oran"] for d in bilgi["degisimler"] if d["anahtar"] == "1g"), None)
        parcalar.append(f"{e['ad']} {yuzde(g1)}")
    if parcalar:
        maddeler.append(_madde("Son kapanışta: " + ", ".join(parcalar) + ".", "/emtialar"))

    for e in EMTIALAR:
        if not e["cot"] or e.get("cot_notu"):
            continue
        c = emtia_sorgulari.cot(e["slug"], hafta=53)
        if c and c["konum"] is not None and (c["konum"] >= 90 or c["konum"] <= 10):
            yon = "en iyimser" if c["konum"] >= 90 else "en kötümser"
            maddeler.append(_madde(
                f"{e['ad']}: büyük fonlar son bir yılın {yon} konumuna yakın ({c['konum']}/100, "
                f"{uzun_tarih(c['tarih'])} raporu).",
                f"/emtia/{e['slug']}#arz-talep",
            ))
    return maddeler


def gunluk_ozet(gun=None):
    with closing(get_connection()) as conn:
        gunler = ozet_gunleri(conn)
        if not gunler:
            return None
        gun = gun if gun in gunler else gunler[0]
        i = gunler.index(gun)
        bolumler = [
            ("Siyasetçiler", _siyasetciler(conn, gun)),
            ("Şirket yöneticileri", _yoneticiler(conn, gun)),
        ]

    # Emtia fiyatları canlıdır; yalnızca en güncel günün özetinde gösterilir
    if i == 0:
        bolumler.append(("Emtialar", _emtialar()))
    bolumler = [(b, m) for b, m in bolumler if m]

    d = date.fromisoformat(gun)
    baslik = f"{uzun_tarih(gun)} {GUNLER[d.weekday()]}"
    # Paylaşım için düz metin: sitede gösterilmez, istendiğinde dışarıya verilir
    duz_metin = "\n".join(
        [f"Piyasa Kaydı · {baslik} özeti", ""]
        + [satir for b, m in bolumler for satir in [b.upper(), *[f"• {x['metin']}" for x in m], ""]]
        + ["Kaynak: resmi bildirimler (SEC, ABD Kongresi). Yatırım tavsiyesi değildir."]
    )
    return {
        "gun": gun,
        "baslik": baslik,
        "bolumler": bolumler,
        "duz_metin": duz_metin,
        "onceki": gunler[i + 1] if i + 1 < len(gunler) else None,
        "sonraki": gunler[i - 1] if i > 0 else None,
        "gunler": gunler[:30],
    }
