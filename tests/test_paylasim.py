"""X paylaşımı: seçim eşikleri, haber metinleri, kurallar ve OAuth imzası."""

from datetime import datetime

from piyasa.paylasim import calistir, metin, secim, x


def test_tutar_ve_sayilar():
    assert metin.tutar(30_400_000) == "30,4 milyon TL"
    assert metin.tutar(1_250_000_000, "dolar") == "1,25 milyar dolar"
    assert metin.tutar(3_000_000, "dolar") == "3 milyon dolar"
    assert metin.adet(14_160_000) == "14,16 milyon" and metin.adet(180_000) == "180.000"
    assert metin.fiyat_metni(1234.5, "TL") == "1.234,50 TL"


def test_kap_metni_haber_dilinde():
    m = metin.kap_islem({"islem": "buy", "kisi_turu": "kisi", "kisi": "Nahit Kiler", "kisi_kisa": "Nahit Kiler",
                         "sirket": "Kiler Holding", "gorev": "Yönetim kurulu başkanı", "islem_tarihi": "2026-10-08",
                         "tutar": 399_700_000, "nominal": 29_260_000, "fiyat": 13.66, "oran_sonra": 50.0, "kod": "KLRHO"})
    assert m.startswith("Kiler Holding yönetim kurulu başkanı Nahit Kiler, 8 Ekim'de şirket paylarında 399,7 milyon TL")
    assert "ortalama 13,66 TL" in m and "#KLRHO" in m and "piyasakaydi.com/bist/KLRHO" in m
    # Şirket ortak, kişi gibi yazılmaz
    m = metin.kap_islem({"islem": "buy", "kisi_turu": "kisi", "kisi": "Ahes İnşaat Anonim Şirketi", "kisi_kisa": "Ahes İnşaat",
                         "sirket": "Ahes GYO", "gorev": "Yönetim kurulu başkanı", "islem_tarihi": "2026-10-08",
                         "tutar": 54_800_000, "kod": "AHSGY"})
    assert m.startswith("Ahes GYO ortağı Ahes İnşaat,")


def test_form4_metni_ve_rol():
    m = metin.form4({"action": "buy", "rol": "CEO", "sirket": "NVIDIA", "kisi": "Jensen Huang", "tutar": 12_400_000,
                     "adet": 100_000, "fiyat": 124.0, "ticker": "NVDA"})
    assert m.startswith("NVIDIA'nın CEO'su Jensen Huang, şirket hisselerinde 12,4 milyon dolarlık alım yaptı.")
    assert "$NVDA" in m
    assert secim._rol("President and CEO") == "CEO" and secim._rol("Yönetim kurulu üyesi") == "Yönetim kurulu üyesi"


def test_adaylar_ornek_veride(uygulama):
    from piyasa.veritabani import get_connection
    conn = get_connection()
    try:
        liste = secim.adaylar(conn, datetime.now(), kur=40.0, saat=24 * 10)
    finally:
        conn.close()
    # Örnek veride THYAO'da 30 milyon TL'lik yönetim kurulu üyesi alımı var; fon eşik bildirimi paylaşılmaz
    assert any(a["anahtar"] == "kap:1001" for a in liste)
    assert not any(a["anahtar"] == "kap:1003" for a in liste)
    assert all(calistir.uzunluk(a["metin"]) <= calistir.X_SINIRI for a in liste)
    # Önce haberler (kendi puanıyla), sonra alım satımlar (dolar karşılığıyla) sıralı
    haberler = [a for a in liste if a["grup"] == "haber"]
    islemler = [a for a in liste if a["grup"] == "islem"]
    assert liste == haberler + islemler and islemler == sorted(islemler, key=lambda a: -a["onem"])


def test_gece_ve_gunluk_sinir(uygulama):
    from piyasa.veritabani import get_connection
    conn = get_connection()
    try:
        assert calistir.paylasabilir_mi(conn, datetime(2026, 10, 10, 3, 0)) == (False, "gece saatleri")
        assert calistir.paylasabilir_mi(conn, datetime(2026, 10, 10, 10, 0))[0]
    finally:
        conn.close()


