"""
Sitenin kendi verisiyle paylaşım kartları:

  islem_karti     tek bir içeriden işlem: hissenin son 6 aylık grafiği üzerinde işlem günü, tutar,
                  adet, fiyat, işlem sonrası pay ve bizim verimizden bağlam (son 90 günde kaç içeriden alım,
                  işlemden bu yana hissenin seyri)
  liste_kartlari  haftanın sıralamaları: KAP'ta en çok içeriden alım, ABD'de yöneticilerin en çok aldığı,
                  en büyük geri alımlar, siyasetçilerin en çok aldığı hisseler
  hareket_karti   Borsa İstanbul'da son işlem gününün en çok yükselen ve düşen hisseleri

Her kart: {anahtar, tur, grup, onem, metin (X gönderisi), kart (SVG şablonunun alanları)}.
"""

from datetime import date, timedelta

from piyasa.bicim import AYLAR, ek, sirket_gorunen_ad, tr_baslik
from piyasa.bist.sorgular import kisa_unvan
from piyasa.kurallar import GECERLI_KOD, TEMIZ
from piyasa.paylasim import metin

SITE = metin.SITE
YESIL, KIRMIZI, MAVI, MOR = "#22C55E", "#EF4444", "#3B82F6", "#8B5CF6"


def _kisa_gun(iso):
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {AYLAR[d.month - 1]}"


def _yuzde(oran, isaretli=True):
    if oran is None:
        return "—"
    isaret = ("+" if oran > 0 else "−" if oran < 0 else "") if isaretli else ""
    return f"{isaret}%{abs(oran) * 100:.1f}".replace(".", ",")


# ---------------------------------------------------------------------------
# Fiyat geçmişi ve grafik
# ---------------------------------------------------------------------------

def fiyat_serisi(kod, bist, gun=182):
    """[(tarih, kapanış)] son 'gun' gün; bulunamazsa []."""
    try:
        if bist:
            from piyasa.bist import piyasa
            piyasa._dosyadan_oku()
            s = piyasa._durum["seri"].get(kod)
            seri = list(zip(s["t"], s["c"], strict=True)) if s else []
        else:
            from piyasa import fiyat
            b = fiyat.fiyat_bilgisi(kod, ham=True)
            seri = [(x[0], x[1]) for x in (b or {}).get("seriler", {}).get("1y", [])]
    except Exception:
        return []
    sinir = (date.today() - timedelta(days=gun)).isoformat()
    seri = [(t, c) for t, c in seri if t >= sinir and c]
    if bist:
        # Borsa İstanbul'da günlük hareket ±%10 ile sınırlı: bunu aşan sıçrama düzeltilmemiş bedelsiz ya da
        # bölünmedir; grafik ve değişim o günden sonrasıyla hesaplanır (yanlış "%76 düştü" yazılmasın)
        from piyasa.bist.hareket import GUNLUK_SINIR
        for i in range(len(seri) - 1, 0, -1):
            if abs(seri[i][1] / seri[i - 1][1] - 1) > GUNLUK_SINIR:
                return seri[i:]
    return seri


