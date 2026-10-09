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

import re
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
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
        "cg_id": x.get("id"), "ad": x.get("name"), "sembol": (x.get("symbol") or "").upper(),
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


PIYASA_PARAMETRELERI = {"vs_currency": "usd", "per_page": 250, "price_change_percentage": "1h,24h,7d,30d,1y",
                        "sparkline": "true"}


@sureli(3 * 60, hatada_eskisi=True)
def _coingecko():
    """
    Piyasa değerine göre ilk 250 kripto para tek istekte; elle profili yazılmış coinlerden
    bu listeye girmeyen olursa ikinci istekle tamamlanır. {coingecko kimliği: satır}
    """
    cevap = requests.get(f"{COINGECKO}/coins/markets", params={**PIYASA_PARAMETRELERI, "order": "market_cap_desc"},
                         headers=BASLIK, timeout=25)
    cevap.raise_for_status()
    satirlar = {x["id"]: _cg_satiri(x) for x in cevap.json()}
    eksik = [k["coingecko"] for k in KRIPTOLAR if k["coingecko"] not in satirlar]
    if eksik:
        try:
            ek = requests.get(f"{COINGECKO}/coins/markets", params={**PIYASA_PARAMETRELERI, "ids": ",".join(eksik)},
                              headers=BASLIK, timeout=25)
            ek.raise_for_status()
            satirlar.update({x["id"]: _cg_satiri(x) for x in ek.json()})
        except requests.RequestException:
            pass
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


# Blok yüksekliği kaynakları; biri yavaşsa ötekine geçilir. Hiçbiri yoksa son
# yarılanmadan (840.000. blok, 20 Nisan 2024) bu yana geçen süreden tahmin edilir.
YUKSEKLIK_KAYNAKLARI = ("https://blockchain.info/q/getblockcount", "https://mempool.space/api/blocks/tip/height")
SON_YARILANMA = (840_000, datetime(2024, 4, 20, 0, 9, tzinfo=UTC))


