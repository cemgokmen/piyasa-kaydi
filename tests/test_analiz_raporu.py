"""Teknik/temel analiz motorları ve /analiz sayfaları (sahte fiyat ve tablolarla, internetsiz)."""

import numpy as np
import pandas as pd
import pytest

from piyasa.analiz import rapor, tarama, teknik, temel_analiz
from piyasa.analiz.ajan import kanit as ajan_kanit


def sahte_ohlcv(gun=900, egim=0.0006, tohum=3, baslangic=100.0):
    rng = np.random.default_rng(tohum)
    getiri = egim + rng.normal(0, 0.015, gun)
    kapanis = baslangic * np.exp(np.cumsum(getiri))
    acilis = kapanis * (1 + rng.normal(0, 0.004, gun))
    yuksek = np.maximum(acilis, kapanis) * (1 + np.abs(rng.normal(0, 0.006, gun)))
    dusuk = np.minimum(acilis, kapanis) * (1 - np.abs(rng.normal(0, 0.006, gun)))
    hacim = rng.integers(1_000_000, 3_000_000, gun).astype(float)
    tarih = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=gun)
    return pd.DataFrame({"Open": acilis, "High": yuksek, "Low": dusuk, "Close": kapanis, "Volume": hacim}, index=tarih)


# ---------------------------------------------------------------------------
# Teknik
# ---------------------------------------------------------------------------

def test_gostergeler_bilinen_degerler():
    s = pd.Series(np.arange(1, 31, dtype=float))
    assert teknik.sma(s, 5).iloc[-1] == pytest.approx(28.0)
    # Sürekli yükselen seride RSI 100
    assert teknik.rsi(s, 14).iloc[-1] == pytest.approx(100.0)
    dusen = pd.Series(np.arange(30, 0, -1, dtype=float))
    assert teknik.rsi(dusen, 14).iloc[-1] == pytest.approx(0.0)


def test_yukselen_hisse_olumlu_dusen_olumsuz_puan():
    endeks = sahte_ohlcv(egim=0.0, tohum=9)["Close"]
    yukari = teknik.analiz(sahte_ohlcv(egim=0.002, tohum=1), endeks)
    asagi = teknik.analiz(sahte_ohlcv(egim=-0.002, tohum=1), endeks)
    for v in teknik.VADELER:
        assert 0 <= yukari["puanlar"][v] <= 100
        assert yukari["puanlar"][v] > asagi["puanlar"][v]
    assert yukari["puanlar"]["uzun"] >= 60 and asagi["puanlar"]["uzun"] <= 40
    assert yukari["bilesen"]["trend"] > 0 > asagi["bilesen"]["trend"]
    assert yukari["evre"]["evre"] == 2 and asagi["evre"]["evre"] == 4


def test_okuma_ve_senaryo_turkce_bicimde():
    df = sahte_ohlcv()
    t = teknik.analiz(df, sahte_ohlcv(egim=0, tohum=5)["Close"])
    from piyasa.analiz.destek_direnc import bolgeleri_hesapla
    bolgeler = bolgeleri_hesapla(df.iloc[-756:])["bolgeler"]
    maddeler = teknik.okuma(t, bolgeler)
    basliklar = {m["baslik"].split(":")[0] for m in maddeler}
    assert {"Ana trend", "Momentum", "Tepe-dip yapısı"} <= basliklar
    metin = " ".join(m["metin"] for m in maddeler)
    # Ondalık ayırıcı virgül: "12.34" gibi İngilizce yazım kalmamalı
    import re
    assert not re.search(r"\d\.\d{2}\b", metin), metin
    s = teknik.senaryolar(t, bolgeler)
    assert s["asagi_esik"] < t["gosterge"]["close"] < s["yukari_esik"]


def test_gecmis_isabet_seyreltilmis_gruplar():
    t = teknik.analiz(sahte_ohlcv(gun=1200))
    i = t["isabet"]["orta"]
    assert i["gun"] == 60 and [g["ad"][:4] for g in i["gruplar"]] == ["Olum", "Nötr", "Olum"]
    assert sum(g["n"] for g in i["gruplar"]) == i["n"]


