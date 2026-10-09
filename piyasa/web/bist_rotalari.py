"""
Borsa İstanbul sayfaları: BIST 100 ve KAP bildirimleri (/bist) ve şirket sayfası (/bist/<kod>).
"""

import re
import threading
import time
from collections import Counter

from flask import Blueprint, abort, jsonify, render_template, request

from piyasa import fiyat, hisse_haberleri, sirket_profili, temel
from piyasa.bist import piyasa, sorgular

bist = Blueprint("bist", __name__)

KOD = re.compile(r"^[A-Z0-9]{3,6}$")
GUNLUK_SINIR = 0.105        # Borsa İstanbul fiyat marjı ±%10 (yuvarlama payıyla)
# Tanıtım metninin başındaki tam unvan: '... Anonim Ortakligi', '... A.S.', '... Sanayi ve Ticaret A.Ş.'
TR_UNVAN = re.compile(r"^[^,.]{3,120}?\b(Anonim\s+(Ortakligi|Ortaklığı|Sirketi|Şirketi)|A\.\s?[SŞ]\.?|T\.A\.[SŞO]\.?)",
                      re.IGNORECASE)


def _kucuk_grafik(degerler, genislik=100, yukseklik=30, nokta=32):
    """Küçük grafik için SVG noktaları; yüzlerce satırlık tabloda sayfa şişmesin diye seyreltilir."""
    if not degerler or len(degerler) < 2:
        return None
    if len(degerler) > nokta:
        adim_ = len(degerler) / nokta
        degerler = [degerler[int(i * adim_)] for i in range(nokta - 1)] + [degerler[-1]]
    az, cok = min(degerler), max(degerler)
    aralik = (cok - az) or 1
    adim = genislik / (len(degerler) - 1)
    noktalar = " ".join(f"{i * adim:.0f},{(1 - (v - az) / aralik) * (yukseklik - 4) + 2:.0f}"
                        for i, v in enumerate(degerler))
    return {"noktalar": noktalar, "artis": degerler[-1] >= degerler[0]}


def _tum_kodlar():
    """Fiyatı tazelenecek bütün hisseler: BIST 100 önce (ilk parçada gelsin)."""
    tum = sorgular.sirketler()
    return [x["kod"] for x in sorted(tum, key=lambda x: (not x["xu100"], x["kod"]))]


def _gecerli(f):
    """Günlük değişimi borsanın ±%10 sınırını aşan fiyat (düzeltilmemiş bölünme) gösterilmez."""
    if f and f.get("g1") is not None and abs(f["g1"]) > GUNLUK_SINIR:
        return {**f, "g1": None}
    return f


def _fiyat_ekle(sirketler, fiyatlar):
    for s in sirketler:
        f = _gecerli(fiyatlar.get(s["kod"]))
        s["f"] = f
        s["grafik"] = _kucuk_grafik(f["seri"]) if f else None
    return sirketler


@bist.route("/bist")
def liste():
    liste_ = request.args.get("liste", "tum")
    liste_ = liste_ if liste_ in sorgular.LISTELER else "tum"
    sektorler = sorgular.sektorler()
    sektor = request.args.get("sektor") or None
    sektor = sektor if sektor in {s[0] for s in sektorler} else None

    fiyatlar = piyasa.fiyatlar(_tum_kodlar())
    sirketler = _fiyat_ekle(sorgular.sirketler(liste_, sektor), fiyatlar)
    son = sorgular.son_islem_tarihleri([s["kod"] for s in sirketler])
    for s in sirketler:
        s["iceriden"] = son.get(s["kod"])

    # Günün hareketi bütün hisselerden. Borsa İstanbul'da günlük hareket ±%10 ile sınırlı:
    # bunu aşanlar bölünme ya da bedelsiz sermaye artırımının düzeltilmediği veri hatasıdır.
    # Son işlem günü fiyatı gelmeyen (eski kalan) hisseler de sayılmaz.
    tum = _fiyat_ekle(sorgular.sirketler(), fiyatlar)
    fiyatli = [s for s in tum if s["f"] and s["f"]["g1"] is not None]
    son_gun = Counter(s["f"]["tarih"] for s in fiyatli).most_common(1)[0][0] if fiyatli else None
    fiyatli = [s for s in fiyatli if s["f"]["tarih"] == son_gun and abs(s["f"]["g1"]) <= GUNLUK_SINIR]
    hareketli = sorted((s for s in fiyatli if s["f"]["fiyat"] >= 1), key=lambda s: s["f"]["g1"])
    return render_template(
        "bist.html",
        aktif="bist",
        sirketler=sirketler,
        liste=liste_,
        listeler=sorgular.LISTELER,
        sektor=sektor,
        sektorler=sektorler,
        toplam=len(tum),
        endeks=fiyatlar.get("XU100"),
        endeks30=fiyatlar.get("XU030"),
        yukselenler=hareketli[::-1][:6],
        dusenler=hareketli[:6],
        artan=sum(1 for s in fiyatli if s["f"]["g1"] > 0),
        azalan=sum(1 for s in fiyatli if s["f"]["g1"] < 0),
        pay_ozeti=sorgular.pay_ozeti(30),
        iceriden=sorgular.pay_islemleri(gun=60, limit=150),
        geri_alim=sorgular.geri_alim_ozeti(30),
    )