def _blok_yuksekligi():
    for adres in YUKSEKLIK_KAYNAKLARI:
        try:
            cevap = requests.get(adres, headers=BASLIK, timeout=(3, 4))
            cevap.raise_for_status()
            return int(cevap.text.strip()), True
        except (requests.RequestException, ValueError):
            continue
    blok, zaman = SON_YARILANMA
    return blok + int((datetime.now(UTC) - zaman).total_seconds() // (BLOK_SURESI * 60)), False


@sureli(30 * 60, hatada_eskisi=True)
def _yarilanma():
    yukseklik, kesin = _blok_yuksekligi()
    sonraki = (yukseklik // YARILANMA_ARALIGI + 1) * YARILANMA_ARALIGI
    kalan = sonraki - yukseklik
    tarih = (datetime.now(UTC) + timedelta(minutes=kalan * BLOK_SURESI)).date()
    donem = sonraki // YARILANMA_ARALIGI
    return {"yukseklik": yukseklik, "kesin": kesin, "sonraki_blok": sonraki, "kalan_blok": kalan, "tarih": tarih.isoformat(),
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
    # Aday vadeler paralel denenir (Yahoo'da olmayan vadeye sorgu birkaç saniye sürüyor)
    adaylar = list(dict.fromkeys(vade_kodu(kok, "CME", (3, 6, 9, 12), ay_sonra=a) for a in (12, 9, 6, 3, 1)))
    with ThreadPoolExecutor(max_workers=len(adaylar)) as havuz:
        fiyatlar = list(havuz.map(lambda aday: fiyat.anlik_fiyat(aday[0], ham=True), adaylar))
    for (_kod, yil, ay), v in zip(adaylar, fiyatlar, strict=True):
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


# ---------------------------------------------------------------------------
# BÜTÜN KRİPTOLAR: elle profili yazılmış 27 coin + hacmi yüksek diğerleri
# ---------------------------------------------------------------------------

EN_AZ_HACIM = 5_000_000          # 24 saatlik işlem hacmi, dolar
# Başka bir coinin sarılmış, stake edilmiş ya da köprülenmiş kopyaları ayrı yatırım aracı değil
KOPYA = re.compile(r"^(wrapped|staked|bridged|binance-peg|coinbase wrapped|liquid staked|lido staked|"
                   r"rocket pool eth|mantle staked|ether\.fi staked|kelp|renzo|restaked|jito staked|"
                   r"marinade staked|benqi liquid|savings|l2 standard bridged)|"
                   r"\b(wrapped|staked|bridged)\b", re.I)
KRIPTO_CG = {k["coingecko"]: k for k in KRIPTOLAR}

# CoinGecko kategorilerinin Türkçe karşılığı (öncelik sırasıyla)
KATEGORILER = [
    ("Stablecoins", "Sabit para"), ("Tokenized Gold", "Altına dayalı token"), ("Meme", "Meme coin"),
    ("Privacy Coins", "Gizlilik odaklı para"), ("Exchange-based Tokens", "Borsa tokeni"),
    ("Decentralized Exchange (DEX)", "Merkeziyetsiz borsa"), ("Oracle", "Veri ağı (oracle)"),
    ("Lending/Borrowing Protocols", "DeFi (kredi)"), ("Artificial Intelligence (AI)", "Yapay zeka"),
    ("Real World Assets (RWA)", "Gerçek varlık tokenizasyonu"), ("Gaming (GameFi)", "Oyun"),
    ("Layer 2 (L2)", "Ölçekleme ağı (katman 2)"), ("Smart Contract Platform", "Akıllı sözleşme platformu"),
    ("Layer 1 (L1)", "Blokzincir (katman 1)"), ("Payment Solutions", "Ödeme ağı"),
    ("Decentralized Finance (DeFi)", "DeFi (merkeziyetsiz finans)"), ("Infrastructure", "Altyapı"),
]
SABIT_ISARETI = re.compile(r"usd|dollar|euro|eur\b", re.I)


def _tahmini_tur(satir):
    """Kategori bilinmeyen coin: fiyatı 1 dolara çok yakın ve adı dolar çağrıştırıyorsa sabit para."""
    f = satir.get("fiyat") or 0
    if 0.97 <= f <= 1.03 and SABIT_ISARETI.search(f"{satir.get('ad')} {satir.get('sembol')}"):
        return "Sabit para"
    return "Kripto para"


def liste():
    """
    Sitedeki bütün kripto paralar, piyasa değerine göre: [{slug, ad, sembol, tur, ozel, b}].
    ozel=True: elle yazılmış ayrıntılı profili var (adresi kendi kısa adı, ör. /kripto/xrp).
    """
    try:
        cg = _coingecko()
    except Exception:
        cg = {}
    sonuc = []
    for cg_id, b in cg.items():
        k = KRIPTO_CG.get(cg_id)
        if k:
            sonuc.append({"slug": k["slug"], "ad": k["ad"], "sembol": k["sembol"], "tur": k["tur"], "ozel": True, "b": b})
        elif (b.get("hacim_24s") or 0) >= EN_AZ_HACIM and b.get("piyasa_degeri") and not KOPYA.search(
                f"{b.get('ad')} {cg_id}") and re.fullmatch(r"[A-Z0-9]{1,10}", b.get("sembol") or ""):
            sonuc.append({"slug": cg_id, "ad": b["ad"], "sembol": b["sembol"],
                          "tur": kayitli_turler().get(cg_id) or _tahmini_tur(b), "ozel": False, "b": b})
    if not sonuc:   # CoinGecko'ya ulaşılamadı: elle profili olanlar Yahoo'dan
        for k in KRIPTOLAR:
            b = _yahoo_bilgisi(k)
            if b:
                sonuc.append({"slug": k["slug"], "ad": k["ad"], "sembol": k["sembol"], "tur": k["tur"], "ozel": True, "b": b})
    sonuc.sort(key=lambda x: -(x["b"].get("piyasa_degeri") or 0))
    return sonuc


@sureli(10 * 60)
def kayitli_turler():
    """Profili alınmış coinlerin türü: {cg_id: tur}."""
    from piyasa.veritabani import get_connection
    try:
        with closing(get_connection()) as conn:
            return {r[0]: r[1] for r in conn.execute("SELECT cg_id, tur FROM kripto_profil WHERE tur IS NOT NULL")}
    except Exception:
        return {}


def dinamik(slug):
    """Elle profili olmayan coin (CoinGecko kimliğiyle); listede yoksa None."""
    return next((x for x in liste() if x["slug"] == slug and not x["ozel"]), None)


@sureli(30 * 60, hatada_eskisi=True)
def _cg_gecmis(cg_id):
    """CoinGecko'dan son 365 günün günlük kapanışı ve hacmi (ücretsiz sürümün sınırı)."""
    import pandas as pd

    cevap = requests.get(f"{COINGECKO}/coins/{cg_id}/market_chart",
                         params={"vs_currency": "usd", "days": 365, "interval": "daily"}, headers=BASLIK, timeout=25)
    cevap.raise_for_status()
    v = cevap.json()
    if not v.get("prices"):
        raise VeriYok(cg_id)
    tablo = pd.DataFrame({
        "Close": [p[1] for p in v["prices"]],
        "Volume": [h[1] for h in v.get("total_volumes", [])][:len(v["prices"])] or 0,
    }, index=pd.to_datetime([p[0] for p in v["prices"]], unit="ms").normalize())
    tablo = tablo[~tablo.index.duplicated(keep="last")]
    return fiyat.tablodan_bilgi(cg_id, tablo)


def _ayni_coin_mi(yahoo, cg):
    """Yahoo'daki sembol aynı coin mi? Fiyat ve (varsa) 30 günlük ile 1 yıllık değişim tutmalı."""
    if not (yahoo.get("fiyat") and cg.get("fiyat")) or abs(yahoo["fiyat"] / cg["fiyat"] - 1) > 0.08:
        return False
    for anahtar, cg_alani, pay in (("1a", "degisim_30g", 0.10), ("1y", "degisim_1y", 0.20)):
        y = next((d["oran"] for d in yahoo["degisimler"] if d["anahtar"] == anahtar), None)
        c = cg.get(cg_alani)
        if y is not None and c is not None and abs((1 + y) / (1 + c) - 1) > pay:
            return False
    return True


def gecmis(x):
    """
    Grafik ve dönemsel değişimler. Önce Yahoo ('SOL-USD' gibi; 10 yıla kadar geçmiş), Yahoo'nun
    fiyatı CoinGecko'yla tutmuyorsa (aynı sembol başka coine ait olabilir) CoinGecko'nun son 365 günü.
    """
    yahoo = KRIPTO[x["slug"]]["yahoo"] if x.get("ozel") else f"{x['sembol']}-USD"
    try:
        b = fiyat.fiyat_bilgisi(yahoo, ham=True)
    except Exception:
        b = None
    if b and (x.get("ozel") or _ayni_coin_mi(b, x.get("b") or {})):
        return b
    if x.get("ozel"):
        return b
    try:
        return _cg_gecmis(x["slug"])
    except Exception:
        return None


@sureli(24 * 3600)
def _cg_ayrinti(cg_id):
    cevap = requests.get(f"{COINGECKO}/coins/{cg_id}", params={
        "localization": "false", "tickers": "false", "market_data": "false", "community_data": "false",
        "developer_data": "false"}, headers=BASLIK, timeout=25)
    cevap.raise_for_status()
    return cevap.json()


def _ilk_cumleler(metin, adet=2):
    duz = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", (metin or "").replace("&nbsp;", " "))).strip()
    cumleler = re.split(r"(?<=[.!?])\s+(?=[A-Z])", duz)
    return " ".join(cumleler[:adet])[:600]


def profil(x):
    """
    Elle profili olmayan coinin tanıtımı: CoinGecko açıklamasının ilk cümleleri (Türkçeye
    çevrilir), türü, sitesi ve başlangıç yılı. Veritabanında 30 gün saklanır.
    """
    from piyasa.ceviri import adi_koruyarak_cevir, turkcelestir
    from piyasa.veritabani import get_connection

    cg_id = x["slug"]
    with closing(get_connection()) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS kripto_profil (
            cg_id TEXT PRIMARY KEY, ozet TEXT, ozet_en TEXT, tur TEXT, site TEXT, baslangic TEXT, guncelleme TEXT)""")
        kayit = conn.execute("SELECT * FROM kripto_profil WHERE cg_id = ?", (cg_id,)).fetchone()
        if kayit and kayit["ozet"] and kayit["guncelleme"] >= (datetime.now(UTC) - timedelta(days=30)).isoformat():
            return dict(kayit)
        try:
            v = _cg_ayrinti(cg_id)
        except Exception:
            return dict(kayit) if kayit else None
        kategoriler = v.get("categories") or []
        tur = next((tr for en, tr in KATEGORILER if en in kategoriler), None) or _tahmini_tur(x.get("b") or {})
        ozet_en = _ilk_cumleler((v.get("description") or {}).get("en"))
        try:
            ozet = turkcelestir(adi_koruyarak_cevir(ozet_en, x["ad"])) if ozet_en else None
        except Exception:
            ozet = None
        site = next((s for s in (v.get("links") or {}).get("homepage", []) if s), None)
        yeni = {"cg_id": cg_id, "ozet": ozet, "ozet_en": ozet_en or None, "tur": tur, "site": site,
                "baslangic": v.get("genesis_date"), "guncelleme": datetime.now(UTC).isoformat()}
        conn.execute("INSERT OR REPLACE INTO kripto_profil VALUES (:cg_id, :ozet, :ozet_en, :tur, :site, :baslangic, "
                     ":guncelleme)", yeni)
        conn.commit()
    return yeni
