"""
Hisse sayfasındaki "Şirketin rakamları": değerleme, karlılık, bilanço,
sahiplik, son çeyrek sonuçları ve analist beklentileri (Yahoo Finance).

Ham veriyi alan kısım (_veri_al) ile göstergeleri hazırlayan kısım
(hazirla) ayrıdır; hazirla saf bir fonksiyondur ve ağa çıkmaz.
Sonuç 6 saat bellekte tutulur: bu rakamlar gün içinde değişmez.
"""

from datetime import UTC, date, datetime

import yfinance as yf

from piyasa import fiyat as fiyat_servisi
from piyasa.bicim import AYLAR, ondalik, para, uzun_tarih, yuzde
from piyasa.onbellek import sureli

ONBELLEK_SURESI = 6 * 3600

ONERILER = {
    "strong_buy": ("Güçlü al", "artis"), "buy": ("Al", "artis"), "hold": ("Tut", "notr"),
    "underperform": ("Zayıf", "azalis"), "sell": ("Sat", "azalis"), "strong_sell": ("Güçlü sat", "azalis"),
}


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _sayi(deger):
    """NaN ve boş değerleri None yapar."""
    try:
        deger = float(deger)
    except (TypeError, ValueError):
        return None
    return None if deger != deger else deger


def _oran(deger):
    """0.2761 -> '%27,6'; -0.55 -> '−%55,0'"""
    deger = _sayi(deger)
    if deger is None:
        return None
    return f"{'−' if deger < 0 else ''}%{ondalik(abs(deger) * 100, 1)}"


def _kat(deger):
    """Pozitif çarpan (F/K, PD/DD...): 38.17 -> '38,2'; eksi ya da yoksa None."""
    deger = _sayi(deger)
    return ondalik(deger, 1) if deger and deger > 0 else None


def _degisim(simdi, onceki):
    simdi, onceki = _sayi(simdi), _sayi(onceki)
    if simdi is None or not onceki:
        return None
    return (simdi - onceki) / abs(onceki)


def _satir(etiket, deger, aciklama=""):
    return {"etiket": etiket, "deger": deger, "aciklama": aciklama} if deger not in (None, "—") else None


def _ceyrek_adi(tarih):
    """Üç aylık dönemin adı: 2026-06-30 -> 'Nis–Haz 2026'"""
    bas = (tarih.month - 3) % 12
    yil = tarih.year if tarih.month > 2 else tarih.year - 1
    on = f" {yil}" if yil != tarih.year else ""
    return f"{AYLAR[bas]}{on}–{AYLAR[tarih.month - 1]} {tarih.year}"


def _kalem(tablo, satir, sutun):
    if tablo is None or satir not in tablo.index or sutun not in tablo.columns:
        return None
    return _sayi(tablo.at[satir, sutun])


# ---------------------------------------------------------------------------
# Göstergeler
# ---------------------------------------------------------------------------

