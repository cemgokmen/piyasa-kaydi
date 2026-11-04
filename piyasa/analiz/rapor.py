"""
Hisse analiz raporu (/analiz/<kod>): teknik ve temel analizi, piyasa rejimini, risk planını
ve grafik verisini tek sözlükte toplar. Web katmanı yalnızca bunu çizer.

Veri: Yahoo Finance. Fiyat geçmişi 15 dakika, temel tablolar 6 saat bellekte tutulur.
"""

import math
import warnings
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import numpy as np

from piyasa import fiyat as fiyat_servisi
from piyasa.analiz import tarama, teknik, temel_analiz
from piyasa.analiz.ajan import kanit as ajan_kanit
from piyasa.analiz.ajan import okuma as ajan_okuma
from piyasa.analiz.destek_direnc import bolgeleri_hesapla
from piyasa.bicim import fiyat as fiyat_yazi
from piyasa.bicim import ondalik
from piyasa.onbellek import sureli

GECMIS_SURESI = 15 * 60
TEMEL_SURESI = 6 * 3600
SR_GUN = 756                       # destek/direnç için son 3 yıl
GRAFIK_GUN = 1260                  # grafikte son 5 yıl


class Bulunamadi(Exception):
    pass


# ---------------------------------------------------------------------------
# Kod çözme ve veri
# ---------------------------------------------------------------------------

def kod_coz(kod):
    """'THYAO' → BIST; 'AAPL' → ABD; 'BTC-USD', 'GC=F' → yalnızca teknik."""
    kod = (kod or "").strip().upper().removesuffix(".IS")
    if not kod or len(kod) > 15:
        raise Bulunamadi(kod)
    from piyasa.veritabani import get_connection
    satir = None
    with closing(get_connection()) as conn:
        try:
            satir = conn.execute("SELECT kod, unvan, ana_sektor, xu100 FROM bist_sirket WHERE kod = ?", (kod,)).fetchone()
        except Exception:
            satir = None
    if satir:
        return {"kod": kod, "yahoo": f"{kod}.IS", "endeks": "XU100.IS", "endeks_ad": "BIST 100", "piyasa": "BIST",
                "ad": satir[1], "sektor": satir[2], "xu100": bool(satir[3]), "para": "TRY", "temel": True}
    yahoo = kod if any(c in kod for c in "=^") else fiyat_servisi.yahoo_kodu(kod)
    hisse = not any(c in yahoo for c in "=^") and not yahoo.endswith("-USD")
    return {"kod": kod, "yahoo": yahoo, "endeks": "SPY" if hisse else None, "endeks_ad": "S&P 500" if hisse else None,
            "piyasa": "ABD" if hisse else "DİĞER", "ad": None, "sektor": None, "xu100": False,
            "para": "USD", "temel": hisse}


@sureli(GECMIS_SURESI)
def gecmis(yahoo, yil=5):
    import yfinance as yf
    df = yf.Ticker(yahoo).history(period=f"{yil}y", interval="1d", auto_adjust=True)
    if df is None or df.empty:
        return None
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    df.index = df.index.tz_localize(None).normalize()
    df = df[~df.index.duplicated(keep="last")]
    return df if len(df) >= 60 else None


@sureli(TEMEL_SURESI, hatada_eskisi=True)
def _temel_ham(yahoo):
    return temel_analiz.veri_al(yahoo)


def temel_ham(yahoo):
    try:
        return _temel_ham(yahoo)
    except Exception:
        return None


@sureli(TEMEL_SURESI)
def _tr_enflasyon():
    from piyasa.analiz.karsilastirma import enflasyon
    return temel_analiz.yillik_enflasyon(enflasyon("TR"))


def dolar_kuru():
    b = fiyat_servisi.fiyat_bilgisi("TRY=X", ham=True)
    return b["fiyat"] if b else None


# ---------------------------------------------------------------------------
# Risk planı
# ---------------------------------------------------------------------------