def grafik(seri, x, y, en, boy, isaret_tarihi=None):
    """SVG çizgi ve alan yolu; işlem gününün noktası; son fiyat ve işlemden bu yana değişim."""
    if len(seri) < 5:
        return None
    degerler = [c for _, c in seri]
    az, cok = min(degerler), max(degerler)
    aralik = (cok - az) or 1
    adim = en / (len(seri) - 1)

    def nokta(i, c):
        return x + i * adim, y + (1 - (c - az) / aralik) * boy

    noktalar = [nokta(i, c) for i, (_, c) in enumerate(seri)]
    cizgi = "M" + " L".join(f"{a:.1f},{b:.1f}" for a, b in noktalar)
    alan = cizgi + f" L{noktalar[-1][0]:.1f},{y + boy:.1f} L{x:.1f},{y + boy:.1f} Z"
    sonuc = {"cizgi": cizgi, "alan": alan, "son": degerler[-1], "en_yuksek": cok, "en_dusuk": az,
             "bas_tarih": _kisa_gun(seri[0][0]), "son_tarih": _kisa_gun(seri[-1][0]), "isaret": None}
    if isaret_tarihi:
        i = next((i for i, (t, _) in enumerate(seri) if t >= isaret_tarihi[:10]), None)
        # İşlem son günlerdeyse "işlemden bu yana" anlamsızdır: onun yerine 6 aylık değişim
        if i is not None and i >= len(seri) - 3:
            sonuc["isaret"] = {"x": round(noktalar[i][0], 1), "y": round(noktalar[i][1], 1),
                               "tarih": _kisa_gun(seri[i][0]), "sag": True}
            sonuc["degisim"] = degerler[-1] / degerler[0] - 1 if degerler[0] else None
            ay = round((date.fromisoformat(seri[-1][0][:10]) - date.fromisoformat(seri[0][0][:10])).days / 30)
            sonuc["degisim_etiket"] = f"Son {ay} ayda" if ay >= 1 else "Son günlerde"
            return sonuc
        if i is not None:
            px, py = noktalar[i]
            sonuc["isaret"] = {"x": round(px, 1), "y": round(py, 1), "tarih": _kisa_gun(seri[i][0]),
                               "sag": px > x + en * 0.62}
            sonuc["degisim"] = degerler[-1] / seri[i][1] - 1 if seri[i][1] else None
            sonuc["degisim_etiket"] = "İşlemden bu yana"
    return sonuc


# ---------------------------------------------------------------------------
# Tek işlem kartı
# ---------------------------------------------------------------------------

def rol_iyelik(rol):
    """'Başkan' → 'başkanı', 'CEO' → "CEO'su", 'Yönetim kurulu üyesi' → aynen (zaten iyelikli)."""
    if not rol:
        return ""
    if rol.isupper():
        return ek(rol, "si")
    kucuk = rol[0].lower() + rol[1:]
    if kucuk.endswith(("ı", "i", "u", "ü")):
        return kucuk
    return ek(kucuk, "si").replace("'", "")


def _soyad(ad):
    return (ad or "").split()[-1] if ad else ad


def _kap_baglam(conn, kod):
    r = conn.execute(
        """SELECT COUNT(*), COUNT(DISTINCT p.kisi), SUM(p.tutar) FROM kap_pay_islem p JOIN kap_bildirim b USING (indeks)
           WHERE p.kod = ? AND p.islem = 'buy' AND p.kisi_turu != 'fon' AND b.yayin >= ?""",
        (kod, (date.today() - timedelta(days=90)).isoformat())).fetchone()
    return {"adet": r[0] or 0, "kisi": r[1] or 0, "tutar": r[2] or 0}


def _abd_baglam(conn, ticker):
    r = conn.execute(
        f"""SELECT COUNT(DISTINCT person_slug), SUM(amount_max) FROM transactions
            WHERE chamber IS NULL AND {TEMIZ} AND ticker = ? AND action = 'buy' AND amount_max > 0 AND disclosed_date >= ?""",
        (ticker, (date.today() - timedelta(days=90)).isoformat())).fetchone()
    return {"kisi": r[0] or 0, "tutar": r[1] or 0}