def _ceyrekler(gelir, bilanco, nakit, birim):
    """Son çeyrek özeti ve grafik için son beş çeyrek (eskiden yeniye)."""
    if gelir is None or gelir.empty or "Total Revenue" not in gelir.index:
        return None, []
    sutunlar = sorted(gelir.columns)[-5:]
    seri = []
    for s in sutunlar:
        g, n = _kalem(gelir, "Total Revenue", s), _kalem(gelir, "Net Income", s)
        if g is not None:
            seri.append({"ad": _ceyrek_adi(s.date()), "gelir": g, "net": n})
    if not seri:
        return None, []

    en_buyuk = max(max(abs(c["gelir"]), abs(c["net"] or 0)) for c in seri) or 1
    for c in seri:
        c["gelir_boy"] = round(abs(c["gelir"]) / en_buyuk * 100, 1)
        c["net_boy"] = round(abs(c["net"] or 0) / en_buyuk * 100, 1)
        c["net_eksi"] = (c["net"] or 0) < 0
        c["gelir_yazi"], c["net_yazi"] = para(c["gelir"], birim), para(c["net"], birim)

    son = sutunlar[-1]
    gecen_yil = sutunlar[-5] if len(sutunlar) >= 5 else None
    gelir_son, net_son = _kalem(gelir, "Total Revenue", son), _kalem(gelir, "Net Income", son)
    ozet = {
        "donem": _ceyrek_adi(son.date()),
        "bitis": uzun_tarih(son.date().isoformat()),
        "kalemler": [k for k in (
            {"etiket": "Gelir", "deger": para(gelir_son, birim),
             "degisim": _degisim(gelir_son, _kalem(gelir, "Total Revenue", gecen_yil))},
            {"etiket": "Net kar", "deger": para(net_son, birim),
             "degisim": _degisim(net_son, _kalem(gelir, "Net Income", gecen_yil))},
            {"etiket": "Hisse başına kar", "deger": _hbk(_kalem(gelir, "Diluted EPS", son), birim),
             "degisim": _degisim(_kalem(gelir, "Diluted EPS", son), _kalem(gelir, "Diluted EPS", gecen_yil))},
            {"etiket": "Net kar marjı", "deger": _oran(net_son / gelir_son) if gelir_son and net_son is not None else None,
             "degisim": None},
            {"etiket": "Serbest nakit akışı", "deger": para(_kalem(nakit, "Free Cash Flow", son), birim)
             if _kalem(nakit, "Free Cash Flow", son) is not None else None, "degisim": None},
        ) if k["deger"] not in (None, "—")],
        "karsilastirma": "geçen yılın aynı çeyreğine göre" if gecen_yil is not None else None,
    }
    return ozet, seri


def _hbk(deger, birim):
    deger = _sayi(deger)
    if deger is None:
        return None
    return f"{'−' if deger < 0 else ''}{ondalik(abs(deger), 2)} {para(0, birim).split()[-1]}"


def _aralik_52(bilgi, son_fiyat):
    dusuk, yuksek = _sayi(bilgi.get("fiftyTwoWeekLow")), _sayi(bilgi.get("fiftyTwoWeekHigh"))
    if not (dusuk and yuksek and son_fiyat) or yuksek <= dusuk:
        return None
    return {"dusuk": ondalik(dusuk, 2), "yuksek": ondalik(yuksek, 2),
            "konum": round(min(max((son_fiyat - dusuk) / (yuksek - dusuk), 0), 1) * 100, 1)}


def _analist(bilgi, son_fiyat):
    hedef = _sayi(bilgi.get("targetMeanPrice"))
    adet = bilgi.get("numberOfAnalystOpinions")
    if not hedef or not adet:
        return None
    oneri, ton = ONERILER.get(bilgi.get("recommendationKey"), (None, "notr"))
    return {
        "hedef": ondalik(hedef, 2),
        "dusuk": ondalik(_sayi(bilgi.get("targetLowPrice")), 2),
        "yuksek": ondalik(_sayi(bilgi.get("targetHighPrice")), 2),
        "potansiyel": hedef / son_fiyat - 1 if son_fiyat else None,
        "oneri": oneri, "ton": ton, "adet": adet,
    }


def _sonraki_bilanco(takvim, birim):
    if not isinstance(takvim, dict):
        return None
    tarihler = [t for t in (takvim.get("Earnings Date") or []) if isinstance(t, date) and t >= date.today()]
    if not tarihler:
        return None
    hbk = _sayi(takvim.get("Earnings Average"))
    gelir = _sayi(takvim.get("Revenue Average"))
    return {"tarih": uzun_tarih(tarihler[0].isoformat()),
            "hbk": _hbk(hbk, birim) if hbk is not None else None,
            "gelir": para(gelir, birim) if gelir else None}


