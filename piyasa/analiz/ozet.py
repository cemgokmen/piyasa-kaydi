"""
Günlük özet: Bir günün bildirimlerinden ve piyasa verilerinden kısa,
Türkçe, paylaşılabilir bir özet üretir. Metinler kural tabanlıdır;
her cümle doğrudan veritabanındaki kayıtlara dayanır.
"""

from contextlib import closing
from datetime import date, timedelta

from piyasa import fiyat
from piyasa.analiz import cakisma
from piyasa.bicim import kisa_aralik, kisa_tutar, sayi, sirket_gorunen_ad, tr_kucuk, unvan, uzun_tarih, yuzde
from piyasa.emtia import sorgular as emtia_sorgulari
from piyasa.emtia.tanimlar import EMTIALAR
from piyasa.kripto import piyasa as kripto_piyasa
from piyasa.kripto.tanimlar import KRIPTO, KRIPTOLAR
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


def _madde(baslik, metin, adres=None, vurgu=None):
    return {"baslik": baslik, "metin": metin, "adres": adres, "vurgu": vurgu}


def _bolum(ad, giris, maddeler):
    return {"ad": ad, "giris": giris, "maddeler": maddeler}


def _rol(ham_unvan):
    """Haber cümlesinde kişinin önüne gelecek sıfat ('CEO', 'Yönetim kurulu üyesi'...)."""
    u = unvan(ham_unvan) if ham_unvan else ""
    if not u or u == "Bildirim yükümlüsü":
        return ""
    if u.startswith("%10"):
        return "Şirketin büyük ortaklarından"
    return u[0].upper() + u[1:]


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
        return None

    alim, satim = o["alim"] or 0, o["satim"] or 0
    giris = (f"{sayi(o['kisi'])} şirket yöneticisi ve büyük ortak, toplam {kisa_tutar(o['alim_tutar'])} "
             f"değerinde {sayi(alim)} alım ve {kisa_tutar(o['satim_tutar'])} değerinde {sayi(satim)} satım bildirdi.")
    if satim > alim * 3:
        giris += " Satışların ağır basması olağandır: yöneticiler maaş olarak aldıkları hisseleri düzenli olarak nakde çevirir."

    maddeler = []
    for s in conn.execute(
        f"""SELECT ticker, MAX(asset_name) AS sirket, MAX(person) AS kisi, MAX(job_title) AS unvan,
                  SUM(amount_max) AS tutar
           FROM transactions WHERE chamber IS NULL AND action = 'buy' AND {TEMIZ} AND {GECERLI}
             AND disclosed_date = ?
           GROUP BY ticker, person_slug ORDER BY tutar DESC LIMIT 3""",
        (gun,),
    ):
        sirket = sirket_gorunen_ad(s["sirket"]) or s["ticker"]
        rol = _rol(s["unvan"])
        maddeler.append(_madde(
            f"{sirket} hissesine {kisa_tutar(s['tutar'])} değerinde içeriden alım",
            f"{rol + ' ' if rol else ''}{s['kisi']}, {sirket} hissesinden {kisa_tutar(s['tutar'])} "
            f"değerinde alım yaptığını bildirdi.",
            f"/hisse/{s['ticker']}", s["ticker"],
        ))

    # Bu gün, son 30 günde ikinci bir yöneticinin de aldığı hisseler
    for s in conn.execute(
        f"""SELECT ticker, MAX(asset_name) AS sirket, COUNT(DISTINCT person_slug) AS kisi
           FROM transactions WHERE chamber IS NULL AND action = 'buy' AND {TEMIZ} AND {GECERLI}
             AND disclosed_date BETWEEN ? AND ?
             AND ticker IN (SELECT ticker FROM transactions WHERE chamber IS NULL AND action = 'buy'
                            AND disclosed_date = ?)
           GROUP BY ticker HAVING kisi >= 2 ORDER BY kisi DESC LIMIT 2""",
        ((date.fromisoformat(gun) - timedelta(days=30)).isoformat(), gun, gun),
    ):
        sirket = sirket_gorunen_ad(s["sirket"]) or s["ticker"]
        maddeler.append(_madde(
            f"{sirket} hissesinde toplu yönetici alımı",
            f"Son 30 günde {s['kisi']} farklı yönetici {sirket} hissesi aldı; aynı dönemde birden çok "
            f"yöneticinin alması dikkat çeken bir işarettir.",
            f"/hisse/{s['ticker']}", s["ticker"],
        ))
    return _bolum("Şirket yöneticileri", giris, maddeler)


