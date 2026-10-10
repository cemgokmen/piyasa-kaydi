"""
Günlük özet: Bir günün bildirimlerinden ve piyasa verilerinden kısa,
Türkçe, paylaşılabilir bir özet üretir. Metinler kural tabanlıdır;
her cümle doğrudan veritabanındaki kayıtlara dayanır.
"""

from contextlib import closing
from datetime import UTC, date, datetime, timedelta

from piyasa import fiyat
from piyasa.analiz import cakisma
from piyasa.bicim import (
    kisa_aralik,
    kisa_tutar,
    para,
    sayi,
    sirket_gorunen_ad,
    tr_baslik,
    tr_cumle,
    tr_kucuk,
    unvan,
    uzun_tarih,
    yuzde,
)
from piyasa.bist.sorgular import kisa_unvan as _kisa_unvan
from piyasa.emtia import sorgular as emtia_sorgulari
from piyasa.emtia.tanimlar import EMTIALAR
from piyasa.kripto import piyasa as kripto_piyasa
from piyasa.kripto.tanimlar import KRIPTO, KRIPTOLAR
from piyasa.kurallar import GECERLI_KOD as GECERLI
from piyasa.kurallar import TEMIZ, YUKLU_ALIM_ALT_SINIR, parti_bilgisi
from piyasa.veritabani import get_connection

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def _madde(baslik, metin, adres=None, vurgu=None, vurgu_adres=None):
    """vurgu: maddenin başındaki hisse kodu; vurgu_adres verilmezse ABD hisse sayfasına gider."""
    return {"baslik": baslik, "metin": metin, "adres": adres, "vurgu": vurgu, "vurgu_adres": vurgu_adres}


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
           FROM transactions WHERE chamber IS NULL AND {TEMIZ} AND disclosed_date >= ?""",
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
             AND disclosed_date >= ?
           GROUP BY ticker, person_slug ORDER BY tutar DESC LIMIT 4""",
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
             AND disclosed_date >= ?
             AND ticker IN (SELECT ticker FROM transactions WHERE chamber IS NULL AND action = 'buy'
                            AND disclosed_date >= ?)
           GROUP BY ticker HAVING kisi >= 2 ORDER BY kisi DESC LIMIT 2""",
        ((date.fromisoformat(gun) - timedelta(days=30)).isoformat(), gun),
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
           FROM transactions WHERE chamber IS NOT NULL AND disclosed_date >= ?
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


def sirket_kisa(unvan_):
    return _kisa_unvan(tr_baslik(unvan_)) if unvan_ else None


def _bist(conn, gun, bas_zaman):
    """Son 24 saatte KAP'a bildirilen yönetici ve ortak işlemleri (fonlar hariç) ile geri alımlar."""
    islemler = [dict(r) for r in conn.execute(
        """SELECT p.kod, p.kisi, p.gorev, p.islem, p.nominal, p.fiyat, p.tutar, p.oran_sonra, s.unvan
           FROM kap_pay_islem p JOIN kap_bildirim b USING (indeks) LEFT JOIN bist_sirket s ON s.kod = p.kod
           WHERE b.yayin >= ? AND p.kisi_turu != 'fon' AND p.islem IS NOT NULL""", (bas_zaman,))]
    geri = conn.execute(
        """SELECT COUNT(DISTINCT kod) AS sirket, SUM(nominal * fiyat) AS tutar FROM kap_geri_alim
           WHERE islem_tarihi >= ?""", (gun,)).fetchone()
    if not islemler and not (geri and geri["sirket"]):
        return None
    alim = [i for i in islemler if i["islem"] == "buy"]
    parcalar = []
    if islemler:
        parcalar.append(f"KAP'a {len(islemler)} yönetici ve ortak işlemi bildirildi ({len(alim)} alım, "
                        f"{len(islemler) - len(alim)} satım)")
    if geri and geri["sirket"]:
        parcalar.append(f"{geri['sirket']} şirket toplam {para(geri['tutar'], 'TRY')} tutarında kendi payını geri aldı")
    maddeler = []
    for i in sorted((i for i in islemler if i["tutar"]), key=lambda x: -x["tutar"])[:5]:
        ad = sirket_kisa(i["unvan"]) or i["kod"]
        rol = tr_cumle(i["gorev"]) if i["gorev"] else None
        kisi = tr_baslik(i["kisi"])
        maddeler.append(_madde(
            f"{ad} hissesinde {para(i['tutar'], 'TRY')} değerinde {'alım' if i['islem'] == 'buy' else 'satış'}",
            f"{kisi}{' (' + rol + ')' if rol else ''}, {ad} payından {sayi(round(i['nominal']))} adetlik "
            f"{'alım' if i['islem'] == 'buy' else 'satış'} bildirdi"
            + (f"; işlemden sonra şirketteki payı %{str(round(i['oran_sonra'], 2)).replace('.', ',')}." if i["oran_sonra"] is not None else "."),
            f"/bist/{i['kod']}", i["kod"], f"/bist/{i['kod']}",
        ))
    return _bolum("Borsa İstanbul", "; ".join(parcalar) + ".", maddeler)


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
           FROM kripto_islem WHERE disclosed_date >= ? ORDER BY amount_max DESC LIMIT 3""", (gun,),
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


# Haber konuları: özet sayfasındaki sıra ve başlıklar (bkz. toplama/haber_akisi.py)
HABER_KONULARI = [("faiz", "Faiz ve enflasyon"), ("doviz", "Döviz ve altın"), ("borsa", "Borsa"),
                  ("enerji", "Enerji"), ("kripto", "Kripto"), ("dunya", "Dünya ekonomisi"), ("ekonomi", "Ekonomi")]
KONU_BASINA = 5
HABER_ESIK = 12          # önem puanı: fiyat sayfaları ve önemsiz haberler özete girmez


def _yerel_saat(utc_iso):
    return datetime.fromisoformat(utc_iso).astimezone().strftime("%H:%M")


def _haberler(conn, bas_utc):
    """Son 24 saatin haberleri; aynı olaydan tek haber, konulara göre gruplu, önem sırasıyla."""
    try:
        satirlar = [dict(r) for r in conn.execute(
            """SELECT adres, kaynak, baslik, ozet, konu, puan, kaynak_sayisi, yayin FROM haber
               WHERE yayin >= ? AND adres = kume AND puan >= ? ORDER BY puan DESC""", (bas_utc, HABER_ESIK))]
    except Exception:
        return None, []
    for h in satirlar:
        h["saat"] = _yerel_saat(h["yayin"])
    manset = satirlar[0] if satirlar else None
    gruplar = []
    for konu, ad in HABER_KONULARI:
        liste = [h for h in satirlar[1:] if h["konu"] == konu][:KONU_BASINA]
        if liste:
            gruplar.append({"ad": ad, "haberler": liste})
    return manset, gruplar


def _piyasalar():
    """Piyasa göstergeleri ve tek cümlelik sade özet."""
    try:
        from piyasa.emtia import serit
        gostergeler = serit.son_hali() or [serit.bicimli(g) for g in serit.serit()]
    except Exception:
        return None
    if not gostergeler:
        return None
    g = {x["kod"]: x for x in gostergeler}
    parcalar = []
    bist = g.get("XU100.IS")
    if bist and bist["degisim"] is not None:
        yon = "yükselişte" if bist["degisim"] > 0 else "düşüşte" if bist["degisim"] < 0 else "yatay"
        parcalar.append(f"Borsa İstanbul'da BIST 100 endeksi {yuzde(bist['degisim'])} ile {yon}")
    if g.get("TRY=X"):
        parcalar.append(f"dolar {g['TRY=X']['deger_metni'].replace(' ₺', ' TL')}")
    if g.get("GRAM"):
        parcalar.append(f"gram altın {g['GRAM']['deger_metni'].replace(' ₺', ' TL')}")
    if g.get("BTC-USD"):
        parcalar.append(f"Bitcoin {g['BTC-USD']['deger_metni'].replace('$', '')} dolar")
    cumle = (", ".join(parcalar) + ".") if parcalar else ""
    if cumle:
        cumle = cumle[0].upper() + cumle[1:]
    if date.today().weekday() >= 5:
        cumle += " Borsalar hafta sonu kapalı; hisse ve döviz değerleri son kapanıştır."
    return {"gostergeler": gostergeler, "cumle": cumle}


def gunluk_ozet():
    """
    Bugünün özeti: son 24 saatin haberleri, bildirimleri ve piyasa durumu. Hiçbir içerik bir
    günden eski değildir. Sabah 07:00'deki tam güncelleme gecenin ABD bildirimlerini getirir;
    haberler gün içinde 30 dakikada bir, KAP bildirimleri 15 dakikada bir eklenir.
    """
    simdi = datetime.now()
    bas = simdi - timedelta(hours=24)
    bas_gun = bas.date().isoformat()
    bas_zaman = bas.strftime("%Y-%m-%d %H:%M:%S")
    bas_utc = bas.astimezone(UTC).isoformat()
    with closing(get_connection()) as conn:
        manset_haber, haber_gruplari = _haberler(conn, bas_utc)
        siyaset = _siyasetciler(conn, bas_gun)
        yonetici = _yoneticiler(conn, bas_gun)
        kripto = _kripto(conn, bas_gun, canli=True)
        bist = _bist(conn, bas_gun, bas_zaman)

    if manset_haber:
        manset = manset_haber["baslik"]
        spot = manset_haber["ozet"] or ""
    else:
        manset, spot = _manset(siyaset, yonetici)
    if yonetici:
        yonetici["ad"] = "ABD'de şirket yöneticileri"
    if siyaset:
        siyaset["ad"] = "ABD'de siyasetçiler"
    bolumler = [b for b in (bist, yonetici, siyaset, _emtialar(), kripto) if b]

    baslik = f"{uzun_tarih(simdi.date().isoformat())} {GUNLER[simdi.weekday()]}"
    return {
        "gun": simdi.date().isoformat(),
        "baslik": baslik,
        "guncelleme": simdi.strftime("%H:%M"),
        "manset": manset,
        "spot": spot,
        "manset_haber": manset_haber,
        "piyasa": _piyasalar(),
        "haber_gruplari": haber_gruplari,
        "bolumler": bolumler,
    }