def islem_karti(conn, aday):
    """secim.py adayını (KAP, geri alım, Form 4, Kongre) grafikli ve bağlamlı veri kartına çevirir."""
    x, tur = aday["kaynak"], aday["tur"]
    bist = tur in ("KAP içeriden", "Geri alım")
    kod = x["kod"] if bist else x["ticker"]
    alim = (x.get("islem") or x.get("action") or "buy") == "buy"
    tarih = x.get("islem_tarihi") or x.get("son_tarih") or x.get("disclosed_date")
    seri = fiyat_serisi(kod, bist)
    g = grafik(seri, 640, 214, 470, 210, tarih)
    faaliyet = aday["kart"].get("faaliyet")

    if tur == "KAP içeriden":
        sirket_mi = x["kisi_turu"] == "sirket" or bool(metin.SIRKET_ADI.search(x["kisi"] or ""))
        kisi = x["kisi_kisa"] if sirket_mi else x["kisi"]
        rol = "Ortak" if sirket_mi or not x.get("gorev") else x["gorev"]
        baglam = _kap_baglam(conn, kod)
        etiket = f"KAP · İÇERİDEN {'ALIM' if alim else 'SATIŞ'}"
        tutar_metni = metin.tutar(x["tutar"])
        kutular = [("Adet", metin.adet(x["nominal"]) if x.get("nominal") else "—"),
                   ("Ort. fiyat", metin.fiyat_metni(x["fiyat"], "TL") if x.get("fiyat") else "—"),
                   ("Sonraki pay", f"%{metin.ondalik(x['oran_sonra'])}" if x.get("oran_sonra") is not None else "—")]
        adres, kaynak = f"{SITE}/bist/{kod}", "KAP"
        ilk = (f"{x['sirket']} (#{kod}) {rol_iyelik(rol) if rol != 'Ortak' else 'ortağı'} {kisi}, "
               f"{ek(metin.gun(tarih), 'de')} şirket hisselerinden {ek(tutar_metni, 'lik')} {'alım' if alim else 'satış'} yaptı.")
        ayrinti = ""
        if x.get("nominal") and x.get("fiyat"):
            ayrinti = (f"{_soyad(kisi) if not sirket_mi else kisi}, {metin.adet(x['nominal'])} adet payı ortalama "
                       f"{metin.fiyat_metni(x['fiyat'], 'TL')} fiyattan {'aldı' if alim else 'sattı'}")
            if x.get("oran_sonra") is not None:
                ayrinti += f"; şirketteki payı %{metin.ondalik(x['oran_sonra'])} oldu"
            ayrinti += "."
        baglam_metni = (f"Son 90 günde {x['sirket']} hisselerinde {baglam['adet']} içeriden alım bildirildi."
                        if baglam["adet"] > 1 else "")
    elif tur == "Geri alım":
        etiket, rol, kisi = "KAP · PAY GERİ ALIMI", "Şirketin kendisi", x["sirket"]
        tutar_metni = metin.tutar(x["tutar"])
        kutular = [("Ort. fiyat", metin.fiyat_metni(x["ortalama"], "TL") if x.get("ortalama") else "—"),
                   ("Son 90 günde", metin.tutar(x["toplam_90"]) if x.get("toplam_90") else "—")]
        adres, kaynak = f"{SITE}/bist/{kod}", "KAP"
        ilk = f"{x['sirket']} (#{kod}), {ek(metin.gun(tarih), 'de')} borsadan {ek(tutar_metni, 'lik')} kendi payını geri aldı."
        ayrinti = f"Şirketin son 90 günde geri aldığı payların toplamı {metin.tutar(x['toplam_90'])}." if x.get("toplam_90") else ""
        baglam_metni = ""
    elif tur == "ABD yönetici":
        rol = x["rol"] if x["rol"] not in ("Bildirim yükümlüsü", "Üst düzey yönetici", "") else (
            "Büyük ortak" if metin.KURUM.search(x["kisi"]) else "Yönetici")
        kisi = x["kisi"]
        baglam = _abd_baglam(conn, kod)
        etiket = f"ABD · YÖNETİCİ {'ALIMI' if alim else 'SATIŞI'}"
        tutar_metni = metin.tutar(x["tutar"], "dolar")
        kutular = [("Adet", metin.adet(x["adet"]) if x.get("adet") else "—"),
                   ("Ort. fiyat", metin.fiyat_metni(x["fiyat"], "$") if x.get("fiyat") else "—"),
                   ("Son 90 gün", f"{baglam['kisi']} alıcı" if alim else "—")]
        adres, kaynak = f"{SITE}/hisse/{kod}", "SEC Form 4"
        ilk = (f"{x['sirket']} (${kod}) {rol_iyelik(rol)} {kisi}, şirket hisselerinden "
               f"{tutar_metni}lık {'alım' if alim else 'satış'} yaptı.")
        ayrinti = (f"{_soyad(kisi)}, {metin.adet(x['adet'])} adet hisseyi ortalama "
                   f"{metin.fiyat_metni(x['fiyat'], 'dolar')} fiyattan {'aldı' if alim else 'sattı'}.") \
            if x.get("adet") and x.get("fiyat") else ""
        baglam_metni = (f"Son 90 günde {x['sirket']} hisselerinde {baglam['kisi']} yöneticinin alımı bildirildi."
                        if alim and baglam["kisi"] > 1 else "")
    else:   # Kongre
        parti = {"D": "Demokrat", "R": "Cumhuriyetçi"}.get(x.get("parti") or "", "")
        rol = "Senatör" if "senato" in (x.get("meclis") or "").lower() else "Temsilciler Meclisi"
        kisi = x["kisi"]
        etiket = f"ABD KONGRESİ · {'ALIM' if alim else 'SATIŞ'}"
        tutar_metni = (f"{metin.tutar(x['alt'], '').strip()} – {metin.tutar(x['ust'], 'dolar')}"
                       if x["alt"] != x["ust"] else metin.tutar(x["ust"], "dolar"))
        kutular = [("Parti", parti or "—"), ("İşlem tarihi", metin.gun(x["islem_tarihi"]) if x.get("islem_tarihi") else "—")]
        adres, kaynak = f"{SITE}/hisse/{kod}", "Kongre bildirimi"
        ilk = (f"ABD {'Senatörü' if rol == 'Senatör' else 'Temsilciler Meclisi üyesi'} {kisi}"
               f"{f' ({parti})' if parti else ''}, {x['sirket']} (${kod}) hissesinde {tutar_metni} arasında "
               f"{'alım' if alim else 'satış'} bildirdi.")
        ayrinti = "ABD'li siyasetçiler hisse işlemlerini yasa gereği 45 gün içinde açıklamak zorunda."
        baglam_metni = ""
        tarih = x.get("islem_tarihi") or tarih
        g = grafik(seri, 640, 214, 470, 210, tarih)

    seyir = ""
    if g and g.get("degisim") is not None and abs(g["degisim"]) >= 0.005 and g.get("degisim_etiket") == "İşlemden bu yana":
        seyir = f"Hisse işlem gününden bu yana {_yuzde(g['degisim'], isaretli=False)} {'yükseldi' if g['degisim'] > 0 else 'geriledi'}."
    govde = [ilk] + [p for p in (ayrinti, " ".join(t for t in (baglam_metni, seyir) if t)) if p]
    tam_faaliyet = aday["kart"].get("faaliyet_tam") or faaliyet
    if tam_faaliyet:
        govde.insert(1, f"Şirket hakkında: {tam_faaliyet}")
    gonderi = "\n\n".join(govde) + f"\n\nKaynak: {kaynak}\n{adres}"

    renk = MAVI if tur == "Geri alım" else (YESIL if alim else KIRMIZI)
    return {**aday, "grup": "veri", "metin": gonderi, "kart": {
        "tip": "islem", "renk": renk, "etiket": etiket, "kod": kod, "sirket": x["sirket"],
        "faaliyet": faaliyet, "kisi": kisi, "rol": rol, "tutar": tutar_metni,
        "tutar_alt": "tutarında alım" if alim and tur != "Geri alım" else ("tutarında geri alım" if tur == "Geri alım" else "tutarında satış"),
        "kutular": kutular, "grafik": g, "baglam": baglam_metni, "adres": adres, "kaynak": f"Kaynak: {kaynak}",
        "dosya": f"{kod}-{tarih}-{tur.split()[0].lower()}"}}


