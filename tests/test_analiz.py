"""Getiri hesabı, istatistik ve sektör eşlemesi."""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from piyasa.analiz import istatistik
from piyasa.analiz.getiri import FiyatDeposu, getiri_hesapla
from piyasa.analiz.sektorler import KOMITE_SEKTORLERI, sic_sektoru


class SahteBaglanti:
    """FiyatDeposu'nun okuyacağı tabloyu doğrudan veren küçük sahte."""

    def __init__(self, tablo):
        self.tablo = tablo


@pytest.fixture()
def depo(monkeypatch):
    tarihler = pd.bdate_range("2025-01-01", "2025-12-31")
    satirlar = []
    for i, t in enumerate(tarihler):
        satirlar.append(("SPY", t.strftime("%Y-%m-%d"), 100 + i * 0.1))   # endeks yavaş yükselir
        satirlar.append(("ABC", t.strftime("%Y-%m-%d"), 50 + i * 0.1))    # hisse daha hızlı
    tablo = pd.DataFrame(satirlar, columns=["ticker", "tarih", "kapanis"])
    monkeypatch.setattr(pd, "read_sql_query", lambda sorgu, conn: tablo)
    return FiyatDeposu(None)


def test_hafta_sonu_islemi_sonraki_is_gunune_kayar(depo):
    # 2025-03-01 Cumartesi: giriş fiyatı 3 Mart Pazartesi kapanışı olmalı
    assert depo.kapanis("ABC", date(2025, 3, 1)) == depo.kapanis("ABC", date(2025, 3, 3))
    # 7 günden uzak boşlukta fiyat yok sayılır
    assert depo.kapanis("ABC", date(2026, 6, 1)) is None


def test_getiri_ve_endeks(depo):
    hisse, endeks = getiri_hesapla(depo, "ABC", date(2025, 3, 1), 30)
    assert hisse > endeks > 0          # hisse endeksten hızlı yükseliyor
    assert getiri_hesapla(depo, "ABC", date(2025, 12, 20), 30) is None   # süre dolmadı
    assert getiri_hesapla(depo, "YOK", date(2025, 3, 1), 30) is None


def test_istatistik_ozet():
    rng = np.random.default_rng(1)
    s = istatistik.ozet(rng.normal(0.05, 0.02, 200))
    assert s["n"] == 200 and s["alt"] < s["ortalama"] < s["ust"]
    assert s["karar"]["kod"] == "iyi"
    assert istatistik.ozet([0.1, -0.1])["karar"]["kod"] == "yetersiz"


def test_holm_coklu_karsilastirma():
    # Biri p=0,02, dokuzu p=0,5: tek başına anlamlı, düzeltmeden sonra değil
    ozetler = [{"n": 50, "p": 0.02, "ortalama": 0.03}] + [{"n": 50, "p": 0.5, "ortalama": 0.0}] * 9
    ozetler = [dict(o) for o in ozetler]
    istatistik.holm(ozetler)
    assert ozetler[0]["p_duzeltilmis"] == pytest.approx(0.2)
    assert ozetler[0]["karar"]["kod"] == "sans"


@pytest.mark.parametrize("sic, sektor", [
    (3812, "Savunma ve havacılık"),   # savunma elektroniği
    (2834, "Sağlık"),                 # ilaç
    (1311, "Enerji"),                 # petrol ve gaz üretimi
    (6022, "Finans"),                 # banka
    (6798, "Gayrimenkul"),            # gayrimenkul yatırım ortaklığı
    (3674, "Teknoloji"),              # yarı iletken
    (None, None),
])
def test_sic_sektoru(sic, sektor):
    assert sic_sektoru(sic) == sektor


def test_komite_sektorleri_tanimli():
    gecerli = {"Savunma ve havacılık", "Sağlık", "Enerji", "Kamu hizmetleri", "Tarım ve gıda",
               "Otomotiv", "Ulaştırma", "İletişim ve medya", "Teknoloji", "Gayrimenkul", "Finans",
               "Madencilik ve malzeme", "İnşaat", "Perakende", "Eğitim", "Sanayi"}
    for sektorler in KOMITE_SEKTORLERI.values():
        assert set(sektorler) <= gecerli


def test_portfoy_satilan_hisse_cikar(istemci):
    """Jane 12 kez NVDA aldı, hiç satmadı; AAPL'yi yalnızca sattı."""
    from piyasa.analiz import portfoy

    p = portfoy.hesapla("jane-senator")
    hisseler = {x["ticker"]: x for x in p["pozisyonlar"]}
    assert set(hisseler) == {"NVDA"}
    nvda = hisseler["NVDA"]
    assert nvda["alim"] >= 12
    assert nvda["deger"] > nvda["maliyet"]        # NVDA test verisinde sürekli yükseliyor
    assert nvda["pay"] == 1
    assert portfoy.hesapla("yok-boyle") is None


def test_portfoy_sayfada(istemci):
    html = istemci.get("/kisi/jane-senator").get_data(as_text=True)
    assert "Tahmini portföyü" in html and 'class="pasta"' in html and "%100,0" in html