def test_oauth_imzasi_belirli():
    a = {"X_API_KEY": "k", "X_API_SECRET": "s", "X_ACCESS_TOKEN": "t", "X_ACCESS_SECRET": "ts"}
    b1 = x.oauth_basligi("POST", x.ADRES, a, zaman=1700000000, rastgele="abc")
    b2 = x.oauth_basligi("POST", x.ADRES, a, zaman=1700000000, rastgele="abc")
    assert b1 == b2 and b1.startswith("OAuth ") and 'oauth_signature="' in b1 and 'oauth_token="t"' in b1
    assert x.oauth_basligi("POST", x.ADRES, a, zaman=1700000001, rastgele="abc") != b1


def test_anahtar_yoksa_paylasmaz(tmp_path, monkeypatch):
    monkeypatch.setattr(x, "ANAHTAR_DOSYASI", tmp_path / "yok.env")
    assert x.anahtarlar() is None
    (tmp_path / "x.env").write_text("X_API_KEY=a\nX_API_SECRET=b\nX_ACCESS_TOKEN=c\nX_ACCESS_SECRET=d\n")
    monkeypatch.setattr(x, "ANAHTAR_DOSYASI", tmp_path / "x.env")
    assert x.anahtarlar()["X_ACCESS_SECRET"] == "d"


def test_paylasim_varsayilan_kapali(tmp_path, monkeypatch):
    dosya = tmp_path / "x.env"
    dosya.write_text("X_API_KEY=a\nX_PAYLASIM=kapali\n")
    monkeypatch.setattr(x, "ANAHTAR_DOSYASI", dosya)
    assert not x.acik_mi()
    dosya.write_text("X_PAYLASIM=acik\n")
    assert x.acik_mi()


def test_paylasim_kartlari_yalnizca_yerel(istemci):
    # Cloudflare üzerinden gelen istek sayfayı göremez
    assert istemci.get("/paylasim", headers={"CF-Connecting-IP": "1.2.3.4"}).status_code == 404
    assert istemci.post("/paylasim/isaretle", json={"anahtar": "a"}, headers={"CF-Ray": "x"}).status_code == 404
    r = istemci.get("/paylasim?saat=240")
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    html = r.get_data(as_text=True)
    assert 'class="paylasim-svg"' in html and "KAP · İÇERİDEN ALIM" in html and "piyasakaydi.com/bist/THYAO" in html


def test_paylasildi_isaretlenen_bir_daha_onerilmez(istemci):
    assert 'data-anahtar="kap:1001"' in istemci.get("/paylasim?saat=240").get_data(as_text=True)
    assert istemci.post("/paylasim/isaretle", json={"anahtar": "kap:1001", "metin": "deneme"}).get_json()["tamam"]
    assert 'data-anahtar="kap:1001"' not in istemci.get("/paylasim?saat=240").get_data(as_text=True)
    # Geçersiz durum reddedilir
    assert istemci.post("/paylasim/isaretle", json={"anahtar": "x", "durum": "sil"}).status_code == 400
    from piyasa.veritabani import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM paylasim")
    conn.commit()
    conn.close()


def test_robots_paylasim_sayfasini_engeller(istemci):
    assert "Disallow: /paylasim" in istemci.get("/robots.txt").get_data(as_text=True)


def test_tanitim_sayfalari_yalnizca_yerel(istemci):
    assert istemci.get("/paylasim/tanitim", headers={"CF-Connecting-IP": "1.2.3.4"}).status_code == 404
    html = istemci.get("/paylasim/tanitim").get_data(as_text=True)
    assert "Tanıtım zinciri" in html and "Biyografi 1" in html
    slayt = istemci.get("/paylasim/tanitim/slayt/02-bist").get_data(as_text=True)
    assert 'id="slayt"' in slayt and "KAP&#39;ta kim ne aldı?" in slayt
    assert istemci.get("/paylasim/tanitim/slayt/yok").status_code == 404
    from piyasa.paylasim import tanitim
    # X biyografisi 160 karakteri geçemez; bir gönderide en çok 4 görsel
    assert all(len(b) <= 160 for b in tanitim.PROFIL["bio_secenekleri"])
    assert all(len(g) <= 4 for _, g in tanitim.ZINCIR)