# ---------------------------------------------------------------------------
# Sıralama kartları
# ---------------------------------------------------------------------------

def _liste(anahtar, baslik, alt, satirlar, renk, kaynak, adres, birim_metni, gonderi_basligi):
    if len(satirlar) < 3:
        return None
    satirlar = satirlar[:5]
    en_cok = max(s["deger"] for s in satirlar) or 1
    for s in satirlar:
        s["oran"] = s["deger"] / en_cok
    gonderi = gonderi_basligi + "\n\n" + "\n".join(
        f"{i}. {s['kod_metin']} {s['ad']}: {s['deger_metni']}" for i, s in enumerate(satirlar, 1)
    ) + f"\n\nKaynak: {kaynak}\n{adres}"
    return {"anahtar": anahtar, "tur": "Sıralama", "grup": "veri", "onem": 1e12, "metin": gonderi,
            "kart": {"tip": "liste", "renk": renk, "etiket": "HAFTANIN LİSTESİ", "baslik": baslik, "alt": alt,
                     "satirlar": satirlar, "kaynak": f"Kaynak: {kaynak}", "adres": adres, "birim": birim_metni,
                     "dosya": anahtar.replace(":", "-")}}


def liste_kartlari(conn):
    bugun = date.today()
    hafta = (bugun - timedelta(days=7)).isoformat()
    ay = (bugun - timedelta(days=30)).isoformat()
    aralik = f"{_kisa_gun(hafta)} – {_kisa_gun(bugun.isoformat())}"
    hafta_no = bugun.isocalendar()
    damga = f"{hafta_no[0]}-{hafta_no[1]}"
    kartlar = []

    satirlar = [{"kod": r[0], "kod_metin": f"#{r[0]}", "ad": tr_baslik(kisa_unvan(r[1])) if r[1] else r[0], "deger": r[2],
                 "deger_metni": metin.tutar(r[2]), "ek": f"{r[3]} alım"} for r in conn.execute(
        """SELECT p.kod, s.unvan, SUM(p.tutar) AS t, COUNT(*) FROM kap_pay_islem p JOIN kap_bildirim b USING (indeks)
           LEFT JOIN bist_sirket s ON s.kod = p.kod
           WHERE b.yayin >= ? AND p.islem = 'buy' AND p.kisi_turu != 'fon' AND p.tutar > 0
           GROUP BY p.kod ORDER BY t DESC LIMIT 5""", (hafta,))]
    kartlar.append(_liste(f"liste:kap:{damga}", "Borsa İstanbul'da bu hafta en çok içeriden alım yapılan hisseler",
                          f"Yöneticilerin ve büyük ortakların KAP'a bildirdiği alımlar · {aralik}", satirlar, YESIL, "KAP",
                          f"{SITE}/bist", "TL",
                          f"Borsa İstanbul'da bu hafta yöneticilerin ve büyük ortakların en çok alım yaptığı hisseler ({aralik}):"))

    satirlar = [{"kod": r[0], "kod_metin": f"${r[0]}", "ad": sirket_gorunen_ad(r[1]) if r[1] else r[0], "deger": r[2],
                 "deger_metni": metin.tutar(r[2], "dolar"), "ek": f"{r[3]} yönetici"} for r in conn.execute(
        f"""SELECT ticker, MAX(COALESCE(company, asset_name)), SUM(amount_max) AS t, COUNT(DISTINCT person_slug)
            FROM transactions WHERE chamber IS NULL AND {TEMIZ} AND {GECERLI_KOD} AND action = 'buy' AND amount_max > 0
              AND disclosed_date >= ? AND COALESCE(job_title, '') != '%10 üzeri ortak'
            GROUP BY ticker ORDER BY t DESC LIMIT 5""", (hafta,))]
    kartlar.append(_liste(f"liste:form4:{damga}", "ABD'de bu hafta yöneticilerin en çok aldığı hisseler",
                          f"Şirket yöneticilerinin kendi şirketlerinde yaptığı alımlar (SEC Form 4) · {aralik}", satirlar,
                          MAVI, "SEC Form 4", f"{SITE}/islemler?kaynak=yonetici", "dolar",
                          f"ABD'de bu hafta şirket yöneticilerinin kendi parasıyla en çok aldığı hisseler ({aralik}):"))

    satirlar = [{"kod": r[0], "kod_metin": f"#{r[0]}", "ad": tr_baslik(kisa_unvan(r[1])) if r[1] else r[0], "deger": r[2],
                 "deger_metni": metin.tutar(r[2]), "ek": ""} for r in conn.execute(
        """SELECT g.kod, s.unvan, SUM(g.nominal * g.fiyat) AS t FROM kap_geri_alim g LEFT JOIN bist_sirket s ON s.kod = g.kod
           WHERE g.islem_tarihi >= ? GROUP BY g.kod ORDER BY t DESC LIMIT 5""", (hafta,))]
    kartlar.append(_liste(f"liste:geri:{damga}", "Bu hafta kendi hissesini en çok geri alan şirketler",
                          f"Borsa İstanbul'da pay geri alımları · {aralik}", satirlar, MOR, "KAP",
                          f"{SITE}/bist#geri-alim", "TL",
                          f"Borsa İstanbul'da bu hafta kendi hisselerini en çok geri alan şirketler ({aralik}):"))

    satirlar = [{"kod": r[0], "kod_metin": f"${r[0]}", "ad": sirket_gorunen_ad(r[1]) if r[1] else r[0], "deger": r[3],
                 "deger_metni": f"{metin.tutar(r[2], '').strip()} – {metin.tutar(r[3], 'dolar')}", "ek": f"{r[4]} üye"}
                for r in conn.execute(
        """SELECT ticker, MAX(asset_name), SUM(amount_min), SUM(amount_max) AS ust, COUNT(DISTINCT person_slug)
           FROM transactions WHERE chamber IS NOT NULL AND action = 'buy' AND disclosed_date >= ? AND ticker NOT IN ('N/A', '--')
           GROUP BY ticker ORDER BY ust DESC LIMIT 5""", (ay,))]
    kartlar.append(_liste(f"liste:kongre:{damga}", "ABD'li siyasetçilerin son 30 günde en çok aldığı hisseler",
                          "Kongre üyelerinin yasal hisse bildirimleri · bildirilen tutar aralığına göre", satirlar, "#F59E0B",
                          "Kongre bildirimleri", f"{SITE}/siyasetciler", "dolar",
                          "ABD Kongresi üyelerinin son 30 günde en çok aldığı hisseler (bildirilen tutar aralığı):"))
    return [k for k in kartlar if k]


