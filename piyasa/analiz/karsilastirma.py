"""
Yatırım karşılaştırma: "X tarihinde şu kadar parayı şuna yatırsaydım bugün ne olurdu?"

Fiyatlar Yahoo Finance'ın aylık kapanışlarıdır (fonlarda temettüler dahil, auto_adjust). Her
varlık seçilen para birimine (TL ya da dolar) aylık dolar/TL kuruyla çevrilir. Enflasyon,
seçilen para biriminin ülkesinin tüketici fiyatları endeksidir (TL: TÜFE, dolar: ABD CPI;
bkz. toplama/enflasyon.py).

İki yatırım biçimi:
  tek    başlangıç ayında bir kez yatırılır
  aylik  başlangıçtan bugüne her ay aynı tutar yatırılır (düzenli birikim)

Vergi, komisyon, alış-satış farkı ve saklama ücreti hesaba katılmaz.
"""

import re
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import date

import pandas as pd
import yfinance as yf

from piyasa.onbellek import sureli
from piyasa.veritabani import get_connection

ILK_AY = "2006-01"            # 2005'teki YTL geçişi eski Türk verilerinde sıçrama yaratıyor
KUR = "TRY=X"                 # 1 doların TL karşılığı
EN_FAZLA_EK = 4               # kullanıcının eklediği hisse/kripto sayısı
EN_FAZLA_VARLIK = 10
KOD = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,11}$")

# anahtar, ad, Yahoo kodu (None: para biriminin kendisi), para birimi, grup, renk
VARLIKLAR = [
    ("tl", "Türk lirası", None, "TRY", "Nakit", "#94A3B8"),
    ("dolar", "Dolar", None, "USD", "Nakit", "#22C55E"),
    ("euro", "Euro", "EURUSD=X", "USD", "Nakit", "#14B8A6"),
    ("altin", "Altın", "GC=F", "USD", "Emtia", "#EAB308"),
    ("gumus", "Gümüş", "SI=F", "USD", "Emtia", "#A1A1AA"),
    ("petrol", "Brent petrol", "BZ=F", "USD", "Emtia", "#78716C"),
    ("bist100", "BIST 100", "XU100.IS", "TRY", "Borsa", "#EF4444"),
    ("sp500", "S&P 500", "SPY", "USD", "Borsa", "#3B82F6"),
    ("nasdaq", "Nasdaq 100", "QQQ", "USD", "Borsa", "#8B5CF6"),
    ("bitcoin", "Bitcoin", "BTC-USD", "USD", "Kripto", "#F97316"),
    ("ethereum", "Ethereum", "ETH-USD", "USD", "Kripto", "#6366F1"),
]
VARLIK = {v[0]: dict(zip(("anahtar", "ad", "yahoo", "para", "grup", "renk"), v, strict=True)) for v in VARLIKLAR}
EK_RENKLER = ["#EC4899", "#06B6D4", "#84CC16", "#F43F5E"]
ACIKLAMALAR = {
    "tl": "Parayı TL olarak elde tutmak (faiz yok)",
    "dolar": "Dolar alıp elde tutmak",
    "euro": "Euro alıp elde tutmak",
    "altin": "Ons altın fiyatı; gram altınla aynı oranda değişir",
    "gumus": "Ons gümüş fiyatı",
    "petrol": "Brent petrol vadeli fiyatı",
    "bist100": "Borsa İstanbul'un en büyük 100 şirketi (endeks)",
    "sp500": "ABD'nin en büyük 500 şirketi (SPY fonu, temettüler dahil)",
    "nasdaq": "ABD teknoloji ağırlıklı 100 şirket (QQQ fonu, temettüler dahil)",
    "bitcoin": "En büyük kripto para",
    "ethereum": "İkinci büyük kripto para",
}
VARSAYILAN = {"tutar": 10_000, "para": "TRY", "tur": "tek", "varliklar": ["tl", "dolar", "altin", "bist100", "sp500", "bitcoin"]}


# ---------------------------------------------------------------------------
# Veri
# ---------------------------------------------------------------------------

@sureli(12 * 3600)
def _aylik(yahoo):
    """{'2016-10': kapanış} — ayın son kapanışı (içinde bulunulan ay için en son fiyat)."""
    tablo = yf.download(yahoo, period="max", interval="1mo", auto_adjust=True, progress=False, timeout=20)
    if tablo is None or tablo.empty:
        return {}
    kapanis = tablo["Close"]
    if isinstance(kapanis, pd.DataFrame):
        kapanis = kapanis.iloc[:, 0]
    return {i.strftime("%Y-%m"): float(v) for i, v in kapanis.dropna().items() if v > 0}


def aylik(yahoo):
    try:
        return _aylik(yahoo)
    except Exception:
        return {}


