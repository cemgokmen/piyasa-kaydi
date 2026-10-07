"""
Kripto paraların canlı piyasa verileri (ücretsiz kaynaklar):

  bilgi(slug)        fiyat, gerçek 24 saatlik değişim, piyasa değeri ve sırası, arz, zirve (CoinGecko;
                     alınamazsa Yahoo Finance)
  toplu_bilgi()      bütün coinlerin bilgisi (CoinGecko'ya tek istek)
  genel_piyasa()     bütün kripto piyasasının değeri ve Bitcoin'in payı (CoinGecko)
  korku_endeksi()    Kripto Korku ve Açgözlülük Endeksi (alternative.me)
  yarilanma()        Bitcoin'in bir sonraki yarılanmasına kalan blok ve tahmini tarih (mempool.space)
  vadeli(slug)       CME vadelisinin fiyatı: piyasanın ileri tarih için bugün anlaştığı fiyat
  dolar_tl()         dolar/TL kuru (TL fiyatı için)

Sonuçlar bellekte tutulur; boş cevaplar önbelleğe alınmaz.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import requests
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


COINGECKO = "https://api.coingecko.com/api/v3"
BASLIK = {"User-Agent": "PiyasaKaydi/1.0", "Accept": "application/json"}


def _yuzde(deger):
    """CoinGecko yüzdeyi 3,12 gibi verir; sitede oran (0,0312) kullanılır."""
    return deger / 100 if deger is not None else None


def _cg_satiri(x):
    zirve_tarihi = (x.get("ath_date") or "")[:10] or None
    return {
        "fiyat": _sayi(x.get("current_price")),
        "degisim_1s": _yuzde(x.get("price_change_percentage_1h_in_currency")),
        "degisim_24s": _yuzde(x.get("price_change_percentage_24h_in_currency")),
        "degisim_7g": _yuzde(x.get("price_change_percentage_7d_in_currency")),
        "degisim_30g": _yuzde(x.get("price_change_percentage_30d_in_currency")),
        "degisim_1y": _yuzde(x.get("price_change_percentage_1y_in_currency")),
        "yuksek_24s": _sayi(x.get("high_24h")),
        "dusuk_24s": _sayi(x.get("low_24h")),
        "piyasa_degeri": _sayi(x.get("market_cap")),
        "sira": x.get("market_cap_rank"),
        "tam_deger": _sayi(x.get("fully_diluted_valuation")),
        "dolasim": _sayi(x.get("circulating_supply")),
        "toplam_arz": _sayi(x.get("total_supply")),
        "azami_arz": _sayi(x.get("max_supply")),
        "hacim_24s": _sayi(x.get("total_volume")),
        "zirve": _sayi(x.get("ath")),
        "zirve_tarihi": zirve_tarihi,
        "zirveden_uzaklik": _yuzde(x.get("ath_change_percentage")),
        "dip": _sayi(x.get("atl")),
        "logo": x.get("image"),
        "guncelleme": x.get("last_updated"),
        # Son 7 günün saatlik fiyatları (liste sayfasındaki küçük grafik)
        "hafta_serisi": [v for v in (x.get("sparkline_in_7d") or {}).get("price", []) if v is not None],
        "kaynak": "CoinGecko",
    }


@sureli(2 * 60, hatada_eskisi=True)
def _coingecko():
    """Takip edilen bütün coinler tek istekte: {coingecko kimliği: satır}."""
    cevap = requests.get(f"{COINGECKO}/coins/markets", params={
        "vs_currency": "usd", "ids": ",".join(k["coingecko"] for k in KRIPTOLAR),
        "per_page": 250, "price_change_percentage": "1h,24h,7d,30d,1y", "sparkline": "true",
    }, headers=BASLIK, timeout=20)
    cevap.raise_for_status()
    satirlar = {x["id"]: _cg_satiri(x) for x in cevap.json()}
    if not satirlar:
        raise VeriYok("coingecko")
    return satirlar


# CoinGecko satırındaki bütün alanlar; Yahoo yedeğinde olmayanlar boş kalır
ALANLAR = ("fiyat", "degisim_1s", "degisim_24s", "degisim_7g", "degisim_30g", "degisim_1y", "yuksek_24s", "dusuk_24s",
           "piyasa_degeri", "sira", "tam_deger", "dolasim", "toplam_arz", "azami_arz", "hacim_24s", "zirve",
           "zirve_tarihi", "zirveden_uzaklik", "dip", "logo", "guncelleme", "hafta_serisi")


def _yahoo_bilgisi(k):
    try:
        b = _bilgi(k["yahoo"])
    except Exception:
        return None
    return {**dict.fromkeys(ALANLAR), **b, "kaynak": "Yahoo Finance"}


def bilgi(slug):
    """Coinin piyasa bilgisi; CoinGecko'ya ulaşılamazsa Yahoo; ikisi de yoksa None."""
    k = KRIPTO.get(slug)
    if not k:
        return None
    try:
        satir = _coingecko().get(k["coingecko"])
    except Exception:
        satir = None
    if satir and satir["fiyat"]:
        # Yahoo'da olup CoinGecko'nun vermediği bağlantılar (site, teknik belge)
        return satir
    return _yahoo_bilgisi(k)


