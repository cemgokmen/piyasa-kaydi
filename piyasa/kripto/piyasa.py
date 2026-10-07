"""
Kripto paraların canlı piyasa verileri (Yahoo Finance, ücretsiz):

  bilgi(slug)       piyasa değeri, dolaşımdaki arz, 24 saatlik hacim, tüm zamanların zirvesi
  toplu_bilgi()     bütün coinlerin bilgisi (paralel)
  vadeli(slug)      CME vadelisinin fiyatı: piyasanın ileri tarih için bugün anlaştığı fiyat
  dolar_tl()        dolar/TL kuru (TL fiyatı için)

Sonuçlar bellekte tutulur; boş cevaplar önbelleğe alınmaz.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import yfinance as yf

from piyasa import fiyat
from piyasa.bicim import AYLAR_UZUN
from piyasa.emtia.beklenti import vade_kodu
from piyasa.emtia.tanimlar import GOSTERGELER
from piyasa.kripto.tanimlar import KRIPTO, KRIPTOLAR
from piyasa.onbellek import sureli


class VeriYok(Exception):
    pass


def _sayi(deger):
    try:
        return float(deger) if deger is not None else None
    except (TypeError, ValueError):
        return None


def _info_al(yahoo, deneme=2):
    """Yahoo'nun ham bilgi sözlüğü; boş gelirse bir kez daha dener."""
    bilgi = {}
    for i in range(deneme):
        try:
            bilgi = yf.Ticker(yahoo).info or {}
        except Exception:
            bilgi = {}
        if bilgi.get("marketCap"):
            break
        time.sleep(1.5 * (i + 1))
    return bilgi


@sureli(15 * 60, hatada_eskisi=True)
def _bilgi(yahoo):
    bilgi = _info_al(yahoo)
    if not bilgi.get("marketCap"):
        raise VeriYok(yahoo)        # boş cevap önbelleğe alınmasın
    fiyat_ = _sayi(bilgi.get("regularMarketPrice"))
    zirve = _sayi(bilgi.get("allTimeHigh"))
    return {
        "fiyat": fiyat_,
        "piyasa_degeri": _sayi(bilgi.get("marketCap")),
        "tam_deger": _sayi(bilgi.get("fullyDilutedValue")),
        "dolasim": _sayi(bilgi.get("circulatingSupply")),
        "toplam_arz": _sayi(bilgi.get("totalSupply")),
        "azami_arz": _sayi(bilgi.get("maxSupply")),
        "hacim_24s": _sayi(bilgi.get("volume24Hr") or bilgi.get("regularMarketVolume")),
        "zirve": zirve,
        "zirveden_uzaklik": (fiyat_ / zirve - 1) if fiyat_ and zirve else None,
        "dip": _sayi(bilgi.get("allTimeLow")),
        "yillik_yuksek": _sayi(bilgi.get("fiftyTwoWeekHigh")),
        "yillik_dusuk": _sayi(bilgi.get("fiftyTwoWeekLow")),
        "ort_200": _sayi(bilgi.get("twoHundredDayAverage")),
        "logo": bilgi.get("coinImageUrl") or bilgi.get("logoUrl"),
        "site": bilgi.get("website"),
        "teknik_belge": bilgi.get("whitepaper"),
    }


def bilgi(slug):
    """Coinin piyasa bilgisi; alınamazsa None."""
    k = KRIPTO.get(slug)
    if not k:
        return None
    try:
        return _bilgi(k["yahoo"])
    except Exception:
        return None


def toplu_bilgi():
    """{slug: bilgi ya da None} — liste sayfası için paralel."""
    with ThreadPoolExecutor(max_workers=8) as havuz:
        return dict(zip((k["slug"] for k in KRIPTOLAR), havuz.map(bilgi, (k["slug"] for k in KRIPTOLAR)),
                        strict=True))


def dolar_tl():
    kur = fiyat.anlik_fiyat(GOSTERGELER["usdtry"]["yahoo"], ham=True)
    return kur["fiyat"] if kur and kur.get("fiyat") else None


# CME kripto vadelileri her ay işlem görür ama Yahoo'da genellikle yalnızca
# yakın vadeler ve çeyrek sonları bulunur; en uzak bulunan vade kullanılır.
@sureli(30 * 60)
def _vadeli(kok, spot_kodu):
    spot = fiyat.anlik_fiyat(spot_kodu, ham=True)
    if not spot or not spot.get("fiyat"):
        return None
    for ay_sonra in (12, 9, 6, 3, 1):
        kod, yil, ay = vade_kodu(kok, "CME", (3, 6, 9, 12), ay_sonra=ay_sonra)
        v = fiyat.anlik_fiyat(kod, ham=True)
        if v and v.get("fiyat"):
            gun = (date(yil, ay, 28) - date.today()).days
            fark = v["fiyat"] / spot["fiyat"] - 1
            return {
                "vade": f"{AYLAR_UZUN[ay - 1]} {yil}",
                "fiyat": v["fiyat"],
                "spot": spot["fiyat"],
                "fark": fark,
                # Yıllığa çevrilmiş fark: vadelinin ne kadar "primli" olduğunu gösterir
                "yillik": (1 + fark) ** (365 / gun) - 1 if gun > 30 else None,
            }
    return None


def vadeli(slug):
    k = KRIPTO.get(slug)
    if not k or not k["vadeli"]:
        return None
    try:
        return _vadeli(k["vadeli"], k["yahoo"])
    except Exception:
        return None