def enflasyon(ulke):
    with closing(get_connection()) as conn:
        try:
            return {r[0]: r[1] for r in conn.execute("SELECT ay, endeks FROM enflasyon WHERE ulke = ? ORDER BY ay", (ulke,))}
        except Exception:
            return {}


def ek_varlik(kod, sira=0):
    """Kullanıcının yazdığı kod: Borsa İstanbul hissesi, kripto para ya da ABD hissesi."""
    kod = kod.strip().upper()
    if not KOD.match(kod):
        return None
    renk = EK_RENKLER[sira % len(EK_RENKLER)]
    from piyasa.kripto.tanimlar import KRIPTOLAR
    with closing(get_connection()) as conn:
        try:
            bist = conn.execute("SELECT unvan FROM bist_sirket WHERE kod = ?", (kod.removesuffix(".IS"),)).fetchone()
        except Exception:
            bist = None
    if bist:
        kod = kod.removesuffix(".IS")
        return {"anahtar": kod, "ad": kod, "yahoo": f"{kod}.IS", "para": "TRY", "grup": "Hisse", "renk": renk,
                "adres": f"/bist/{kod}", "aciklama": "Borsa İstanbul hissesi"}
    kripto = next((k for k in KRIPTOLAR if k["sembol"] == kod.removesuffix("-USD")), None)
    if kripto:
        return {"anahtar": kod, "ad": kripto["ad"], "yahoo": kripto["yahoo"], "para": "USD", "grup": "Kripto",
                "renk": renk, "adres": f"/kripto/{kripto['slug']}", "aciklama": "Kripto para"}
    if kod.endswith("-USD"):
        sembol = kod.removesuffix("-USD")
        return {"anahtar": kod, "ad": sembol, "yahoo": kod, "para": "USD", "grup": "Kripto", "renk": renk,
                "adres": None, "aciklama": "Kripto para"}
    return {"anahtar": kod, "ad": kod, "yahoo": kod, "para": "USD", "grup": "Hisse", "renk": renk,
            "adres": f"/hisse/{kod}", "aciklama": "ABD hissesi (temettüler dahil)"}


# ---------------------------------------------------------------------------
# Hesap
# ---------------------------------------------------------------------------

def aylar(bas, son):
    y, a = map(int, bas.split("-"))
    sy, sa = map(int, son.split("-"))
    sonuc = []
    while (y, a) <= (sy, sa):
        sonuc.append(f"{y:04d}-{a:02d}")
        y, a = (y + 1, 1) if a == 12 else (y, a + 1)
    return sonuc


def _doldur(seri, ay_listesi):
    """Ay listesindeki her ay için değer; eksik ay bir öncekiyle doldurulur, başta veri yoksa None."""
    sonuc, son = [], None
    for ay in ay_listesi:
        son = seri.get(ay, son)
        sonuc.append(son)
    return sonuc


def _cevir(fiyat, kur, kaynak, hedef):
    if kaynak == hedef:
        return fiyat
    if fiyat is None or kur is None:
        return None
    return fiyat * kur if hedef == "TRY" else fiyat / kur


def _en_buyuk_dusus(degerler):
    zirve, dusus = 0.0, 0.0
    for v in degerler:
        zirve = max(zirve, v)
        if zirve:
            dusus = min(dusus, v / zirve - 1)
    return dusus


def _ic_getiri(odemeler, son_deger):
    """Aylık düzenli yatırımın yıllık getirisi (iç verim oranı); odemeler: her ay yatırılan tutar."""
    n = len(odemeler)

    def nbd(aylik_oran):
        return sum(o * (1 + aylik_oran) ** (n - 1 - i) for i, o in enumerate(odemeler)) - son_deger

    alt, ust = -0.99, 1.0
    if nbd(alt) * nbd(ust) > 0:
        return None
    for _ in range(100):
        orta = (alt + ust) / 2
        if nbd(alt) * nbd(orta) <= 0:
            ust = orta
        else:
            alt = orta
    return (1 + (alt + ust) / 2) ** 12 - 1


