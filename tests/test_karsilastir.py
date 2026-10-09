"""Yatırım karşılaştırma: hesaplar ve sayfa."""

import pytest

from piyasa.analiz import karsilastirma as k
from piyasa.web.karsilastir_rotalari import ay_metni, para_yaz, sayi_eki


def _fiyat(seri):
    return {f"2020-{i + 1:02d}": v for i, v in enumerate(seri)}


@pytest.fixture()
def sabit_veri(monkeypatch):
    """12 ay: kur sabit 10 TL; 'A' iki katına çıkıyor, 'B' yarıya iniyor; enflasyon %50."""
    seriler = {
        "TRY=X": _fiyat([10.0] * 12),
        "A": _fiyat([100 + 100 * i / 11 for i in range(12)]),
        "B": _fiyat([100, 120, 80, 60, 70, 50, 55, 60, 50, 45, 50, 50]),
    }
    monkeypatch.setattr(k, "aylik", lambda y: seriler.get(y, {}))
    monkeypatch.setattr(k, "enflasyon", lambda ulke: _fiyat([100 + 50 * i / 11 for i in range(12)]))


def _varlik(ad, yahoo, para="USD"):
    return {"anahtar": ad, "ad": ad, "yahoo": yahoo, "para": para, "grup": "Test", "renk": "#000"}


def test_tek_seferlik_ve_enflasyon(sabit_veri, monkeypatch):
    monkeypatch.setattr(k, "aylar", lambda bas, son: [f"2020-{i:02d}" for i in range(1, 13)])
    r = k.hesapla([_varlik("A", "A"), _varlik("B", "B"), _varlik("Dolar", None)], "2020-01", 1_000, "TRY")
    a, dolar, b = r["varliklar"]
    assert (a["ad"], dolar["ad"], b["ad"]) == ("A", "Dolar", "B")
    assert a["son"] == pytest.approx(2_000) and a["kat"] == pytest.approx(2)
    assert b["son"] == pytest.approx(500)
    # En büyük düşüş: 120'den 45'e
    assert b["dusus"] == pytest.approx(45 / 120 - 1)
    # Enflasyon %50: alım gücünü korumak için 1.500 TL gerekir; A'nın reel getirisi 2000/1500 − 1
    assert r["enflasyon"][-1] == pytest.approx(1_500)
    assert a["reel"] == pytest.approx(2_000 / 1_500 - 1)
    assert dolar["son"] == pytest.approx(1_000) and dolar["reel"] == pytest.approx(1_000 / 1_500 - 1)


def test_her_ay_duzenli_yatirim(sabit_veri, monkeypatch):
    monkeypatch.setattr(k, "aylar", lambda bas, son: [f"2020-{i:02d}" for i in range(1, 13)])
    r = k.hesapla([_varlik("Dolar", None)], "2020-01", 100, "TRY", "aylik")
    d = r["varliklar"][0]
    assert d["yatirilan"] == pytest.approx(1_200) and d["son"] == pytest.approx(1_200)


def test_veri_olmayan_varlik_ayrica_belirtilir(sabit_veri, monkeypatch):
    monkeypatch.setattr(k, "aylar", lambda bas, son: [f"2020-{i:02d}" for i in range(1, 13)])
    r = k.hesapla([_varlik("A", "A"), _varlik("Yok", "YOK")], "2020-01", 1_000, "USD")
    assert [v["ad"] for v in r["varliklar"]] == ["A"] and r["eksik"][0]["ad"] == "Yok"


def test_ic_getiri():
    # Her ay 100, 12 ay; aylık %1 getiriyle son değer → yıllık ≈ %12,68
    son = sum(100 * 1.01 ** (11 - i) for i in range(12))
    assert k._ic_getiri([100.0] * 12, son) == pytest.approx(1.01 ** 12 - 1, rel=1e-4)


def test_turkce_ekler_ve_tutar():
    assert ay_metni("2016-10", "de") == "Ekim 2016'da"
    assert ay_metni("2012-03", "den") == "Mart 2012'den"
    assert ay_metni("2013-01", "de") == "Ocak 2013'te"
    assert ay_metni("2026-09", "e") == "Eylül 2026'ya"
    assert sayi_eki(2040, "den") == "tan"
    assert para_yaz(12_345.6, "TRY") == "12.346 ₺" and para_yaz(18_720_000, "TRY") == "18,72 milyon ₺"
    assert para_yaz(1_000, "USD") == "$1.000"


def test_karsilastir_sayfasi(istemci):
    html = istemci.get("/yatirim-karsilastir").get_data(as_text=True)
    assert "Yatırım karşılaştırma" in html and 'id="kars-veri"' in html
    # Sahte veride en hızlı büyüyen Bitcoin
    assert "ile <b" in html and "Bitcoin</b> alsaydınız" in html
    assert "Enflasyon" in html


def test_karsilastir_secimleri_ve_hatali_girdi(istemci):
    from html import unescape
    html = unescape(istemci.get("/yatirim-karsilastir?para=USD&tutar=1.000&tur=aylik&bas=2015-01&v=altin,sp500&ek=THYAO")
                    .get_data(as_text=True))
    assert "Ocak 2015'ten bu yana her ay" in html and "$1.000" in html and 'href="/bist/THYAO"' in html
    # Geçersiz tarih ve tutar varsayılana döner, sayfa bozulmaz
    assert istemci.get("/yatirim-karsilastir?bas=1990-01&tutar=abc&para=XYZ&ek=<script>").status_code == 200
    assert "en az bir yatırım" in istemci.get("/yatirim-karsilastir?v=").get_data(as_text=True)


def test_ana_sayfada_karsilastirma_tanitimi(istemci):
    html = istemci.get("/").get_data(as_text=True)
    assert "10 yıl önce 10.000 TL yatırsaydınız?" in html