def test_kisa_veri_hata_verir():
    with pytest.raises(ValueError):
        teknik.analiz(sahte_ohlcv(gun=30))


# ---------------------------------------------------------------------------
# Temel
# ---------------------------------------------------------------------------

def sahte_tablolar(yillar=(2022, 2023, 2024, 2025), gelir=(100, 120, 150, 180), net=(10, 13, 17, 22), para="USD"):
    sutun = [pd.Timestamp(f"{y}-12-31") for y in yillar]

    def tablo(satirlar):
        return pd.DataFrame({s: [v[i] for v in satirlar.values()] for i, s in enumerate(sutun)}, index=list(satirlar))

    g = tablo({"Total Revenue": [x * 1e9 for x in gelir], "Net Income": [x * 1e9 for x in net],
               "Gross Profit": [x * 0.4e9 for x in gelir], "Operating Income": [x * 0.15e9 for x in gelir],
               "EBITDA": [x * 0.2e9 for x in gelir], "Interest Expense": [1e9] * 4,
               "Pretax Income": [x * 1.25e9 for x in net], "Tax Provision": [x * 0.25e9 for x in net]})
    b = tablo({"Total Assets": [200e9, 220e9, 240e9, 260e9], "Stockholders Equity": [100e9, 110e9, 125e9, 140e9],
               "Total Debt": [40e9] * 4, "Cash And Cash Equivalents": [20e9] * 4,
               "Current Assets": [80e9, 85e9, 95e9, 105e9], "Current Liabilities": [50e9] * 4,
               "Long Term Debt": [30e9, 29e9, 28e9, 27e9], "Retained Earnings": [50e9, 60e9, 72e9, 85e9],
               "Working Capital": [30e9, 35e9, 45e9, 55e9], "Total Liabilities Net Minority Interest": [100e9, 110e9, 115e9, 120e9],
               "Ordinary Shares Number": [1e9] * 4})
    n = tablo({"Operating Cash Flow": [x * 1.2e9 for x in net], "Free Cash Flow": [x * 0.8e9 for x in net],
               "Capital Expenditure": [-5e9] * 4})
    bilgi = {"quoteType": "EQUITY", "currency": para, "financialCurrency": para, "marketCap": 300e9,
             "sector": "Industrials", "dividendYield": 2.0}
    return {"bilgi": bilgi, "gelir": g, "bilanco": b, "nakit": n, "ceyrek_bilanco": None, "kur": 1.0}


def test_saglam_sirket_yuksek_temel_puan():
    s = temel_analiz.degerlendir(**sahte_tablolar())
    assert s["puan"] > 60
    assert s["piotroski"]["puan"] >= 7
    assert s["altman"]["bolge"] == "guvenli"
    assert s["oranlar"]["fk"] == pytest.approx(300 / 22)
    assert s["oranlar"]["gelir_cagr"] == pytest.approx((180 / 100) ** (1 / 3) - 1)
    assert not s["bayraklar"] and s["guclu"]
    assert {m["baslik"] for m in s["okuma"]} == set(temel_analiz.BILESEN_ADLARI.values())


def test_tl_raporlayanda_buyume_enflasyondan_arindirilir():
    veri = sahte_tablolar(para="TRY")
    enf = {2023: 0.65, 2024: 0.44, 2025: 0.31}
    s = temel_analiz.degerlendir(enflasyon=enf, **veri)
    assert s["tms29"] and s["reel"]
    # TMS 29: son adım reel, önceki adımlar bir sonraki yılın enflasyonuyla arındırılır
    beklenen = ((120 / 100 / 1.44) * (150 / 120 / 1.31) * (180 / 150)) ** (1 / 3) - 1
    assert s["oranlar"]["gelir_cagr_reel"] == pytest.approx(beklenen)
    assert s["oranlar"]["roe_reel"] == s["oranlar"]["roe"]          # TMS 29'da özkaynak karlılığı zaten reel