def hesapla(varliklar, bas, tutar, para="TRY", tur="tek"):
    """
    varliklar: VARLIK sözlüğü biçiminde liste. Dönen: aylar, enflasyon çizgisi ve her varlık için
    değer serisi ile özet (son değer, getiri, yıllık getiri, enflasyondan arındırılmış getiri, en büyük düşüş).
    """
    yahoo = {v["yahoo"] for v in varliklar if v["yahoo"]} | {KUR}
    with ThreadPoolExecutor(min(8, len(yahoo))) as havuz:
        seriler = dict(zip(yahoo, havuz.map(aylik, yahoo), strict=True))
    kur_serisi = seriler[KUR]
    if not kur_serisi:
        return None
    son = max(kur_serisi)
    ay_listesi = aylar(bas, son)
    if len(ay_listesi) < 2:
        return None
    kur = _doldur(kur_serisi, ay_listesi)

    # Enflasyon: verisi henüz yayımlanmamış son aylarda son bilinen düzeyde kalır
    tufe = enflasyon("TR" if para == "TRY" else "US")
    tufe_dizi = _doldur(tufe, ay_listesi)
    enflasyon_son_ay = max((a for a in tufe if a <= son), default=None)

    def yatirim(fiyatlar):
        """Fiyat serisinden (seçilen para biriminde) yatırımın aylık değeri ve yatırılan toplam."""
        degerler, adet, yatirilan, odemeler = [], 0.0, 0.0, []
        for i, f in enumerate(fiyatlar):
            if tur == "aylik" or i == 0:
                adet += tutar / f
                yatirilan += tutar
                odemeler.append(tutar)
            else:
                odemeler.append(0.0)
            degerler.append(adet * f)
        return degerler, yatirilan, odemeler

    # Enflasyon çizgisi: yatırılan paranın alım gücünü korumak için her ay ulaşması gereken tutar
    enflasyon_cizgisi = None
    if all(tufe_dizi):
        enflasyon_cizgisi = [d * tufe_dizi[i] for i, d in enumerate(_enflasyon_degeri(tufe_dizi, tutar, tur))]

    sonuc, eksik = [], []
    for v in varliklar:
        if v["yahoo"]:
            ham = _doldur(seriler.get(v["yahoo"], {}), ay_listesi)
        else:
            ham = [1.0] * len(ay_listesi)
        fiyatlar = [_cevir(f, k, v["para"], para) for f, k in zip(ham, kur, strict=True)]
        # Verisi seçilen aydan sonra başlayan yatırım (ör. sonradan halka arz olan hisse) kendi ilk ayından
        # hesaplanır; o aya kadar grafikte çizgisi yoktur
        ilk = next((i for i, f in enumerate(fiyatlar) if f is not None), None)
        if ilk is None or ilk == len(fiyatlar) - 1:
            eksik.append(v)
            continue
        kendi = fiyatlar[ilk:]
        degerler, yatirilan, odemeler = yatirim(kendi)
        son_deger = degerler[-1]
        yil = (len(kendi) - 1) / 12
        if tur == "tek":
            yillik = (son_deger / yatirilan) ** (1 / yil) - 1 if yil >= 1 and son_deger > 0 else None
        else:
            yillik = _ic_getiri(odemeler, son_deger) if yil >= 1 else None
        # Enflasyon karşılığı da yatırımın kendi döneminden
        kendi_tufe = tufe_dizi[ilk:]
        enf_son = (_enflasyon_degeri(kendi_tufe, tutar, tur)[-1] * kendi_tufe[-1]) if all(kendi_tufe) else None
        sonuc.append({
            **v,
            "aciklama": v.get("aciklama") or ACIKLAMALAR.get(v["anahtar"], ""),
            "degerler": [None] * ilk + degerler,
            "bas": ay_listesi[ilk],
            "tam": ilk == 0,                 # seçilen ayın başından beri mi?
            "son": son_deger,
            "yatirilan": yatirilan,
            "getiri": son_deger / yatirilan - 1,
            "kat": son_deger / yatirilan,
            "yillik": yillik,
            "reel": son_deger / enf_son - 1 if enf_son else None,
            "dusus": _en_buyuk_dusus(kendi),
        })
    sonuc.sort(key=lambda s: s["son"], reverse=True)
    yatirilan = tutar * (len(ay_listesi) if tur == "aylik" else 1)
    return {
        "aylar": ay_listesi,
        "varliklar": sonuc,
        "eksik": eksik,
        "enflasyon": enflasyon_cizgisi,
        "enflasyon_orani": (tufe_dizi[-1] / tufe_dizi[0] - 1) if tufe_dizi[0] and tufe_dizi[-1] else None,
        "enflasyon_son_ay": enflasyon_son_ay,
        "yatirilan": yatirilan,
        "son_ay": son,
        "kur_bas": kur[0],
        "kur_son": kur[-1],
    }


def _enflasyon_degeri(tufe_dizi, tutar, tur):
    """Her ayın sonunda, yatırılan paranın alım gücünü korumak için gereken tutar ÷ o ayın TÜFE'si."""
    sonuc, toplam = [], 0.0
    for i, t in enumerate(tufe_dizi):
        if tur == "aylik" or i == 0:
            toplam += tutar / t
        sonuc.append(toplam)
    return sonuc


def varsayilan_baslangic():
    bugun = date.today()
    return f"{bugun.year - 10:04d}-{bugun.month:02d}"


def gecerli_baslangic(deger):
    """'2016-10' biçiminde, ILK_AY ile bir yıl öncesi arasında; değilse None."""
    if not deger or not re.match(r"^\d{4}-\d{2}$", deger):
        return None
    y, a = map(int, deger.split("-"))
    bugun = date.today()
    if not 1 <= a <= 12 or deger < ILK_AY or (y, a) > (bugun.year - 1, bugun.month):
        return None
    return deger