def _siyasetciler(conn, gun):
    satirlar = [dict(s) for s in conn.execute(
        """SELECT id, person, person_slug, party, ticker, asset_name, action, amount_min, amount_max,
                  transaction_date
           FROM transactions WHERE chamber IS NOT NULL AND disclosed_date = ?
           ORDER BY amount_max DESC""",
        (gun,),
    )]
    if not satirlar:
        return None

    kisiler = {s["person_slug"] for s in satirlar}
    alim = [s for s in satirlar if s["action"] == "buy"]
    satim = len(satirlar) - len(alim)
    dagilim = ("hepsi alım" if not satim else "hepsi satım" if not alim
               else f"{len(alim)} alım, {satim} satım")
    uye = "Bir Kongre üyesi" if len(kisiler) == 1 else f"{len(kisiler)} Kongre üyesi"
    giris = f"{uye} {len(satirlar)} hisse işlemi bildirdi ({dagilim})."

    maddeler = []
    for s in [s for s in alim if (s["amount_min"] or 0) >= YUKLU_ALIM_ALT_SINIR][:3]:
        p = parti_bilgisi(s["party"])
        sirket = sirket_gorunen_ad(s["asset_name"]) or s["ticker"]
        maddeler.append(_madde(
            f"{s['person']} {sirket} hissesi aldı",
            f"{p['ad'] + ' ' if p else ''}{s['person']}, {uzun_tarih(s['transaction_date'])} tarihinde "
            f"{sirket} hissesinden {kisa_aralik(s['amount_min'], s['amount_max'])} arasında alım yaptı.",
            f"/kisi/{s['person_slug']}", s["ticker"],
        ))

    cakisanlar = cakisma.cakisan_islemler()
    for s in [s for s in satirlar if s["id"] in cakisanlar][:2]:
        c = cakisanlar[s["id"]]
        sirket = sirket_gorunen_ad(s["asset_name"]) or s["ticker"]
        maddeler.append(_madde(
            f"{s['person']}, komitesinin denetlediği sektörde hisse {'aldı' if s['action'] == 'buy' else 'sattı'}",
            f"{s['person']}, üyesi olduğu {', '.join(k.removesuffix(' Komitesi') for k in c['komiteler'])} komitesinin denetlediği "
            f"{c['sektor'].lower()} sektöründen {sirket} hissesinde {'alım' if s['action'] == 'buy' else 'satım'} yaptı.",
            f"/kisi/{s['person_slug']}", s["ticker"],
        ))
    return _bolum("Siyasetçiler", giris, maddeler)


def _emtialar():
    bilgiler = fiyat.toplu_fiyat_bilgisi([e["yahoo"] for e in EMTIALAR])
    hareket = []
    for e in EMTIALAR:
        bilgi = bilgiler.get(e["yahoo"])
        g1 = bilgi and next((d["oran"] for d in bilgi["degisimler"] if d["anahtar"] == "1g"), None)
        if g1 is not None:
            hareket.append((e, g1))
    if not hareket:
        return None

    hareket.sort(key=lambda x: x[1])
    yukselen = [h for h in hareket if h[1] > 0]
    if len(yukselen) == len(hareket):
        genel = "Emtialar günü yükselişle kapattı"
    elif not yukselen:
        genel = "Emtialar günü düşüşle kapattı"
    else:
        genel = "Emtialarda karışık bir gün"
    (en_dusuk, d), (en_yuksek, y) = hareket[0], hareket[-1]
    giris = (f"{genel}. En çok {'yükselen' if y > 0 else 'az düşen'} {_emtia_adi(en_yuksek)} ({yuzde(y)}), "
             f"en çok {'düşen' if d < 0 else 'az yükselen'} {_emtia_adi(en_dusuk)} ({yuzde(d)}) oldu.")

    maddeler = []
    for e in EMTIALAR:
        if not e["cot"] or e.get("cot_notu"):
            continue
        c = emtia_sorgulari.cot(e["slug"], hafta=53)
        if c and c["konum"] is not None and (c["konum"] >= 90 or c["konum"] <= 10):
            iyimser = c["konum"] >= 90
            maddeler.append(_madde(
                f"Büyük fonlar {_emtia_adi(e)} için {'bir yılın en iyimser' if iyimser else 'bir yılın en kötümser'} noktasında",
                f"Spekülatif fonların {_emtia_adi(e)} vadelilerindeki konumu son bir yılın "
                f"{'en yükseğine' if iyimser else 'en düşüğüne'} yakın ({c['konum']}/100, {uzun_tarih(c['tarih'])} raporu).",
                f"/emtia/{e['slug']}#arz-talep",
            ))
    return _bolum("Emtialar", giris, maddeler)