def toplu_bilgi():
    """{slug: bilgi ya da None}."""
    try:
        cg = _coingecko()
    except Exception:
        cg = {}
    if cg:
        # CoinGecko'nun vermediği coin olursa onun için Yahoo'ya düşülür
        return {k["slug"]: cg.get(k["coingecko"]) or _yahoo_bilgisi(k) for k in KRIPTOLAR}
    with ThreadPoolExecutor(max_workers=8) as havuz:
        return dict(zip((k["slug"] for k in KRIPTOLAR), havuz.map(_yahoo_bilgisi, KRIPTOLAR), strict=True))


@sureli(10 * 60, hatada_eskisi=True)
def _genel():
    cevap = requests.get(f"{COINGECKO}/global", headers=BASLIK, timeout=20)
    cevap.raise_for_status()
    v = cevap.json()["data"]
    return {
        "toplam_deger": v["total_market_cap"]["usd"],
        "hacim_24s": v["total_volume"]["usd"],
        "degisim_24s": _yuzde(v.get("market_cap_change_percentage_24h_usd")),
        "btc_payi": _yuzde(v["market_cap_percentage"].get("btc")),
        "eth_payi": _yuzde(v["market_cap_percentage"].get("eth")),
        "coin_sayisi": v.get("active_cryptocurrencies"),
    }


def genel_piyasa():
    try:
        return _genel()
    except Exception:
        return None


KORKU_ETIKETLERI = {
    "Extreme Fear": ("Aşırı korku", "satim"), "Fear": ("Korku", "satim"), "Neutral": ("Nötr", ""),
    "Greed": ("Açgözlülük", "alim"), "Extreme Greed": ("Aşırı açgözlülük", "alim"),
}


@sureli(30 * 60, hatada_eskisi=True)
def _korku():
    cevap = requests.get("https://api.alternative.me/fng/", params={"limit": 31}, headers=BASLIK, timeout=20)
    cevap.raise_for_status()
    veri = cevap.json()["data"]
    if not veri:
        raise VeriYok("fng")

    def oku(x):
        etiket, ton = KORKU_ETIKETLERI.get(x["value_classification"], (x["value_classification"], ""))
        return {"deger": int(x["value"]), "etiket": etiket, "ton": ton,
                "tarih": datetime.fromtimestamp(int(x["timestamp"]), UTC).date().isoformat()}

    gunler = [oku(x) for x in veri]
    return {**gunler[0], "dun": gunler[1] if len(gunler) > 1 else None,
            "hafta_once": gunler[7] if len(gunler) > 7 else None,
            "ay_once": gunler[30] if len(gunler) > 30 else None,
            "seri": [[g["tarih"], g["deger"]] for g in reversed(gunler)]}


def korku_endeksi():
    try:
        return _korku()
    except Exception:
        return None


YARILANMA_ARALIGI = 210_000      # blok
BLOK_SURESI = 10                 # dakika


@sureli(30 * 60, hatada_eskisi=True)
def _yarilanma():
    cevap = requests.get("https://mempool.space/api/blocks/tip/height", headers=BASLIK, timeout=15)
    cevap.raise_for_status()
    yukseklik = int(cevap.text)
    sonraki = (yukseklik // YARILANMA_ARALIGI + 1) * YARILANMA_ARALIGI
    kalan = sonraki - yukseklik
    tarih = (datetime.now(UTC) + timedelta(minutes=kalan * BLOK_SURESI)).date()
    donem = sonraki // YARILANMA_ARALIGI
    return {"yukseklik": yukseklik, "sonraki_blok": sonraki, "kalan_blok": kalan, "tarih": tarih.isoformat(),
            "kalan_gun": (tarih - date.today()).days,
            "odul_simdi": 50 / 2 ** (donem - 1), "odul_sonra": 50 / 2 ** donem}


def yarilanma():
    try:
        return _yarilanma()
    except Exception:
        return None


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