def test_bankada_tms29_yok_ve_borc_oranlari_atlanir():
    veri = sahte_tablolar(para="TRY")
    veri["bilgi"]["sector"] = "Financial Services"
    s = temel_analiz.degerlendir(enflasyon={2023: 0.65, 2024: 0.44, 2025: 0.31}, **veri)
    assert s["finans"] and not s["tms29"] and s["altman"] is None
    assert s["oranlar"]["roe_reel"] < s["oranlar"]["roe"]
    assert s["oranlar"]["fd_favok"] is None


def test_yabanci_para_ozet_rakamlari_fiyat_para_biriminde():
    # TAVHL gibi: tablolar EUR, Yahoo özetindeki son 12 ay rakamları TL
    veri = sahte_tablolar(para="EUR")
    veri["bilgi"].update(currency="TRY", marketCap=300e9 * 50, totalRevenue=180e9 * 50, netIncomeToCommon=22e9 * 50)
    veri["kur"] = 50.0
    s = temel_analiz.degerlendir(**veri)
    assert s["oranlar"]["fk"] == pytest.approx(300 / 22)
    assert s["oranlar"]["roe"] < 1


def test_ters_ina_buyumeyi_bulur():
    sonuc = temel_analiz.ters_ina(100.0, 5.0, 0.0, "USD")
    assert sonuc and -0.05 < sonuc["buyume"] < 0.15
    assert temel_analiz.ters_ina(100.0, 5.0, 0.0, "TRY") is None


def test_yillik_enflasyon():
    aylik = {"2023-12": 100.0, "2024-12": 144.0, "2025-06": 160.0, "2024-06": 120.0}
    assert temel_analiz.yillik_enflasyon(aylik)[2024] == pytest.approx(0.44)


# ---------------------------------------------------------------------------
# Rapor ve sayfalar
# ---------------------------------------------------------------------------

def test_risk_plani_stop_girisin_altinda():
    df = sahte_ohlcv()
    t = teknik.analiz(df)
    from piyasa.analiz.destek_direnc import bolgeleri_hesapla
    plan = rapor.risk_plani(t, bolgeleri_hesapla(df.iloc[-756:])["bolgeler"])
    assert all(s["fiyat"] < plan["giris"] for s in plan["stoplar"])
    assert plan["onerilen"] in {s["kod"] for s in plan["stoplar"]}
    assert all(h["fiyat"] > plan["giris"] for h in plan["hedefler"])


@pytest.fixture()
def sahte_analiz(monkeypatch):
    fiyatlar = {"THYAO.IS": sahte_ohlcv(egim=0.001), "XU100.IS": sahte_ohlcv(egim=0.0, tohum=7),
                "AAPL": sahte_ohlcv(egim=0.0008, tohum=4), "SPY": sahte_ohlcv(egim=0.0003, tohum=8)}
    monkeypatch.setattr(rapor, "gecmis", lambda yahoo, yil=5: fiyatlar.get(yahoo))
    monkeypatch.setattr(rapor, "temel_ham", lambda yahoo: sahte_tablolar(para="TRY" if yahoo.endswith(".IS") else "USD"))
    monkeypatch.setattr(rapor, "_tr_enflasyon", lambda: {2023: 0.65, 2024: 0.44, 2025: 0.31})
    monkeypatch.setattr(rapor, "dolar_kuru", lambda: 42.0)
    satir = tarama.hisse_ozeti(fiyatlar["THYAO.IS"], fiyatlar["XU100.IS"]["Close"])
    veri = {"teknik": {"zaman": 1e12, "hisseler": {"THYAO": satir}, "genislik": tarama.genislik([satir]),
                       "rejim": tarama.rejim(fiyatlar["XU100.IS"])},
            "temel": {"THYAO": {"puan": 64.0, "bilesen": {"kalite": 0.4, "degerleme": 0.5}, "fk": 7.0, "roe": 0.2}},
            "adlar": {"THYAO": "TÜRK HAVA YOLLARI A.O."}, "sektorler": {"THYAO": "ULAŞTIRMA VE DEPOLAMA"},
            "medyan": {"genel": {"fk": 9.0, "pddd": 1.0, "fd_favok": 7.0, "n": 99}}}
    monkeypatch.setattr(tarama, "_oku", lambda: veri)
    monkeypatch.setattr(tarama, "teknik_gerekli", lambda v, simdi=None: False)
    donem = {"bas": "2025-11-04", "bit": "2026-11-03", "tez": {"getiri": 0.04}, "bugun": {"getiri": 0.08},
             "endeks": 0.01, "al_tut": -0.08, "faiz": 0.37}
    monkeypatch.setattr(ajan_kanit, "oku", lambda: {"hisse": 99, "bas": "2020-11-04", "bit": "2026-11-03", "deney": [donem],
                                                    "kurallar": {"altay.stokastik": {"al": {"kanit": "sans", "ortalama": 0.004, "sinyal": 10},
                                                                                     "sat": {"kanit": "zayif", "ortalama": 0.002, "sinyal": 9}}}})
    return fiyatlar