def _hisse(bilgi, gelir, bilanco, nakit, takvim):
    birim = bilgi.get("financialCurrency") or "USD"           # bilanço kalemlerinin para birimi
    pb = bilgi.get("currency") or "USD"                       # fiyatın para birimi
    son_fiyat = _sayi(bilgi.get("currentPrice") or bilgi.get("regularMarketPrice"))
    temettu = _sayi(bilgi.get("dividendYield"))
    temettu = temettu / 100 if temettu is not None else None  # Yahoo yüzde olarak verir: 0,32 = %0,32
    borc_ozk = _sayi(bilgi.get("debtToEquity"))
    son_ceyrek = sorted(bilanco.columns)[-1] if bilanco is not None and not bilanco.empty else None
    nakit_ = _sayi(bilgi.get("totalCash"))
    borc = _sayi(bilgi.get("totalDebt"))

    pe = _sayi(bilgi.get("trailingPE"))
    # Bilanço başka para birimindeyse Yahoo'nun firma değeri, PD/DD ve fiyat/satış
    # oranları iki para birimini karıştırıyor: gösterilmez
    tek_para = birim == pb
    ozet = [k for k in (
        {"etiket": "Piyasa değeri", "deger": para(_sayi(bilgi.get("marketCap")), pb)},
        {"etiket": "F/K", "deger": _kat(pe) or ("Zararda" if (_sayi(bilgi.get("trailingEps")) or 0) < 0 else None),
         "alt": "son 12 aylık kara göre"},
        {"etiket": "Net kar marjı", "deger": _oran(bilgi.get("profitMargins")), "alt": "son 12 ay"},
        {"etiket": "Temettü verimi", "deger": f"%{ondalik(temettu * 100, 2)}" if temettu else "Dağıtmıyor",
         "alt": "yıllık"},
    ) if k["deger"] not in (None, "—")]

    sekmeler = [
        {"ad": "Değerleme", "satirlar": [
            _satir("Piyasa değeri", para(_sayi(bilgi.get("marketCap")), pb), "Bütün hisselerin bugünkü fiyatla toplam değeri"),
            _satir("Firma değeri", para(_sayi(bilgi.get("enterpriseValue")), pb)
                   if tek_para and _sayi(bilgi.get("enterpriseValue")) else None,
                   "Piyasa değerine borç eklenip nakit çıkarılmış hali"),
            _satir("F/K (son 12 ay)", _kat(pe), "Fiyat, hisse başına yıllık karın kaç katı"),
            _satir("F/K (gelecek 12 ay)", _kat(bilgi.get("forwardPE")), "Analistlerin beklediği kara göre"),
            _satir("PD/DD", _kat(bilgi.get("priceToBook")) if tek_para else None,
                   "Piyasa değeri, şirketin defterdeki özkaynağının kaç katı"),
            _satir("Fiyat/Satış", _kat(bilgi.get("priceToSalesTrailing12Months")) if tek_para else None,
                   "Piyasa değeri, yıllık gelirin kaç katı"),
            _satir("Temettü verimi", f"%{ondalik(temettu * 100, 2)}" if temettu else None, "Yıllık temettünün hisse fiyatına oranı"),
            _satir("Temettü dağıtım oranı", _oran(bilgi.get("payoutRatio")) if _sayi(bilgi.get("payoutRatio")) else None,
                   "Karın ne kadarı ortaklara dağıtılıyor"),
        ]},
        {"ad": "Karlılık", "satirlar": [
            _satir("Gelir (son 12 ay)", para(_sayi(bilgi.get("totalRevenue")), birim) if _sayi(bilgi.get("totalRevenue")) else None,
                   "Satışlardan elde edilen toplam gelir"),
            _satir("Gelir büyümesi", yuzde(_sayi(bilgi.get("revenueGrowth")), basamak=1) if _sayi(bilgi.get("revenueGrowth")) is not None else None,
                   "Son çeyrek, geçen yılın aynı çeyreğine göre"),
            _satir("Kar büyümesi", yuzde(_sayi(bilgi.get("earningsGrowth")), basamak=1) if _sayi(bilgi.get("earningsGrowth")) is not None else None,
                   "Son çeyrek, geçen yılın aynı çeyreğine göre"),
            _satir("Brüt kar marjı", _oran(bilgi.get("grossMargins")), "Üretim maliyetleri düşüldükten sonra kalan pay"),
            _satir("Faaliyet kar marjı", _oran(bilgi.get("operatingMargins")), "Ana faaliyetlerden kalan pay"),
            _satir("Net kar marjı", _oran(bilgi.get("profitMargins")), "Her 100 birim gelirden kalan net kar"),
            _satir("Özkaynak karlılığı", _oran(bilgi.get("returnOnEquity")), "Ortakların sermayesine göre yıllık kar"),
            _satir("Aktif karlılığı", _oran(bilgi.get("returnOnAssets")), "Şirketin bütün varlıklarına göre yıllık kar"),
        ]},
        {"ad": "Bilanço", "satirlar": [
            _satir("Nakit ve yatırımlar", para(nakit_, birim) if nakit_ else None, "Kasadaki nakit ve kısa vadeli yatırımlar"),
            _satir("Toplam borç", para(borc, birim) if borc is not None else None, "Finansal borçlar"),
            _satir("Net borç", para(borc - nakit_, birim) if borc is not None and nakit_ is not None else None,
                   "Borçtan nakit düşülünce kalan; eksiyse şirketin net nakdi var"),
            _satir("Borç / özkaynak", ondalik(borc_ozk / 100, 2) if borc_ozk is not None else None,
                   "Her 1 birim özkaynağa düşen borç"),
            _satir("Cari oran", ondalik(_sayi(bilgi.get("currentRatio")), 2) if _sayi(bilgi.get("currentRatio")) else None,
                   "Kısa vadeli varlıklar / kısa vadeli borçlar; 1'in üstü rahat"),
            _satir("Serbest nakit akışı (12 ay)", para(_sayi(bilgi.get("freeCashflow")), birim)
                   if _sayi(bilgi.get("freeCashflow")) is not None else None, "Yatırımlardan sonra şirkette kalan nakit"),
            _satir("Toplam varlıklar", para(_kalem(bilanco, "Total Assets", son_ceyrek), birim)
                   if _kalem(bilanco, "Total Assets", son_ceyrek) else None, "Son bilanço tarihindeki"),
            _satir("Özkaynak", para(_kalem(bilanco, "Stockholders Equity", son_ceyrek), birim)
                   if _kalem(bilanco, "Stockholders Equity", son_ceyrek) is not None else None, "Varlıklardan borçlar düşülünce kalan"),
        ]},
        {"ad": "Sahiplik", "satirlar": [
            _satir("Dolaşımdaki hisse", f"{ondalik(_sayi(bilgi.get('sharesOutstanding')) / 1e6, 1)} mn"
                   if _sayi(bilgi.get("sharesOutstanding")) else None, "Şirketin toplam hisse adedi"),
            _satir("Kurumsal yatırımcılar", _oran(bilgi.get("heldPercentInstitutions")), "Fonların ve kurumların payı"),
            _satir("Şirket içindekiler", _oran(bilgi.get("heldPercentInsiders")), "Yöneticilerin ve büyük ortakların payı"),
            _satir("Açığa satış", _oran(bilgi.get("shortPercentOfFloat")), "Düşüşe oynayanların halka açık hisselere oranı"),
            _satir("Beta", ondalik(_sayi(bilgi.get("beta")), 2) if _sayi(bilgi.get("beta")) is not None else None,
                   "Piyasaya göre oynaklık; 1'in üstü daha oynak"),
            _satir("Ortalama günlük hacim", f"{ondalik(_sayi(bilgi.get('averageVolume')) / 1e6, 1)} mn hisse"
                   if _sayi(bilgi.get("averageVolume")) else None, "Son 3 ayın ortalaması"),
        ]},
    ]
    for s in sekmeler:
        s["satirlar"] = [r for r in s["satirlar"] if r]
    sekmeler = [s for s in sekmeler if s["satirlar"]]

    son_ceyrek_ozeti, ceyrekler = _ceyrekler(gelir, bilanco, nakit, birim)
    if not ozet and not sekmeler:
        return None
    return {
        "tur": "hisse",
        "ozet": ozet,
        "sekmeler": sekmeler,
        "son_ceyrek": son_ceyrek_ozeti,
        "ceyrekler": ceyrekler,
        "sonraki": _sonraki_bilanco(takvim, birim),
        "aralik": _aralik_52(bilgi, son_fiyat),
        "analist": _analist(bilgi, son_fiyat),
        "birim_notu": f"Bilanço rakamları {birim} cinsindendir." if birim != pb else None,
    }