def _kripto(conn, gun, canli):
    """Kripto piyasası (yalnızca en yeni özette, canlı) ve o gün bildirilen Kongre kripto işlemleri."""
    giris, maddeler = None, []
    if canli:
        bilgiler = kripto_piyasa.toplu_bilgi()
        btc, eth = bilgiler.get("bitcoin"), bilgiler.get("ethereum")
        if btc and btc.get("degisim_24s") is not None:
            giris = f"Bitcoin son 24 saatte {yuzde(btc['degisim_24s'])} değişimle {sayi(round(btc['fiyat']))} dolar"
            if eth and eth.get("degisim_24s") is not None:
                giris += f", Ethereum {yuzde(eth['degisim_24s'])} değişimle {sayi(round(eth['fiyat']))} dolar"
            giris += "."
            # Sabit paralar hareket etmez; onlar dışındaki en sert yükselen ve düşen
            hareket = sorted(((k, bilgiler[k["slug"]]["degisim_24s"]) for k in KRIPTOLAR
                              if k["tur"] != "Sabit para" and bilgiler.get(k["slug"])
                              and bilgiler[k["slug"]].get("degisim_24s") is not None), key=lambda x: x[1])
            if len(hareket) > 2:
                (dk, d), (yk, y) = hareket[0], hareket[-1]
                if y > 0 and d < 0:
                    giris += (f" Takip ettiğimiz kriptolar arasında en çok yükselen {yk['ad']} ({yuzde(y)}), "
                              f"en çok düşen {dk['ad']} ({yuzde(d)}) oldu.")
                elif y <= 0:
                    giris += (f" Takip ettiğimiz kriptoların hepsi geriledi; en sert düşüş {dk['ad']} ({yuzde(d)}), "
                              f"en hafif düşüş {yk['ad']} ({yuzde(y)}).")
                else:
                    giris += (f" Takip ettiğimiz kriptoların hepsi yükseldi; en çok {yk['ad']} ({yuzde(y)}), "
                              f"en az {dk['ad']} ({yuzde(d)}).")
    for s in conn.execute(
        """SELECT person, person_slug, party, coin, varlik, ticker, action, amount_min, amount_max, transaction_date
           FROM kripto_islem WHERE disclosed_date = ? ORDER BY amount_max DESC LIMIT 3""", (gun,),
    ):
        k = KRIPTO.get(s["coin"])
        p = parti_bilgisi(s["party"])
        ne = f"{s['ticker']} ({k['ad']} fonu)" if s["ticker"] else k["ad"]
        maddeler.append(_madde(
            f"{s['person']} {k['ad']} {'aldı' if s['action'] == 'buy' else 'sattı'}",
            f"{p['ad'] + ' ' if p else ''}{s['person']}, {uzun_tarih(s['transaction_date'])} tarihinde "
            f"{kisa_aralik(s['amount_min'], s['amount_max'])} arasında {ne} {'alımı' if s['action'] == 'buy' else 'satışı'} bildirdi.",
            f"/kripto/{s['coin']}",
        ))
    if not giris and not maddeler:
        return None
    return _bolum("Kripto paralar", giris or "Kongre üyeleri kripto işlemi bildirdi.", maddeler)


def _emtia_adi(e):
    return e["ad"] if e["ad"].startswith("Brent") else tr_kucuk(e["ad"])


def _manset(siyaset, yonetici):
    """
    Günün başlığı ve giriş cümlesi: en dikkat çekici haber öne çıkar ve
    bölümünden alınır ki aşağıda tekrar etmesin.
    """
    for b in (siyaset, yonetici):
        if b and b["maddeler"]:
            ilk = b["maddeler"].pop(0)
            return ilk["baslik"], ilk["metin"]
    return None, None


def gunluk_ozet(gun=None):
    with closing(get_connection()) as conn:
        gunler = ozet_gunleri(conn)
        if not gunler:
            return None
        gun = gun if gun in gunler else gunler[0]
        i = gunler.index(gun)
        siyaset = _siyasetciler(conn, gun)
        yonetici = _yoneticiler(conn, gun)
        kripto = _kripto(conn, gun, canli=i == 0)

    manset, spot = _manset(siyaset, yonetici)
    # Emtia fiyatları canlıdır; yalnızca en güncel günün özetinde gösterilir
    bolumler = [b for b in (siyaset, yonetici, _emtialar() if i == 0 else None, kripto) if b]

    d = date.fromisoformat(gun)
    baslik = f"{uzun_tarih(gun)} {GUNLER[d.weekday()]}"
    # Paylaşım için düz metin: sitede gösterilmez, istendiğinde dışarıya verilir
    duz_metin = "\n".join(
        [f"Piyasa Kaydı · {baslik}", ""] + ([manset, spot, ""] if manset else [])
        + [satir for b in bolumler for satir in [b["ad"].upper(), *[f"• {x['metin']}" for x in b["maddeler"]], ""]]
        + ["Kaynak: resmi bildirimler (SEC, ABD Kongresi). Yatırım tavsiyesi değildir."]
    )
    return {
        "gun": gun,
        "baslik": baslik,
        "manset": manset,
        "spot": spot,
        "bolumler": bolumler,
        "duz_metin": duz_metin,
        "onceki": gunler[i + 1] if i + 1 < len(gunler) else None,
        "sonraki": gunler[i - 1] if i > 0 else None,
        "gunler": gunler[:30],
        "en_yeni": i == 0,
    }