def risk_plani(t, bolgeler):
    """
    Stop ve hedef adayları. Pozisyon boyutu sayfada, kullanıcının sermayesi ve risk oranıyla hesaplanır:
        adet = sermaye × risk% / (giriş − stop)
    Stop yapısal seviyenin (destek) hemen altına konur; destek çok yakın ya da çok uzaksa ATR stopu.
    """
    gs = t["gosterge"]
    c, a = gs["close"], gs["atr"]
    if not c or not a:
        return None
    df = t["_df"]
    stoplar = [{"kod": "atr", "ad": "2 ATR altı", "fiyat": c - 2 * a,
                "aciklama": "Günlük ortalama hareketin iki katı aşağısı: olağan dalgalanmada tetiklenmez."}]
    destekler = sorted([b for b in bolgeler if b["tur"] == "destek" and b["ust"] < c], key=lambda b: -b["merkez"])
    destek_stop = None
    for b in destekler:
        s = b["alt"] - 0.25 * a
        if 0.8 * a <= c - s <= 5 * a:
            destek_stop = {"kod": "destek", "ad": "Desteğin altı", "fiyat": s,
                           "aciklama": f"{fiyat_yazi(b['alt'])}–{fiyat_yazi(b['ust'])} destek bölgesinin çeyrek ATR altı: "
                                       "destek kırılırsa senaryo bozulmuş demektir."}
            stoplar.append(destek_stop)
            break
    if len(df) >= 22:
        avize = float(df["High"].iloc[-22:].max()) - 3 * a
        if avize < c:
            stoplar.append({"kod": "avize", "ad": "İzleyen stop (Chandelier)", "fiyat": avize,
                            "aciklama": "Son 22 günün zirvesinden 3 ATR aşağısı; fiyat yükseldikçe yukarı taşınır."})
    if gs.get("st_yon") == 1 and gs.get("st_cizgi") and gs["st_cizgi"] < c:
        stoplar.append({"kod": "supertrend", "ad": "Süpertrend çizgisi", "fiyat": gs["st_cizgi"],
                        "aciklama": "Süpertrend (10, 3) yükseliş çizgisi; altında kapanış trendi düşüşe çevirir."})
    onerilen = destek_stop if destek_stop and 1.0 * a <= c - destek_stop["fiyat"] <= 4 * a else stoplar[0]

    direncler = sorted([b for b in bolgeler if b["tur"] == "direnç" and b["alt"] > c + 0.5 * a], key=lambda b: b["merkez"])
    hedefler = [{"ad": ad, "fiyat": b["alt"], "puan": b["puan"]} for ad, b in zip(("İlk direnç", "İkinci direnç"), direncler[:2], strict=False)]
    if not hedefler:
        hedefler = [{"ad": "3 ATR yukarısı", "fiyat": c + 3 * a, "puan": None}]
    risk = c - onerilen["fiyat"]
    for h in hedefler:
        h["rr"] = (h["fiyat"] - c) / risk if risk > 0 else None
    for s in stoplar:
        s["uzaklik"] = s["fiyat"] / c - 1
        s["fiyat"] = round(s["fiyat"], 4)
    return {"giris": c, "atr": a, "stoplar": stoplar, "onerilen": onerilen["kod"], "hedefler": hedefler,
            "rr": hedefler[0]["rr"]}


# ---------------------------------------------------------------------------
# Birleşik karar
# ---------------------------------------------------------------------------

def kontrol_listesi(t, temel, rj, risk, bist):
    """İşleme girmeden önce bakılan maddeler (ikili)."""
    gs, b = t["gosterge"], t["bilesen"]
    m = []

    def madde(ad, gecti, aciklama):
        if gecti is not None:
            m.append({"ad": ad, "gecti": bool(gecti), "aciklama": aciklama})

    if bist and rj:
        madde("Piyasa rejimi uygun", rj["kod"] != "ayi", f"BIST 100: {rj['ad'].lower()}")
    madde("Fiyat 200 günlük ortalamanın üstünde", gs["sma200"] and gs["close"] > gs["sma200"], "Ana trend yukarı")
    madde("50 günlük, 200 günlüğün üstünde", gs["sma50"] and gs["sma200"] and gs["sma50"] > gs["sma200"], "Orta vadeli trend yukarı")
    if t["evre"]:
        madde("Haftalık grafikte 2. evre", t["evre"]["evre"] == 2, f"Weinstein: {t['evre']['evre']}. evre")
    if b.get("relatif") is not None:
        madde("Endeksten güçlü", b["relatif"] > 0, "Son 3-6 ayda endeksi geride bırakıyor")
    if b.get("hacim") is not None:
        madde("Hacim alıcıları destekliyor", b["hacim"] > 0, "Para akışı ve OBV olumlu")
    if gs["rsi"] is not None:
        madde("Aşırı alımda değil", gs["rsi"] < 75, f"RSI {ondalik(gs['rsi'], 0)}")
    if temel and temel.get("puan") is not None:
        madde("Temel puan 50 ve üstü", temel["puan"] >= 50, f"Temel puan {ondalik(temel['puan'], 0)}")
        madde("Kırmızı bayrak yok", not temel["bayraklar"], f"{len(temel['bayraklar'])} bayrak" if temel["bayraklar"] else "Bilançoda alarm yok")
    if risk and risk.get("rr") is not None:
        madde("Risk/ödül en az 2", risk["rr"] >= 2, f"İlk hedefe göre {ondalik(risk['rr'], 1)} R")
    return m


