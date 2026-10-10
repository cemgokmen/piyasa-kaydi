"""Biçimlendirme, fiyat hesapları ve Kongre ayrıştırma yardımcıları."""

from datetime import UTC

import pandas as pd
import pytest

from piyasa import bicim, fiyat
from piyasa.toplama import kongre


@pytest.mark.parametrize("girdi, beklenen", [
    (0, "0 $"),
    (950, "950 $"),
    (15_000, "15 bin $"),
    (1_250_000, "1,2 mn $"),
    (3_400_000_000, "3,4 mr $"),
])
def test_kisa_tutar(girdi, beklenen):
    assert bicim.kisa_tutar(girdi) == beklenen


def test_kisa_aralik():
    assert bicim.kisa_aralik(1_001, 15_000) == "1 bin – 15 bin $"
    assert bicim.kisa_aralik(5_000, 5_000) == "5 bin $"
    assert bicim.kisa_aralik(None, None) == "—"


def test_yuzde_ve_fiyat():
    assert bicim.yuzde(0.0532) == "+%5,32"
    assert bicim.yuzde(-0.1) == "−%10,00"
    assert bicim.yuzde(None) == "—"
    assert bicim.fiyat(1234.5) == "1.234,50"
    assert bicim.ondalik(32.456) == "32,5"
    assert bicim.ondalik(1234.5, 2) == "1.234,50"
    assert bicim.ondalik(7, 0) == "7"


def test_tarihler():
    assert bicim.kisa_tarih("2026-08-18") == "18 Ağu"
    assert bicim.uzun_tarih("2026-08-18") == "18 Ağustos 2026"
    assert bicim.donem_metni("2026-06-30") == "2026 2. çeyrek"


def test_yahoo_kodu():
    assert fiyat.yahoo_kodu("BRK.B") == "BRK-B"
    assert fiyat.yahoo_kodu("LEN, LEN.B") == "LEN"
    assert fiyat.yahoo_kodu("aapl") == "AAPL"


def test_degisim_hesabi():
    tarihler = pd.bdate_range("2020-01-01", "2026-01-01")
    seri = pd.Series(100.0, index=tarihler)
    seri.iloc[-1] = 110.0
    assert fiyat._degisim(seri, None) == pytest.approx(0.10)
    assert fiyat._degisim(seri, pd.DateOffset(years=1)) == pytest.approx(0.10)
    # 10 yıllık geçmiş yok: değişim hesaplanmamalı
    assert fiyat._degisim(seri, pd.DateOffset(years=10)) is None


def test_kongre_tutar_ve_isim():
    assert kongre.tutar_coz("$1,001 - $15,000") == (1001, 15000)
    assert kongre.tutar_coz("Over $50,000,000") == (50_000_000, 50_000_000)
    assert kongre.sade("Sánchez") == "sanchez"

    uyeler = {
        "MD06": {"parti": "D", "ad": "April McClain Delaney", "soyad": "McClain Delaney"},
        "GA07": {"parti": "R", "ad": "Richard McCormick", "soyad": "McCormick"},
    }
    assert kongre.uye_bul({"bolge": "MD06", "soyad": "Delaney"}, uyeler)["parti"] == "D"
    # Bölge değişmiş ama soyadı tek: yine bulunmalı
    assert kongre.uye_bul({"bolge": "GA06", "soyad": "McCormick"}, uyeler)["parti"] == "R"
    assert kongre.uye_bul({"bolge": "TX01", "soyad": "Kimse"}, uyeler) is None


def test_haber_secimi():
    from datetime import datetime

    from piyasa.emtia import haberler

    def h(baslik, kaynak="Ajans", gun=1):
        return {"baslik": baslik, "kaynak": kaynak, "zaman": datetime(2026, 10, gun, tzinfo=UTC),
                "etiketler": haberler.etiketle(baslik)}

    secilen = haberler._sec([
        h("Gram altın bugün ne kadar?"),                      # fiyat listesi
        h("6 Ekim altın fiyatları: gram düşüşte"),             # tarihli fiyat listesi
        h("Konya'da altın fiyatları güne nasıl başladı?"),     # yerel fiyat listesi
        h("OPEC üretimi artırma kararı aldı", gun=3),
        h("OPEC üretimi artırma kararı aldı", gun=2),           # aynı başlık
        h("Altın için Fed beklentisi", kaynak="instagram.com"),  # sosyal medya
    ], 10)
    assert [x["baslik"] for x in secilen] == ["OPEC üretimi artırma kararı aldı"]
    assert set(secilen[0]["etiketler"]) >= {"OPEC", "Arz"}


def test_turkce_ekler():
    from piyasa.bicim import ek
    ornekler = {("2016", "de"): "2016'da", ("2013", "den"): "2013'ten", ("2012", "e"): "2012'ye",
                ("%40", "si"): "%40'ı", ("%25", "si"): "%25'i", ("%6", "si"): "%6'sı", ("%10", "si"): "%10'u",
                ("%92", "lik"): "%92'lik", ("%30", "lik"): "%30'luk", ("1.050.000", "de"): "1.050.000'de",
                ("1.000.000", "de"): "1.000.000'da", ("3,125", "den"): "3,125'ten", ("Ethereum", "e"): "Ethereum'a",
                ("Solana", "e"): "Solana'ya", ("XRP", "e"): "XRP'ye", ("07:00", "de"): "07:00'de",
                ("21:00", "de"): "21:00'de", ("06:15", "de"): "06:15'te", ("16:30", "de"): "16:30'da"}
    for (metin, tur), beklenen in ornekler.items():
        assert ek(metin, tur) == beklenen


def test_yeni_halka_arzda_ilk_islemden_beri():
    """Ocak 2026'da işlem görmeye başlayan hisse: 1/5/10 yıl yerine tek 'ilk işlemden beri' değişimi."""
    import pandas as pd

    from piyasa import fiyat
    gunler = pd.bdate_range("2026-01-05", "2026-10-09")
    tablo = pd.DataFrame({"Close": [10 + i * 0.05 for i in range(len(gunler))], "Volume": 1000}, index=gunler)
    b = fiyat.tablodan_bilgi("YENI.IS", tablo)
    anahtarlar = [d["anahtar"] for d in b["degisimler"]]
    assert anahtarlar == ["1g", "1h", "1a", "ilk"]
    ilk = b["degisimler"][-1]
    assert ilk["ilk_tarih"] == "2026-01-05" and ilk["oran"] == pytest.approx(tablo["Close"].iloc[-1] / 10 - 1)
    # 1 yıllık grafik bütün geçmişi gösterir; 5 ve 10 yıl gizlenir
    assert b["gizli_araliklar"] == ["5y", "10y"] and set(b["seriler"]) == {"1a", "1y"}