def _fon(bilgi):
    gider = _sayi(bilgi.get("netExpenseRatio"))
    verim = _sayi(bilgi.get("yield"))
    ytd = _sayi(bilgi.get("ytdReturn"))
    satirlar = [r for r in (
        _satir("Fon büyüklüğü", para(_sayi(bilgi.get("totalAssets"))) if _sayi(bilgi.get("totalAssets")) else None,
               "Fonun yönettiği toplam varlık"),
        _satir("Yıllık gider oranı", f"%{ondalik(gider, 2)}" if gider is not None else None,
               "Fonun her yıl kestiği yönetim ücreti"),
        _satir("Temettü verimi", f"%{ondalik(verim * 100, 2)}" if verim else None, "Son 12 ayda dağıtılan"),
        _satir("Yılbaşından beri", yuzde(ytd / 100, basamak=1) if ytd is not None else None, "Fonun bu yılki getirisi"),
        _satir("3 yıllık ortalama getiri", yuzde(_sayi(bilgi.get("threeYearAverageReturn")), basamak=1)
               if _sayi(bilgi.get("threeYearAverageReturn")) is not None else None, "Yıllık ortalama"),
        _satir("5 yıllık ortalama getiri", yuzde(_sayi(bilgi.get("fiveYearAverageReturn")), basamak=1)
               if _sayi(bilgi.get("fiveYearAverageReturn")) is not None else None, "Yıllık ortalama"),
        _satir("F/K", ondalik(_sayi(bilgi.get("trailingPE")), 1) if _sayi(bilgi.get("trailingPE")) else None,
               "İçindeki şirketlerin ortalama F/K'sı"),
        _satir("Beta (3 yıl)", ondalik(_sayi(bilgi.get("beta3Year")), 2) if _sayi(bilgi.get("beta3Year")) is not None else None,
               "Piyasaya göre oynaklık"),
        _satir("Yönetici", bilgi.get("fundFamily"), "Fonu yöneten şirket"),
    ) if r]
    if not satirlar:
        return None
    ozet = [{"etiket": r["etiket"], "deger": r["deger"]} for r in satirlar[:4]]
    son_fiyat = _sayi(bilgi.get("regularMarketPrice") or bilgi.get("navPrice"))
    return {"tur": "fon", "ozet": ozet, "sekmeler": [{"ad": "Fon", "satirlar": satirlar[4:] or satirlar}],
            "son_ceyrek": None, "ceyrekler": [], "sonraki": None,
            "aralik": _aralik_52(bilgi, son_fiyat), "analist": None, "birim_notu": None}