DURUMLAR = {
    "guclu": ("Güçlü aday", "Şirket iyi, fiyat yükseliyor"),
    "spekulatif": ("Riskli yükseliş", "Fiyat yükseliyor ama şirket zayıf"),
    "izle": ("İzle", "Şirket iyi ama fiyat düşüyor"),
    "uzak": ("Uzak dur", "Şirket zayıf, fiyat düşüyor"),
    "yukselis": ("Yükselişte", "Fiyat yükseliyor, şirket orta"),
    "dusus": ("Düşüşte", "Fiyat düşüyor, şirket orta"),
    "notr": ("Bekle", "Net bir işaret yok"),
    "olumlu": ("Fiyat yükseliyor", "Şirket verisi yok"),
    "olumsuz": ("Fiyat düşüyor", "Şirket verisi yok"),
}


def durum_kodu(teknik_orta, temel_puan):
    """Tek kelimelik sonuç: orta vade grafik puanı ve şirket puanından."""
    k, tp = teknik_orta, temel_puan
    if k is None:
        return None
    if tp is None:
        return "olumlu" if k >= 60 else "olumsuz" if k <= 40 else "notr"
    if k >= 60 and tp >= 55:
        return "guclu"
    if k >= 60 and tp < 45:
        return "spekulatif"
    if k <= 40 and tp >= 55:
        return "izle"
    if k <= 40 and tp < 45:
        return "uzak"
    if k >= 60:
        return "yukselis"
    if k <= 40:
        return "dusus"
    return "notr"


KARAR_METNI = {
    "guclu": "Hem şirket sağlam hem fiyat yükselişte. Bu ikisinin bir arada olması, geçmişte en istikrarlı getiriyi veren durumdur. "
             "Alırken fiyatın biraz geri çekilmesini bekleyebilirsin; zarar durdurma (stop) seviyesini aşağıdaki bölümden al.",
    "spekulatif": "Fiyat yükseliyor ama şirketin rakamları zayıf. Yükseliş haber ya da beklentiyle olabilir ve çabuk sönebilir. "
                  "Alacaksan az al ve stopa sadık kal.",
    "izle": "Şirket sağlam ama fiyat düşüyor. Düşen hisseyi erken almak yerine düşüşün bitmesini bekle: "
            "fiyatın 50 günlük ortalamanın üstüne çıkması iyi bir işarettir.",
    "uzak": "Hem fiyat düşüyor hem şirketin rakamları zayıf. Geçmişte en kötü getiriyi veren durum budur.",
    "yukselis": "Fiyat yükselişte, şirketin rakamları ise ne iyi ne kötü. Alınabilir ama 'Güçlü aday' kadar sağlam değil; daha küçük al.",
    "dusus": "Fiyat düşüşte, şirketin rakamları ortalama. Şu an almak için bir sebep yok.",
    "notr": "Fiyatın yönü belli değil. Net bir işaret çıkana kadar beklemek daha iyi.",
    "olumlu": "Fiyat yükselişte. Bu varlık için şirket verisi yok; karar yalnızca grafiğe dayanıyor, stopa sadık kal.",
    "olumsuz": "Fiyat düşüşte. Alım için düşüşün bitmesini beklemek daha güvenli.",
}


