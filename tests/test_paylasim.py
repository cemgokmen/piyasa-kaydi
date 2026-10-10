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
    assert all(calistir.uzunluk(a["metin"]) <= 280 for a in liste)
    assert liste == sorted(liste, key=lambda a: -a["onem"])


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
