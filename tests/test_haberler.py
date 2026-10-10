"""Finans haberleri: RSS okuma, konu, aynı haberin kümelenmesi, günün özeti ve paylaşım kartları."""

from piyasa.toplama import haber_akisi as h

RSS = b"""<?xml version="1.0"?><rss xmlns:media="http://search.yahoo.com/mrss/"><channel>
<item><title>Dolar/TL g\xc3\xbcne y\xc3\xbckseli\xc5\x9fle ba\xc5\x9flad\xc4\xb1</title><link>https://ornek/a</link>
<description><![CDATA[<img src="x.jpg"/>Dolar/TL 49,3 seviyesinde. \xc4\xb0kinci c\xc3\xbcmle.]]></description>
<pubDate>Sat, 10 Oct 2026 11:49:00 +0300</pubDate><media:content url="https://ornek/a.jpg"/></item>
<item><title></title><link>https://ornek/b</link></item>
</channel></rss>"""


def test_rss_cozumleme():
    liste = h.akisi_coz(RSS, "AA")
    assert len(liste) == 1
    x = liste[0]
    assert x["baslik"] == "Dolar/TL güne yükselişle başladı" and x["ozet"].startswith("Dolar/TL 49,3 seviyesinde.")
    assert x["yayin"] == "2026-10-10T08:49:00+00:00" and x["gorsel"] == "https://ornek/a.jpg"


def test_konu_ve_istisnalar():
    assert h.konu("TCMB faiz kararını açıkladı")[0] == "faiz"
    assert h.konu("Gram altın yükseldi")[0] == "doviz"
    assert h.konu("Satış beklentinin altında kaldı", "şirket satış")[0] == "ekonomi"     # 'altında' altın değil
    assert h.konu("Ünlü sanatçı konser verdi")[0] is None                                 # 'ons' konserde aranmaz
    assert h.konu("Binance kripto para borsalarında yeni dönem")[0] == "kripto"


def test_ayni_haber_kumelenir():
    assert h.benzer("Merkez Bankası politika faizini yüzde 40'ta sabit tuttu",
                    "Merkez Bankası politika faizini sabit tuttu: yüzde 40") >= 0.6
    assert h.benzer("Türkiye'nin ihracatı 9 ayda 200 milyar dolar", "Türkiye'nin fındık ihracatı 9 ayda düştü") == 0


def test_gunun_ozeti_haberli_ve_guncel(istemci):
    html = istemci.get("/gunluk-ozet").get_data(as_text=True)
    assert "Günün haberleri" in html and "Son 24 saatte olanlar" in html
    # Manşet: aynı haberi iki kaynak verdi (en önemli), fiyat sayfası değil
    assert "Merkez Bankası politika faizini" in html and "2 kaynakta" in html
    assert "Derbi" not in html                                   # ekonomi dışı haber alınmaz
    # Eski tarihli özet bağlantısı bugüne yönlenir
    r = istemci.get("/gunluk-ozet/2026-01-01")
    assert r.status_code == 301 and r.headers["Location"].endswith("/gunluk-ozet")


def test_haber_kartlari_paylasim_sayfasinda(istemci):
    html = istemci.get("/paylasim").get_data(as_text=True)
    assert "Finans haberleri" in html and "FAİZ VE ENFLASYON" in html and "Neden önemli?" in html


def test_spor_ve_fed_karisikligi():
    assert h.konu("Fed faiz kararını açıkladı")[0] == "faiz"
    assert h.konu("TFF'den teşekkür", "Türkiye Futbol Federasyonu açıklama yaptı")[0] != "faiz"
    assert h.GURULTU.search("TFF'den Montella'ya teşekkür mesajı Türkiye Futbol Federasyonu")
