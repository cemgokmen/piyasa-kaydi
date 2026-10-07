"""Kripto: coin eşleştirme, Kongre bildirimlerinden kripto işlemleri, sayfalar."""

from piyasa.kripto import sorgular
from piyasa.kripto.tanimlar import KRIPTOLAR, coin_bul


def test_coin_bul():
    assert coin_bul("Bitcoin") == "bitcoin"
    assert coin_bul("Bitcoin Cash (BCH)") == "bitcoin-cash"      # uzun ad önce
    assert coin_bul("Ethereum (ETH)") == "ethereum"
    assert coin_bul(None, "IBIT") == "bitcoin"                   # kripto fonu
    assert coin_bul(None, "ETHA") == "ethereum"
    assert coin_bul("LinkedIn Corp") is None                     # 'link' kelime içinde
    assert coin_bul(None, "AAPL") is None


def test_tanimlar_eksiksiz():
    for k in KRIPTOLAR:
        for alan in ("ozet", "kurucu", "mekanizma", "arz", "etkenler", "riskler", "haber"):
            assert k[alan], f"{k['slug']} için {alan} boş"


def test_meclis_kripto_satirlari():
    from piyasa.toplama import kongre
    bildirim = {"doc": "20030001", "yil": 2025, "ad": "Örnek Üye", "soyad": "Üye", "bolge": "CA11", "tarih": "2025-08-01"}
    satirlar = [
        {"varlik": "Bitcoin [CT]", "tur": "P", "tutar": "$1,001 - $15,000", "islem_tarihi": "07/15/2025", "sahip": "SP"},
        {"varlik": "iShares Bitcoin Trust ETF (IBIT) [ST]", "tur": "S", "tutar": "$15,001 - $50,000",
         "islem_tarihi": "07/16/2025", "sahip": ""},
        {"varlik": "Apple Inc. (AAPL) [ST]", "tur": "P", "tutar": "$1,001 - $15,000", "islem_tarihi": "07/16/2025", "sahip": ""},
    ]
    kayitlar = kongre.kripto_kayitlari(bildirim, satirlar, {})
    assert [(k["coin"], k["ticker"], k["action"]) for k in kayitlar] == [("bitcoin", None, "buy"), ("bitcoin", "IBIT", "sell")]
    assert kayitlar[0]["amount_min"] == 1001 and kayitlar[0]["transaction_date"] == "2025-07-15"


def test_senato_kripto_satirlari():
    from piyasa.toplama import senato
    rapor = {"kimlik": "abc", "ad": "Sam", "soyad": "Senate", "tarih": "2025-08-01", "adres": "/search/view/ptr/abc/"}
    satirlar = [
        {"sira": "1", "tarih": "07/15/2025", "sahip": "Spouse", "ticker": "--", "varlik": "Ethereum",
         "tur": "Cryptocurrency", "islem": "Purchase", "tutar": "$1,001 - $15,000"},
        {"sira": "2", "tarih": "07/15/2025", "sahip": "Self", "ticker": "MSFT", "varlik": "Microsoft",
         "tur": "Stock", "islem": "Purchase", "tutar": "$1,001 - $15,000"},
    ]
    kayitlar = senato.kripto_kayitlari(rapor, satirlar, None)
    assert len(kayitlar) == 1 and kayitlar[0]["coin"] == "ethereum" and kayitlar[0]["sahip"] == "Spouse"


def test_sorgular(uygulama):
    c = sorgular.cot("bitcoin")
    assert c["kurum_net"] == 4000 + 59 * 10 - 1500 and c["konum"] == 100 and c["hedge_net"] == -7000
    e = sorgular.etf_kurumlari("bitcoin")
    kurum = next(x for x in e["kurumlar"] if x["fon_slug"] == "kripto-fon")
    assert kurum["durum"] == "artirdi" and kurum["deger"] == 300 * 50_000
    assert sorgular.etf_kurumlari("dogecoin") is None
    islemler = sorgular.siyasetci_islemleri("bitcoin")
    assert len(islemler) == 2 and islemler[1]["sahip"] == "eşi adına"
    assert sorgular.siyasetci_ozeti()["coinler"]["ethereum"] == 1


def test_kripto_sayfalari(istemci):
    html = istemci.get("/kripto").get_data(as_text=True)
    for metin in ("Kripto paralar", "Bitcoin", "Siyasetçilerin kripto işlemleri", "Kripto Fon", "Jane Senator"):
        assert metin in html
    html = istemci.get("/kripto/bitcoin").get_data(as_text=True)
    for metin in ("Bitcoin nedir?", "Satoshi Nakamoto", "Arz: piyasada ne kadar Bitcoin var?", "Kurumsal yatırımcılar",
                  "Hangi kurumlar Bitcoin fonu tutuyor?", "Siyasetçilerin Bitcoin işlemleri", "eşi adına", "Riskler"):
        assert metin in html, metin
    # Fon verisi olmayan coin de açılır; boş durum mesajı görünür
    html = istemci.get("/kripto/dogecoin").get_data(as_text=True)
    assert "Kayıtlarımızda Kongre üyelerinin Dogecoin işlemi yok" in html
    assert istemci.get("/kripto/yok").status_code == 404
    assert istemci.get("/api/kripto/bitcoin/fiyat").status_code == 200
    assert istemci.get("/api/kripto/bitcoin/anlik").get_json()["fiyat"] == 123.45


def test_kripto_arama(istemci):
    oneriler = istemci.get("/api/oneri?q=bitcoin").get_json()["oneriler"]
    assert oneriler[0]["adres"] == "/kripto/bitcoin"
    assert istemci.get("/api/oneri?q=eth").get_json()["oneriler"][0]["adres"] == "/kripto/ethereum"
