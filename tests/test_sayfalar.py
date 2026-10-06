"""Sayfalar, bağlantılar ve fiyat uç noktası (tarayıcısız, hızlı)."""

import re
from collections import deque
from urllib.parse import urljoin, urlparse

import pytest

SAYFALAR = [
    "/",
    "/islemler",
    "/islemler?kaynak=siyasetci",
    "/islemler?kaynak=yonetici&islem=buy&donem=90&sira=tutar",
    "/islemler?sira=gecikme&islem=sell",
    "/islemler?q=nvda&donem=365",
    "/islemler?sayfa=2",
    "/siyasetciler",
    "/siyasetciler?parti=D",
    "/hisse/NVDA",
    "/hisse/nvda",
    "/hisse/ORNK",
    "/kisi/jane-senator",
    "/kisi/yonetici-1",
    "/fonlar",
    "/fon/ornek-fon",
    "/hakkinda",
    "/emtialar",
    "/emtia/altin",
    "/emtia/petrol",
    "/emtia/dogalgaz",
    "/emtia/brent",
    "/emtia/bugday",
]


@pytest.mark.parametrize("adres", SAYFALAR)
def test_sayfa_acilir(istemci, adres):
    cevap = istemci.get(adres)
    assert cevap.status_code == 200
    assert b"<h1" in cevap.data


@pytest.mark.parametrize("adres", ["/yok", "/hisse/YOKBOYLE", "/kisi/yok", "/fon/yok", "/emtia/yok"])
def test_olmayan_sayfa_404(istemci, adres):
    cevap = istemci.get(adres)
    assert cevap.status_code == 404
    assert "bulunamadı".encode() in cevap.data


def test_gecersiz_parametreler_varsayilana_duser(istemci):
    cevap = istemci.get("/islemler?sayfa=abc&donem=x&sira=y&kaynak=z&islem=q")
    assert cevap.status_code == 200


def test_eski_ana_sayfa_baglantisi_listeye_yonlenir(istemci):
    cevap = istemci.get("/?q=nvda")
    assert cevap.status_code == 302
    assert "/islemler" in cevap.headers["Location"]


def test_supheli_kayit_hicbir_yerde_gorunmez(istemci):
    for adres in ("/", "/islemler?donem=365", "/islemler?q=hata&donem=365"):
        assert b"Hatali Kayit" not in istemci.get(adres).data
    assert istemci.get("/kisi/hatali-kayit").status_code == 404


def test_yuklu_alim_one_cikar(istemci):
    for adres in ("/", "/siyasetciler"):
        html = istemci.get(adres).get_data(as_text=True)
        assert 'class="hisse-kart"' in html
        assert "NVDA" in html


def test_gec_bildirim_isaretlenir(istemci):
    html = istemci.get("/kisi/bob-rep").get_data(as_text=True)
    assert "gün geç" in html


def test_sayfalama(istemci):
    birinci = istemci.get("/islemler?kaynak=yonetici").get_data(as_text=True)
    assert "Sayfa 1 / 2" in birinci
    ikinci = istemci.get("/islemler?kaynak=yonetici&sayfa=2").get_data(as_text=True)
    assert "Sayfa 2 / 2" in ikinci


def test_fiyat_api(istemci):
    veri = istemci.get("/api/fiyat/NVDA").get_json()
    assert veri["fiyat"] > 0
    assert [d["anahtar"] for d in veri["degisimler"]] == ["1g", "1h", "1a", "1y", "5y", "10y"]
    assert all(d["oran"] is not None for d in veri["degisimler"])
    assert set(veri["seriler"]) == {"1a", "1y", "5y", "10y"}


def test_fiyat_api_bulunamayan(istemci):
    cevap = istemci.get("/api/fiyat/YOK")
    assert cevap.status_code == 404
    assert "hata" in cevap.get_json()


def test_tum_ic_baglantilar_calisir(istemci):
    """Sitedeki her iç bağlantıyı gezer; hiçbiri 404 ya da 500 vermemeli."""
    kuyruk = deque(["/", "/siyasetciler", "/fonlar", "/hakkinda", "/islemler?donem=365", "/emtialar"])
    gorulen = set(kuyruk)
    kirik = []

    while kuyruk:
        adres = kuyruk.popleft()
        cevap = istemci.get(adres)
        # Fiyatı olmayan hisse için API'nin açıklamalı 404 dönmesi beklenen durum
        fiyatsiz = adres.startswith("/api/fiyat/") and cevap.status_code == 404 \
            and "hata" in (cevap.get_json() or {})
        if cevap.status_code not in (200, 302) and not fiyatsiz:
            kirik.append((cevap.status_code, adres))
            continue
        if not cevap.content_type.startswith("text/html"):
            continue
        html = cevap.get_data(as_text=True)
        for hedef in re.findall(r'(?:href|src|data-href|data-fiyat-url)="([^"#]+)"', html):
            hedef = hedef.replace("&amp;", "&")
            if hedef.startswith(("http", "mailto:", "data:")):
                continue
            tam = urlparse(urljoin(adres, hedef))
            yol = tam.path + (f"?{tam.query}" if tam.query else "")
            if yol not in gorulen:
                gorulen.add(yol)
                kuyruk.append(yol)

    assert not kirik, kirik
    assert len(gorulen) > 30


def test_emtia_genel_bakis(istemci):
    html = istemci.get("/emtialar").get_data(as_text=True)
    for metin in ("Altın", "Ham petrol (WTI)", "Gram altın", "Fed politika faizi",
                  "Büyük fonlar ne yapıyor?", "OPEC"):
        assert metin in html, metin
    assert "$/ons" in html and "sent/buşel" in html


def test_emtia_sayfasi_arz_talep(istemci):
    html = istemci.get("/emtia/petrol").get_data(as_text=True)
    assert 'id="cot-verisi"' in html          # fon konumu grafiği
    assert 'id="eia-verisi"' in html          # stok grafiği
    assert "ABD ticari ham petrol stokları" in html
    assert "Örnek haber" in html
    # Altında stok yok, gram altın var
    altin = istemci.get("/emtia/altin").get_data(as_text=True)
    assert 'id="eia-verisi"' not in altin and "Gram altın" in altin


def test_emtia_fiyat_api(istemci):
    veri = istemci.get("/api/emtia/altin/fiyat").get_json()
    assert veri["kod"] == "GC=F" and veri["hacim"]["son"] > 0
    assert istemci.get("/api/emtia/yok/fiyat").status_code == 404