def hazirla(bilgi, gelir=None, bilanco=None, nakit=None, takvim=None):
    """Ham Yahoo verisinden sayfaya hazır göstergeler; yeterli veri yoksa None."""
    if not bilgi:
        return None
    if bilgi.get("quoteType") == "ETF":
        return _fon(bilgi)
    return _hisse(bilgi, gelir, bilanco, nakit, takvim)


# ---------------------------------------------------------------------------
# Veri
# ---------------------------------------------------------------------------

def _veri_al(kod):
    t = yf.Ticker(kod)
    bilgi = t.info or {}
    if bilgi.get("quoteType") == "ETF":
        return bilgi, None, None, None, None

    def guvenli(al):
        try:
            return al()
        except Exception:
            return None

    return (bilgi, guvenli(lambda: t.quarterly_income_stmt), guvenli(lambda: t.quarterly_balance_sheet),
            guvenli(lambda: t.quarterly_cashflow), guvenli(lambda: t.calendar))


@sureli(ONBELLEK_SURESI)
def _temel(kod):
    sonuc = hazirla(*_veri_al(kod))
    if sonuc:
        sonuc["guncelleme"] = datetime.now(UTC).isoformat()
    return sonuc


def temel_bilgiler(ticker):
    """Şirketin rakamları; alınamazsa None. Hata önbelleğe yazılmaz, sonraki istekte yeniden denenir."""
    kod = fiyat_servisi.yahoo_kodu(ticker)
    if not kod:
        return None
    try:
        return _temel(kod)
    except Exception:
        return None