def birlesik_karar(t, temel, rj, bist):
    k = t["puanlar"].get("orta")
    tp = temel.get("puan") if temel else None
    kod = durum_kodu(k, tp)
    if kod is None:
        return None
    uyari = None
    if bist and rj and rj["kod"] == "ayi" and kod in ("guclu", "spekulatif", "olumlu", "yukselis"):
        uyari = "Borsanın geneli düşüşte: iyi hisseler de endeksle birlikte düşebilir. Normalin yarısı kadar al."
    return {"kod": kod, "ad": DURUMLAR[kod][0], "kisa": DURUMLAR[kod][1], "metin": KARAR_METNI[kod],
            "teknik": k, "temel": tp, "uyari": uyari}


def isabet_ozeti(isabet):
    """Orta vade puanının bu hissede geçmişte ne kadar işe yaradığı, tek cümleyle."""
    i = isabet.get("orta") if isabet else None
    if not i:
        return None
    gruplar = {g["ad"][:7]: g for g in i["gruplar"]}
    olumlu, olumsuz = gruplar.get("Olumlu "), gruplar.get("Olumsuz")
    kor = i["korelasyon"]
    if not olumlu or olumlu.get("n", 0) < 5 or not olumsuz or olumsuz.get("n", 0) < 3 or kor is None:
        return {"kod": "yetersiz", "metin": "Bu hissenin geçmişi, puanın ne kadar tuttuğunu ölçmek için yetmiyor."}
    fark = (olumlu.get("ortalama") or 0) - (olumsuz.get("ortalama") or 0)
    if kor > 0.10 and fark > 0:
        return {"kod": "iyi", "metin": "Güven notu: bu hissede grafik puanı geçmişte tuttu. Puan iyiyken hisse sonraki aylarda daha iyi gitti."}
    if kor < -0.10 and fark < 0:
        return {"kod": "ters", "metin": "Dikkat: bu hissede grafik puanı geçmişte ters çalıştı. Puan iyiyken hisse genelde sonra düştü, kötüyken yükseldi. "
                                       "Bu hissede grafik puanına güvenme."}
    return {"kod": "zayif", "metin": "Dikkat: bu hissede grafik puanı geçmişte pek tutmadı. Ona fazla güvenme; şirketin rakamlarına ve destek seviyelerine de bak."}


EGILIM_METNI = {
    "trendli": "Son iki yılda getiriler rassal bir seriden daha uzun süre aynı yönde gitmiş.",
    "donuslu": "Son iki yılda getiriler rassal bir seriden daha sık yön değiştirmiş.",
    "rassal": "Son iki yılda getirilerin yönü rassal bir seriden ayırt edilemiyor.",
}


def egilim_ozeti(e):
    """Tezin 'bu hissede trend takibi işe yarar mı?' sorusu. Cevabın sınırı da yazılır: bkz. analiz_ajani/notlar/altay-1997.md."""
    if not e:
        return None
    return {**e, "metin": EGILIM_METNI[e["kod"]]
            + " Bu ölçümü ağırlık ayarında kullanmıyoruz: BIST 100'de bir dönemin sonucu sonraki dönemi öngörmedi."}


def _hedef_metni(f, kanitlar=None):
    durum = f["durum"]
    if durum == "olusuyor":
        return "Oluşuyor, henüz teyit yok: kırılış gelmeden işlem sinyali sayılmaz."
    yon = "yukarı" if f["kirilis_yon"] > 0 else "aşağı"
    bas = "Hacim teyitli" if f["hacimli"] else ("Aşağı" if f["kirilis_yon"] < 0 else "Hacimsiz, teyitsiz")
    metin = f"{bas} {yon} kırılış, {fiyat_yazi(f['kirilis_fiyat'])}. Kaynakların hedefi {fiyat_yazi(f['hedef'])}."
    k = (kanitlar or {}).get(f["kod"])
    if k and k.get("n", 0) >= 20:
        metin += f" BIST 100'de bu türün %{round(k['hedef'] * 100)} kadarı 60 günde hedefe ulaştı."
    return metin