def test_analiz_genel_sayfasi(istemci, sahte_analiz):
    cevap = istemci.get("/analiz")
    html = cevap.get_data(as_text=True)
    assert cevap.status_code == 200 and "noindex" in cevap.headers["X-Robots-Tag"]
    assert "BIST 100 hisseleri" in html and "Güçlü aday" in html and "THYAO" in html and "Para yönetimi kuralları" in html
    assert "Kaynak kuralları tutuyor mu" in html and "Tezin deneyi" in html and "Altay 1997" in html and "Dow teyidi" in html
    assert istemci.get("/analiz?kod=asels").headers["Location"].endswith("/analiz/ASELS")


def test_analiz_hisse_sayfasi(istemci, sahte_analiz):
    cevap = istemci.get("/analiz/thyao")
    html = cevap.get_data(as_text=True)
    assert cevap.status_code == 200
    for parca in ("Genel görünüm", "Grafik okuması", "Pozisyon ve risk", "Temel analiz", "Piotroski",
                  "geçmişte işe yaradı", 'id="grafik-verisi"', "enflasyon muhasebesi", "Kaynak kuralları bu hissede",
                  "trend takibi işe yarıyor mu"):
        assert parca in html, parca
    abd = istemci.get("/analiz/AAPL").get_data(as_text=True)
    assert "Dolar kuru" in abd and "S&amp;P 500" in abd


def test_analiz_bilinmeyen_kod_404(istemci, sahte_analiz):
    assert istemci.get("/analiz/YOKBOYLE").status_code == 404
    assert istemci.get("/analiz/<script>").status_code == 404
    assert "Disallow: /analiz" in istemci.get("/robots.txt").get_data(as_text=True)


def test_bolunme_duzelt_islenmemis_bedelsizi_siler_gercek_hareketi_korur():
    from piyasa.analiz.teknik.veri import bist_mi, bolunme_duzelt
    t = pd.date_range("2024-01-01", periods=5, freq="B")
    d = pd.DataFrame({"Open": [100.0, 110, 11, 12, 13], "High": [100.0, 110, 11, 12, 13], "Low": [100.0, 110, 11, 12, 13],
                      "Close": [100.0, 110, 11, 12, 13], "Volume": [10.0, 10, 100, 100, 100]}, index=t)
    y = bolunme_duzelt(d)
    assert y["Close"].iloc[-1] == 13 and y["Close"].iloc[2] == 11           # son fiyatlar değişmez
    assert y["Close"].iloc[0] == pytest.approx(10) and y["Close"].iloc[1] == pytest.approx(11)
    assert y["Volume"].iloc[0] == pytest.approx(100)
    assert (y["Close"].pct_change().abs().dropna() <= 0.15).all()
    # %10'luk tavan hareketine dokunulmaz, tablo aynen döner
    assert bolunme_duzelt(d.iloc[:2]) is not None and bolunme_duzelt(d.iloc[:2])["Close"].iloc[0] == 100
    assert bist_mi("GARAN.IS") and not bist_mi("AAPL")
