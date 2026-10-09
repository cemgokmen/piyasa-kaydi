"""Canlı sayfa, gün içi Form 4 akışı ve 15 dakikalık güncelleme."""

from piyasa.toplama import form4_canli

ATOM = b"""<?xml version="1.0" encoding="ISO-8859-1" ?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
  <title>4 - Flanigan Micheal Neil (0002076313) (Reporting)</title>
  <link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/2076313/000143774926032410/0001437749-26-032410-index.htm"/>
  <updated>2026-10-09T10:51:36-04:00</updated>
</entry>
<entry>
  <title>4 - Avidia Bancorp, Inc. (0002064146) (Issuer)</title>
  <link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/2064146/000143774926032410/0001437749-26-032410-index.htm"/>
  <updated>2026-10-09T10:51:36-04:00</updated>
</entry>
<entry>
  <title>424B2 - GOLDMAN SACHS BANK USA (0001234567) (Filer)</title>
  <link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/1234567/000123456726000001/0001234567-26-000001-index.htm"/>
  <updated>2026-10-09T10:50:00-04:00</updated>
</entry>
<entry>
  <title>4/A - Gogoro Inc. (0001886190) (Issuer)</title>
  <link rel="alternate" type="text/html" href="https://www.sec.gov/Archives/edgar/data/1886190/000188619026000050/0001886190-26-000050-index.htm"/>
  <updated>2026-10-09T09:12:00-04:00</updated>
</entry>
</feed>"""


class _Cevap:
    content = ATOM

    def raise_for_status(self):
        pass


def test_akis_yalnizca_form4_sirket_satirlari(monkeypatch):
    monkeypatch.setattr(form4_canli.requests, "get", lambda *a, **k: _Cevap())
    kayitlar = form4_canli.akis()
    # Her bildirim akışta iki kez (kişi ve şirket) görünür; yalnızca şirket satırı alınır, 424B2 gibi formlar atlanır
    assert kayitlar == [
        {"numara": "0001437749-26-032410", "cik": "2064146", "sirket": "Avidia Bancorp, Inc.", "tarih": "2026-10-09"},
        {"numara": "0001886190-26-000050", "cik": "1886190", "sirket": "Gogoro Inc.", "tarih": "2026-10-09"},
    ]


def test_canli_sayfa(istemci):
    r = istemci.get("/canli")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Piyasada şu an" in html and 'id="canli-akis"' in html
    # KAP bildirimleri şirket sayfasına ve KAP'a bağlanır
    assert 'href="/bist/THYAO"' in html and "kap.org.tr/tr/Bildirim/" in html
    assert "Geri alım" in html and "Fon payı" in html


def test_canli_suzgec_ve_parca(istemci):
    bist = istemci.get("/api/canli/akis?kaynak=bist").get_data(as_text=True)
    assert "kaynak-bist" in bist and "kaynak-abd" not in bist
    abd = istemci.get("/api/canli/akis?kaynak=abd").get_data(as_text=True)
    assert "kaynak-bist" not in abd
    # Bilinmeyen süzgeç bütün kaynakları gösterir
    assert istemci.get("/canli?kaynak=xyz").status_code == 200


def test_ana_sayfada_son_dakika_ve_menude_canli(istemci):
    html = istemci.get("/").get_data(as_text=True)
    assert "Son dakika" in html and 'href="/canli"' in html


def test_canli_guncelleme_adimlari():
    from piyasa.__main__ import CANLI_GUNCELLEME, KOMUTLAR
    for adim in CANLI_GUNCELLEME:
        komut = adim[0] if isinstance(adim, tuple) else adim
        assert komut in KOMUTLAR
    from piyasa import zamanlama
    assert zamanlama.CANLI_ARALIK == 900 and {12, 18, 21, 0} <= set(zamanlama.HIZLI_SAATLER)


def test_www_adresi_yonlenir(istemci):
    r = istemci.get("/bist?liste=xu100", base_url="https://www.piyasakaydi.com")
    assert r.status_code == 301 and r.headers["Location"] == "https://piyasakaydi.com/bist?liste=xu100"


def test_cloudflare_onbellek_basliklari(istemci):
    assert istemci.get("/bist").headers["Cache-Control"] == "public, max-age=0, s-maxage=120"
    assert istemci.get("/api/canli/akis").headers["Cache-Control"] == "public, max-age=0, s-maxage=30"
    # Hata sayfaları önbelleğe alınmaz
    assert istemci.get("/bist/YOKBOYLE").headers["Cache-Control"] == "no-cache"


def test_bildirim_saatleri():
    from datetime import datetime

    from piyasa import zamanlama
    assert zamanlama.bildirim_saati_mi(datetime(2026, 10, 9, 10, 0))      # cuma sabah: KAP
    assert zamanlama.bildirim_saati_mi(datetime(2026, 10, 10, 3, 0))      # cumartesi gece: ABD cuma akşamı
    assert not zamanlama.bildirim_saati_mi(datetime(2026, 10, 10, 14, 0)) # cumartesi öğlen
    assert not zamanlama.bildirim_saati_mi(datetime(2026, 10, 12, 6, 0))  # pazartesi sabah 6


def test_bist_fiyat_saatleri_ve_birlestirme():
    from datetime import date, datetime, timedelta

    from piyasa.bist import piyasa
    assert piyasa.borsa_acik(datetime(2026, 10, 9, 11, 0))
    assert not piyasa.borsa_acik(datetime(2026, 10, 10, 11, 0))           # cumartesi
    # Cumartesi: son kapanış cuma 18:35; cuma akşamı indirildiyse yeniden indirilmez
    cumartesi = datetime(2026, 10, 10, 12, 0)
    assert piyasa.son_kapanis(cumartesi) == datetime(2026, 10, 9, 18, 35)
    assert not piyasa.gerekli_mi(cumartesi, datetime(2026, 10, 9, 19, 0).timestamp())
    assert piyasa.gerekli_mi(cumartesi, datetime(2026, 10, 9, 15, 0).timestamp())
    # Borsa açıkken 20 dakikada bir
    acik = datetime(2026, 10, 9, 11, 0)
    assert not piyasa.gerekli_mi(acik, (acik - timedelta(minutes=10)).timestamp())
    assert piyasa.gerekli_mi(acik, (acik - timedelta(minutes=25)).timestamp())
    # Son günler saklanan geçmişe eklenir, aynı gün güncellenir
    d = [(date.today() - timedelta(days=i)).isoformat() for i in (3, 2, 1, 0)]
    s = piyasa._birlestir({"t": d[:3], "c": [1.0, 2.0, 3.0]}, {"t": d[2:], "c": [3.5, 4.0]})
    assert s == {"t": d, "c": [1.0, 2.0, 3.5, 4.0]}


def test_arama_motoru_etiketleri(istemci):
    html = istemci.get("/", base_url="https://piyasakaydi.com").get_data(as_text=True)
    assert '<link rel="canonical" href="https://piyasakaydi.com/">' in html
    assert '"@type": "WebSite"' in html and "Piyasa Kaydi" in html and "/static/logo.png" in html
    # Süzgeçli adreslerin resmi adresi süzgeçsiz sayfadır
    html = istemci.get("/bist?liste=xu100", base_url="https://piyasakaydi.com").get_data(as_text=True)
    assert '<link rel="canonical" href="https://piyasakaydi.com/bist">' in html
