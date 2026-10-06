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
    "/emtia/brent",
    "/emtia/bakir",
    "/siyasetciler/performans",
    "/siyasetciler/cikar-catismasi",
    "/sinyaller",
    "/gunluk-ozet",
    "/yurutme/donald-j-trump",
    "/yurutme/jd-vance",
]


@pytest.mark.parametrize("adres", SAYFALAR)
def test_sayfa_acilir(istemci, adres):
    cevap = istemci.get(adres)
    assert cevap.status_code == 200
    assert b"<h1" in cevap.data


@pytest.mark.parametrize("adres", ["/yok", "/hisse/YOKBOYLE", "/kisi/yok", "/fon/yok", "/emtia/yok",
                                   "/emtia/petrol", "/emtia/dogalgaz", "/emtia/bugday", "/emtia/misir",
                                   "/gunluk-ozet/2000-01-01", "/gunluk-ozet/yok",
                                   "/yurutme/yok"])
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
    for metin in ("Altın", "Gümüş", "Platin", "Bakır", "Brent petrol", "Gram altın",
                  "Fed politika faizi", "Büyük fonlar ne yapıyor?", "OPEC"):
        assert metin in html, metin
    for cikarilan in ("Doğal gaz", "Buğday", "Mısır", "WTI)"):
        assert cikarilan not in html, cikarilan


def test_emtia_sayfasi_arz_talep(istemci):
    html = istemci.get("/emtia/brent").get_data(as_text=True)
    assert 'id="cot-verisi"' in html          # fon konumu grafiği (WTI vekil)
    assert "Londra borsasında" in html        # vekil verinin açıklaması
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


def test_performans_siralamasi(istemci):
    html = istemci.get("/siyasetciler/performans").get_data(as_text=True)
    # Jane'in 12 NVDA alımı var, NVDA endeksten hızlı yükseliyor: sıralamada ve pozitif
    assert "Jane Senator" in html
    assert "Bob Rep" not in html          # 10'dan az ölçülebilir alım
    kisi = istemci.get("/kisi/jane-senator").get_data(as_text=True)
    assert "Yatırım performansı" in kisi and "Komiteleri" in kisi


def test_cikar_catismasi(istemci):
    html = istemci.get("/siyasetciler/cikar-catismasi").get_data(as_text=True)
    assert "Jane Senator" in html and "Bilim, Uzay ve Teknoloji Komitesi" in html
    # Jane'in AAPL satımı da teknoloji: çatışma; Bob'un tarım komitesi NVDA ile çatışmaz
    assert "Bob Rep" not in html
    assert "Komite ↔ sektör" in istemci.get("/hisse/NVDA").get_data(as_text=True)


def test_sinyaller_ve_ozet(istemci):
    html = istemci.get("/sinyaller").get_data(as_text=True)
    for metin in ("Üçlü onay", "Sinyaller işe yarıyor mu?", "Siyasetçi alımları", "Küme alımları"):
        assert metin in html
    ozet = istemci.get("/gunluk-ozet").get_data(as_text=True)
    assert "yönetici" in ozet
    # Paylaşım metni ziyaretçilere gösterilmez
    assert "Metni kopyala" not in ozet and "ozet-metni" not in ozet


def test_arama_onerileri(istemci):
    def oner(q):
        return istemci.get(f"/api/oneri?q={q}").get_json()["oneriler"]

    assert oner("nvid")[0]["etiket"] == "NVDA"                 # şirket adının başı
    assert oner("NVDA")[0]["adres"] == "/hisse/NVDA"           # kod
    assert oner("nvidia corp")[0]["alt"] == "NVIDIA Corporation"
    assert oner("jane")[0] == {"tur": "Siyasetçi", "etiket": "Jane Senator",
                               "alt": "Demokrat · Temsilciler Meclisi · CA-11", "adres": "/kisi/jane-senator"}
    assert oner("altın")[0]["adres"] == "/emtia/altin"         # Türkçe karakterli
    assert oner("altin")[0]["adres"] == "/emtia/altin"         # Türkçe karaktersiz
    assert oner("gold")[0]["adres"] == "/emtia/altin"          # eş anlamlı
    assert oner("hatali") == []                                # şüpheli kayıt dizinde yok
    assert oner("") == []
    # Önerilerin hepsi açılabilir sayfalar
    for o in oner("o") + oner("n"):
        assert istemci.get(o["adres"]).status_code == 200, o


def test_onemli_siyasetciler_ve_trump(istemci):
    html = istemci.get("/siyasetciler").get_data(as_text=True)
    assert "Önemli siyasetçiler" in html
    assert "Donald J. Trump" in html and "/yurutme/donald-j-trump" in html
    assert "Azınlık grup başkanvekili" in html            # Jane'in liderlik görevi
    assert "Tarım Komitesi başkanı" in html                # Bob komite başkanı
    assert "congress/225x275/J000001.jpg" in html          # resmî fotoğraf

    trump = istemci.get("/yurutme/donald-j-trump").get_data(as_text=True)
    assert "İşlem bildirimi (OGE 278-T)" in trump and "https://oge.gov/t1.pdf" in trump

    kisi = istemci.get("/kisi/jane-senator").get_data(as_text=True)
    assert "avatar-buyuk" in kisi and "Azınlık grup başkanvekili" in kisi

    oneri = istemci.get("/api/oneri?q=trump").get_json()["oneriler"]
    assert oneri[0]["adres"] == "/yurutme/donald-j-trump"


def test_paylasim_etiketleri_ve_guncellik(istemci):
    html = istemci.get("/kisi/jane-senator").get_data(as_text=True)
    assert '<meta property="og:title" content="Jane Senator · Piyasa Kaydı">' in html
    assert 'property="og:locale" content="tr_TR"' in html
    assert "Veri güncelliği" in html and "Kongre bildirimleri" in html


def test_serit_api(istemci):
    gostergeler = istemci.get("/api/serit").get_json()["gostergeler"]
    adlar = [g["ad"] for g in gostergeler]
    assert adlar[:3] == ["BIST 100", "S&P 500", "Nasdaq"] and "Gram altın" in adlar
    assert all(g["deger"] > 0 for g in gostergeler)


def test_baskan_portfoyu(istemci):
    html = istemci.get("/yurutme/donald-j-trump").get_data(as_text=True)
    assert "Hisse ve fon portföyü" in html and 'class="pasta"' in html
    assert "NVIDIA CORP" in html and "/hisse/NVDA" in html
    assert "Elenen kalem" in html
    assert "En çok alınanlar" in html and "Apple Inc." in html
    hisse = istemci.get("/hisse/NVDA").get_data(as_text=True)
    assert "portföyünde bildirdi" in hisse