def cizgi_dayanikliligi(t, kanit):
    """Geçerli çizginin eğimine göre, BIST 100'de benzer eğimli çizgilerin ne sıklıkla kırıldığı."""
    k = (kanit or {}).get("cizgiler")
    if not k:
        return []
    sonuc = []
    for c in t.get("trend_cizgileri") or []:
        if c["durum"] == "gecerli":
            i = 0 if c["egim"] <= k["kesit"][0] else 1 if c["egim"] <= k["kesit"][1] else 2
            ad = ("yatık", "orta eğimli", "dik")[i]
            sonuc.append({"baslik": "Trend çizgisinin dayanıklılığı", "yon": 0,
                          "metin": f"{c['tur'].capitalize()} çizgisi {ad}. BIST 100'de bu eğimdeki çizgilerin %{round(k['kirilma'][i] * 100)} kadarı {k['ufuk']} gün içinde kırıldı."})
    return sonuc


def klasik_sunum(t, kanitlar=None):
    sonuc = []
    for f in t.get("klasik") or []:
        yon = 0 if f["durum"] == "olusuyor" else f.get("kirilis_yon", 0)
        ek = " Sağ omuzdaki hacim soldakilerden düşük olmalıydı; değil." if f.get("hacim_uygun") is False else ""
        sonuc.append({"ad": f["ad"], "yon": yon, "aciklama": _hedef_metni(f, kanitlar) + ek})
    return sonuc


# ---------------------------------------------------------------------------
# Grafik verisi
# ---------------------------------------------------------------------------

def _yuvarla(seri, basamak):
    return [None if (v is None or (isinstance(v, float) and not math.isfinite(v))) else round(float(v), basamak)
            for v in seri]


def grafik_verisi(t, bolgeler):
    g, df = t["_g"], t["_df"]
    g, df = g.iloc[-GRAFIK_GUN:], df.iloc[-GRAFIK_GUN:]
    son = float(df["Close"].iloc[-1])
    b = 2 if son >= 10 else 3 if son >= 1 else 5
    fib = t["fibonacci"]
    return {
        "t": [d.strftime("%Y-%m-%d") for d in df.index],
        "o": _yuvarla(df["Open"], b), "h": _yuvarla(df["High"], b), "l": _yuvarla(df["Low"], b), "c": _yuvarla(df["Close"], b),
        "v": [int(x) if np.isfinite(x) else 0 for x in df["Volume"]],
        "sma20": _yuvarla(g["sma20"], b), "sma50": _yuvarla(g["sma50"], b), "sma200": _yuvarla(g["sma200"], b),
        "bbu": _yuvarla(g["bb_ust"], b), "bba": _yuvarla(g["bb_alt"], b),
        "st": _yuvarla(g["st_cizgi"], b), "sty": [int(x) if np.isfinite(x) else 0 for x in g["st_yon"]],
        "rsi": _yuvarla(g["rsi"], 1),
        "macd": _yuvarla(g["macd"], b + 1), "macds": _yuvarla(g["macd_sinyal"], b + 1), "macdh": _yuvarla(g["macd_hist"], b + 1),
        "bolgeler": [{"alt": z["alt"], "ust": z["ust"], "tur": z["tur"], "puan": z["puan"]} for z in bolgeler],
        "noktalar": t["noktalar"],
        "cizgiler": [{k: c[k] for k in ("tur", "durum", "t1", "f1", "t3", "f3", "kanal_f1", "kanal_f3")} for c in t.get("trend_cizgileri") or []],
        "fib": [{"oran": s["oran"], "fiyat": s["fiyat"]} for s in fib["seviyeler"]] if fib else [],
        "basamak": b,
    }


# ---------------------------------------------------------------------------
# Rapor
# ---------------------------------------------------------------------------