@bist.route("/bist/<kod>")
def sirket(kod):
    kod = kod.upper()
    if not KOD.match(kod):
        abort(404)
    s = sorgular.sirket(kod)
    if s is None:
        abort(404)
    islemler = sorgular.pay_islemleri(kod=kod, limit=100)
    fiyatlar = piyasa.fiyatlar(_tum_kodlar())
    benzerler = _fiyat_ekle(sorgular.benzerler(kod, s.get("sektor"), s.get("ana_sektor")), fiyatlar)
    return render_template(
        "bist_sirket.html",
        aktif="bist",
        s=s,
        f=_gecerli(fiyatlar.get(kod)),
        endeks=fiyatlar.get("XU100"),
        benzerler=benzerler,
        kisa_ad=sorgular.kisa_unvan(s["unvan"]),
        islemler=[i for i in islemler if i["kisi_turu"] != "fon"],
        fon_bildirimleri=[i for i in islemler if i["kisi_turu"] == "fon"],
        geri=sorgular.geri_alimlar(kod),
        aciklamalar=sorgular.ozel_aciklamalar(kod),
    )


@bist.route("/bist/<kod>/hakkinda")
def hakkinda(kod):
    kod = kod.upper()
    if not KOD.match(kod):
        abort(404)
    profil = sirket_profili.profil(piyasa.yahoo_kodu(kod), yahoo=piyasa.yahoo_kodu(kod))
    if not profil or not profil.get("ozet"):
        return "", 204
    s = sorgular.sirket(kod)
    if s:
        # Yahoo'nun Türkçe karaktersiz unvanı ('Türk Hava Yollari Anonim Ortakligi') yerine KAP'taki ad
        ozet = TR_UNVAN.sub(sorgular.kisa_unvan(s["unvan"]), profil["ozet"], count=1)
        profil = {**profil, "ozet": ozet, "merkez": s.get("sehir") or profil.get("merkez")}
    return render_template("_sirket_hakkinda.html", profil=profil)


@bist.route("/bist/<kod>/rakamlar")
def rakamlar(kod):
    kod = kod.upper()
    if not KOD.match(kod):
        abort(404)
    bilgiler = temel.temel_bilgiler(piyasa.yahoo_kodu(kod), ham=True)
    if not bilgiler:
        return "", 204
    return render_template("_temel.html", t=bilgiler)


@bist.route("/bist/<kod>/haberler")
def haberler(kod):
    kod = kod.upper()
    s = sorgular.sirket(kod) if KOD.match(kod) else None
    if not s:
        return "", 204
    ad = sorgular.kisa_unvan(s["unvan"])
    return render_template("_hisse_haberleri.html", haberler=hisse_haberleri.hisse_haberleri(kod, ad), sirket=ad)


@bist.route("/api/bist/<kod>/fiyat")
def fiyat_api(kod):
    kod = kod.upper()
    bilgi = fiyat.fiyat_bilgisi(piyasa.yahoo_kodu(kod), ham=True) if KOD.match(kod) else None
    if bilgi is None:
        return jsonify({"hata": "Bu hisse için güncel fiyat bulunamadı."}), 404
    return jsonify(bilgi)


@bist.route("/api/bist/<kod>/anlik")
def anlik_api(kod):
    kod = kod.upper()
    bilgi = fiyat.anlik_fiyat(piyasa.yahoo_kodu(kod), ham=True) if KOD.match(kod) else None
    if bilgi is None:
        return jsonify({"hata": "Anlık fiyat alınamadı."}), 404
    return jsonify(bilgi)


def fiyatlari_isit(aralik=14 * 60):
    """
    Yayındaki sitede BIST 100 fiyatlarını arka planda tazeler: 100 hissenin toplu
    indirilmesi yarım dakika sürebiliyor, ziyaretçi beklemesin.
    """
    def dongu():
        time.sleep(5)
        while True:
            try:
                piyasa.tazele(_tum_kodlar())
            except Exception:
                pass
            time.sleep(aralik)

    threading.Thread(target=dongu, name="bist-fiyat-isitma", daemon=True).start()