def hareket_karti():
    """Borsa İstanbul'da son işlem gününün en çok yükselen ve düşen 5 hissesi."""
    try:
        from piyasa.bist import hareket, piyasa
        piyasa._dosyadan_oku()
        h = hareket.gunun_hareketi(piyasa._durum["veri"], adet=5)
    except Exception:
        return None
    if not h["yukselenler"] or not h["hareket_gunu"]:
        return None

    def satir(s):
        return {"kod": s["kod"], "ad": tr_baslik(kisa_unvan(s["unvan"])) if s.get("unvan") else s["kod"],
                "oran": s["f"]["g1"], "metin": _yuzde(s["f"]["g1"])}

    yukselen, dusen = [satir(s) for s in h["yukselenler"]], [satir(s) for s in h["dusenler"]]
    gun = metin.gun(h["hareket_gunu"])
    gonderi = (f"Borsa İstanbul'da {ek(gun, 'de')} en çok yükselen ve düşen hisseler:\n\n"
               + "\n".join(f"▲ #{s['kod']} {s['metin']}" for s in yukselen) + "\n\n"
               + "\n".join(f"▼ #{s['kod']} {s['metin']}" for s in dusen)
               + f"\n\nGün genelinde {h['artan']} hisse yükseldi, {h['azalan']} hisse geriledi.\n{SITE}/bist")
    return {"anahtar": f"hareket:{h['hareket_gunu']}", "tur": "Günün hareketi", "grup": "veri", "onem": 2e12,
            "metin": gonderi, "kart": {"tip": "hareket", "renk": YESIL, "etiket": "BORSA İSTANBUL",
                                      "baslik": f"{gun}: günün en çok yükselen ve düşen hisseleri",
                                      "alt": f"{h['artan']} hisse yükseldi · {h['azalan']} hisse geriledi",
                                      "yukselen": yukselen, "dusen": dusen, "adres": f"{SITE}/bist",
                                      "kaynak": "Fiyatlar: Borsa İstanbul (15 dk gecikmeli)",
                                      "dosya": f"bist-hareket-{h['hareket_gunu']}"}}