def rapor(kod):
    k = kod_coz(kod)
    with ThreadPoolExecutor(max_workers=3) as havuz:
        f_df = havuz.submit(gecmis, k["yahoo"])
        f_endeks = havuz.submit(gecmis, k["endeks"]) if k["endeks"] else None
        f_temel = havuz.submit(temel_ham, k["yahoo"]) if k["temel"] else None
        df = f_df.result()
        endeks_df = f_endeks.result() if f_endeks else None
        ham = f_temel.result() if f_temel else None
    if df is None:
        raise Bulunamadi(kod)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        endeks = endeks_df["Close"] if endeks_df is not None else None
        t = teknik.analiz(df, endeks)
        try:
            sr = bolgeleri_hesapla(df.iloc[-SR_GUN:])
            bolgeler = sr["bolgeler"]
        except Exception:
            sr, bolgeler = None, []

        bilgi = (ham or {}).get("bilgi") or {}
        temel = None
        medyan_kaynak = None
        if ham:
            medyan, medyan_kaynak = tarama.medyan_al(k["kod"]) if k["piyasa"] == "BIST" else (None, None)
            try:
                temel = temel_analiz.degerlendir(enflasyon=_tr_enflasyon() if bilgi.get("financialCurrency") == "TRY" else None,
                                                 medyan=medyan, sektor=k["sektor"], **ham)
            except Exception:
                temel = None

    tv = tarama.veri()
    rj = ((tv.get("teknik") or {}).get("rejim")) if k["piyasa"] == "BIST" else None
    risk = risk_plani(t, bolgeler)
    kanit = ajan_kanit.oku()
    t["formasyonlar"] = klasik_sunum(t, kanit.get("formasyonlar")) + t["formasyonlar"]
    para = bilgi.get("currency") or k["para"]
    return {
        "kimlik": {**k, "ad": k["ad"] or bilgi.get("longName") or bilgi.get("shortName") or k["kod"],
                   "sektor_yahoo": bilgi.get("sector"), "endustri": bilgi.get("industry"), "para": para},
        "teknik": t,
        "okuma": teknik.okuma(t, bolgeler) + cizgi_dayanikliligi(t, kanit),
        "senaryo": teknik.senaryolar(t, bolgeler),
        "bolgeler": bolgeler,
        "sr": sr,
        "temel": temel,
        "medyan_kaynak": medyan_kaynak,
        "rejim": rj,
        "karar": birlesik_karar(t, temel, rj, k["piyasa"] == "BIST"),
        "kontrol": kontrol_listesi(t, temel, rj, risk, k["piyasa"] == "BIST"),
        "isabet_ozeti": isabet_ozeti(t["isabet"]),
        "ajan": ajan_okuma.oku(t["_df"], t["_g"]),
        "egilim": egilim_ozeti(t["egilim"]),
        "risk": risk,
        "kur": None if para == "TRY" else dolar_kuru() if para == "USD" else None,
        "grafik": grafik_verisi(t, bolgeler),
    }


def genel_bakis():
    """/analiz sayfası: rejim, genişlik ve BIST 100 tarama tablosu."""
    v = tarama.veri()
    t = v.get("teknik") or {}
    temel = v.get("temel") or {}
    adlar, sektorler = v.get("adlar") or {}, v.get("sektorler") or {}
    satirlar = []
    for kod, s in (t.get("hisseler") or {}).items():
        tm = temel.get(kod) or {}
        satirlar.append({"kod": kod, "ad": adlar.get(kod), "sektor": sektorler.get(kod), **s,
                         "temel": tm.get("puan"), "temel_bilesen": tm.get("bilesen"), "fk": tm.get("fk"), "pddd": tm.get("pddd"),
                         "roe": tm.get("roe"), "piotroski": tm.get("piotroski"), "bayrak": tm.get("bayrak"),
                         "birlesik": _birlesik_puan(s["puan"].get("orta"), tm.get("puan")),
                         "durum": durum_kodu(s["puan"].get("orta"), tm.get("puan"))})
    satirlar.sort(key=lambda s: -(s["birlesik"] if s["birlesik"] is not None else -1))
    return {"satirlar": satirlar, "durumlar": DURUMLAR, "genislik": t.get("genislik"), "rejim": t.get("rejim"), "zaman": t.get("zaman"),
            "temel_sayisi": sum(1 for s in temel.values() if s.get("puan") is not None),
            "medyan": (v.get("medyan") or {}).get("genel"),
            "kural_tablosu": ajan_okuma.ozet_tablosu(), "kanit": ajan_kanit.oku()}


def _birlesik_puan(teknik_p, temel_p):
    if teknik_p is None:
        return None
    if temel_p is None:
        return teknik_p
    return 0.5 * teknik_p + 0.5 * temel_p
