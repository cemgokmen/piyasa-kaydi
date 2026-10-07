"""Yıllık mali durum bildirimi ayrıştırma ve ad → kod eşleme."""

import pytest

from piyasa.eslestirme import Eslestirici
from piyasa.toplama import oge_yillik

SEC = [
    {"ticker": "TSLA", "title": "Tesla, Inc."},
    {"ticker": "KR", "title": "KROGER CO"},
    {"ticker": "SHO", "title": "Sunstone Hotel Investors, Inc."},
    {"ticker": "SFM", "title": "Sprouts Farmers Market, Inc."},
    {"ticker": "GM", "title": "General Motors Co"},
    {"ticker": "MMM", "title": "3M CO"},
    {"ticker": "UAL", "title": "United Airlines Holdings, Inc."},
    {"ticker": "CCL", "title": "CARNIVAL CORP"},
]


@pytest.fixture()
def eslestirici(monkeypatch):
    # Fon listesi ağdan alınmasın
    monkeypatch.setattr("piyasa.eslestirme.requests.get", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    return Eslestirici(SEC)


@pytest.mark.parametrize("ad, kod", [
    ("TESLAMOTORSINC", "TSLA"),               # boşluksuz yazım
    ("THEKROGERCO", "KR"),
    ("SUNSTONE HOTEL INVS INC", "SHO"),       # kısaltma
    ("SPROUTS FMRS MKT INC", "SFM"),
    ("3M CO", "MMM"),
    ("UNITED AIRLINES HLDG", "UAL"),
    ("SPY - SPDR S&P 500 ETF", "SPY"),        # kodu açıkça yazılmış fon
])
def test_eslesen_adlar(eslestirici, ad, kod):
    assert eslestirici.bul(ad)[0] == kod


@pytest.mark.parametrize("ad", [
    "GENERAL MTRS FINL CO INC",               # bağlı ortaklık tahvil ihraççısı, GM değil
    "***CARNIVAL CORP",                       # tahvil hesabı işareti
    "WISCONSIN ST HLTH & EFA REV",            # belediye tahvili
    "UBS FDIC INSURED DEPOSIT PROGRAM",       # mevduat
    "NETFLIX INC DUE 11/15/2029 5.375",       # şirket tahvili
    "721 33H LLC",                            # şirket payı
])
def test_elenen_adlar(eslestirici, ad):
    assert eslestirici.bul(ad) == (None, None)


def test_bildirim_satirlari():
    sayfalar = ["""Part 6: Other Assets and Income
# Description EIF Value Income Type Income Amount
INVESTMENT ACCOUNT #2
151 TESLAMOTORSINC N/A $100,001 - $250,000 None (or less than $201)
152 TEXASINSTRUMENTS N/A $15,001 - $50,000 None (or less than $201)
153 OLIN CORP N/A None (or less than $1,001) Capital Gains $201 - $1,000
4. Charles Schwab Brokerage Account #1 No
4.1. QQQ - Invesco QQQ Trust, Series 1 Yes $1,000,001 -$5,000,000 $5,001 -$15,000
Part 7: Transactions
# Description Type Date Amount
490 YELP INC Purchase 7/31/2025 $15,001 - $50,000
9793 EXXON MOBIL CORP Sale 5/5/2025 $15,001 - $50,000
4. QQQ - Invesco QQQ Trust, Series 1 purchase 06/27/2025 $250,001 -$500,000
5. ACME CO Exchange 1/2/2025 $1,001 - $15,000
"""]
    varliklar, islemler = oge_yillik.ayristir(sayfalar)
    assert [(v["ad"], v["alt"], v["ust"]) for v in varliklar] == [
        ("TESLAMOTORSINC", 100_001, 250_000),
        ("TEXASINSTRUMENTS", 15_001, 50_000),        # değeri olmayan OLIN atlandı
        ("QQQ - Invesco QQQ Trust, Series 1", 1_000_001, 5_000_000),
    ]
    assert varliklar[0]["hesap"] == "INVESTMENT ACCOUNT #2"
    assert [(i["ad"], i["islem"], i["tarih"]) for i in islemler] == [
        ("YELP INC", "buy", "2025-07-31"),
        ("EXXON MOBIL CORP", "sell", "2025-05-05"),
        ("QQQ - Invesco QQQ Trust, Series 1", "buy", "2025-06-27"),   # değişim (exchange) atlandı
    ]


def test_tahvil_hesabi_tespiti():
    tahvil = [{"hesap": "H1", "ad": f"CITY OF X GO BONDS 4.000% DUE 20{i:02d}"} for i in range(10)]
    hisse = [{"hesap": "H2", "ad": f"HISSE {i} INC"} for i in range(10)]
    assert oge_yillik.tahvil_hesaplari(tahvil + hisse) == {"H1"}


def test_tutar():
    assert oge_yillik.tutar("$15,001 - $50,000") == (15_001, 50_000)
    assert oge_yillik.tutar("Over $50,000,000") == (50_000_001, 50_000_001)


def test_cusip_hatasi_kalici_bos_esleme_olarak_kaydedilmez():
    import sqlite3

    from piyasa.toplama.cusip import sonuclari_kaydet

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE cusip_ticker (cusip TEXT PRIMARY KEY, ticker TEXT, kaynak TEXT, guncelleme TEXT)")
    sonuc = [
        {"data": [{"ticker": "AAPL", "exchCode": "US"}]},
        {"warning": "No identifier found."},
        {"error": "Too many requests."},
    ]
    assert sonuclari_kaydet(conn, ["A", "B", "C"], sonuc) == (1, 1, 1)
    kayitlar = dict(conn.execute("SELECT cusip, ticker FROM cusip_ticker"))
    assert kayitlar == {"A": "AAPL", "B": None}


def test_tanim_kisaltma_tam_cumlelerle():
    from piyasa.sirket_profili import kisalt

    metin = "Acme Inc. makes rockets. " + "It also sells anvils to coyotes. " * 30
    kisa = kisalt(metin, sinir=80)
    assert kisa.startswith("Acme Inc. makes rockets.") and kisa.endswith(".")
    assert len(kisa) <= 80
    assert kisalt("Tek cümle ama çok uzun " * 50, sinir=40).startswith("Tek")   # ilk cümle her zaman


def test_ceviri_yedek_servise_gecer(monkeypatch):
    from piyasa import sirket_profili

    def bozuk(_):
        raise ConnectionError

    monkeypatch.setattr(sirket_profili, "_google", bozuk)
    monkeypatch.setattr(sirket_profili, "_mymemory", lambda m: "Merhaba")
    assert sirket_profili.cevir("Hello") == "Merhaba"
    monkeypatch.setattr(sirket_profili, "_mymemory", bozuk)
    assert sirket_profili.cevir("Hello") is None


def test_tanim_sadelestirme():
    from piyasa.sirket_profili import kurulus_yili, sadelestir

    tanim = ("VeriSign, Inc., together with its subsidiaries, provides domain name registry services "
             "in the United States, Europe, the Asia-Pacific, and internationally. "
             "It operates through Registry and Other segments. "
             "The company was founded in 1995 and is headquartered in Reston, Virginia.")
    assert sadelestir(tanim, "VeriSign, Inc.") == "VeriSign provides domain name registry services."
    assert kurulus_yili(tanim) == 1995
    assert sadelestir("Arista Networks, Inc. engages in the development, marketing, and sale of networking "
                      "solutions worldwide.", "Arista Networks, Inc.") == \
        "Arista Networks develops, markets, and sells networking solutions."
    # Sözlükte olmayan bir ad varsa kalıp olduğu gibi kalır
    assert "engages in the brewing of" in sadelestir("Acme engages in the brewing of beer.")


def test_turkce_duzeltme():
    from piyasa.sirket_profili import baslik_duzelt, turkcelestir

    assert turkcelestir("Şirket telefon tasarlıyor ve satıyor; iki segmentte faaliyet gösteriyor.") == \
        "Şirket telefon tasarlar ve satar; iki bölümde faaliyet gösterir."
    assert turkcelestir("Amerika Birleşik Devletleri'nde bankacılık hizmeti sunar.") == "ABD'de bankacılık hizmeti sunar."
    assert baslik_duzelt("Otomobil Üreticileri") == "Otomobil üreticileri"
    assert baslik_duzelt("İnternet İçeriği ve REIT") == "İnternet içeriği ve REIT"


def test_ceviri_sirket_adini_korur(monkeypatch):
    from piyasa import sirket_profili

    def sahte(metin):
        return metin.replace("Applied Materials", "Uygulamalı Malzemeler").replace("provides", "sağlar")

    monkeypatch.setattr(sirket_profili, "cevir", sahte)
    assert sirket_profili.adi_koruyarak_cevir("Applied Materials provides tools.", "Applied Materials") == \
        "Applied Materials sağlar tools."


def test_sirket_kisa_ad():
    from piyasa.bicim import sirket_kisa_ad

    assert sirket_kisa_ad("General Dynamics Corporation Common Stock") == "General Dynamics"
    assert sirket_kisa_ad("Alphabet Inc. - Class A") == "Alphabet"
    assert sirket_kisa_ad("KKR & Co. Inc.") == "KKR & Co"
    assert sirket_kisa_ad("Eli Lilly and Company") == "Eli Lilly and Company"
    assert sirket_kisa_ad("The Hershey Company") == "Hershey"
    assert sirket_kisa_ad("Berkshire Hathaway Inc. New") == "Berkshire Hathaway"
    assert sirket_kisa_ad("LENNAR CORP /NEW/") == "LENNAR"


def test_temel_hazirla_eksi_ve_para_birimi():
    from piyasa.temel import hazirla

    t = hazirla({"quoteType": "EQUITY", "currency": "USD", "financialCurrency": "TWD", "marketCap": 2.5e12,
                 "trailingPE": -3.0, "trailingEps": -1.2, "profitMargins": -0.55, "priceToBook": 99.6,
                 "enterpriseValue": 17.7e12, "totalRevenue": 4.4e12})
    ozet = {k["etiket"]: k["deger"] for k in t["ozet"]}
    assert ozet["F/K"] == "Zararda" and ozet["Net kar marjı"] == "−%55,0"
    satirlar = {r["etiket"]: r["deger"] for s in t["sekmeler"] for r in s["satirlar"]}
    # Bilanço başka para biriminde: karışık hesaplanan oranlar gösterilmez
    assert "PD/DD" not in satirlar and "Firma değeri" not in satirlar
    assert satirlar["Gelir (son 12 ay)"] == "4,4 trl TWD"
    assert t["birim_notu"]


def test_temel_fon():
    from piyasa.temel import hazirla

    t = hazirla({"quoteType": "ETF", "totalAssets": 8e11, "netExpenseRatio": 0.0945, "yield": 0.0099,
                 "ytdReturn": 12.7, "fundFamily": "State Street"})
    assert t["tur"] == "fon"
    assert [k["deger"] for k in t["ozet"]] == ["800,0 mr $", "%0,09", "%0,99", "+%12,70"]


def test_gunluk_guncelleme_gerekli_mi():
    from datetime import datetime

    from piyasa.zamanlama import DENEME_SINIRI, gerekli_mi

    def an(metin):
        return datetime.fromisoformat(metin)

    basarili_dun = {"zaman": "2026-10-05T08:00:00", "basarili": True, "deneme": 1}
    # Mac 15:00'te açıldı, bugün güncelleme yok: hemen yapılır
    assert gerekli_mi(an("2026-10-06T15:00"), basarili_dun)
    # Gece 03:00: gün 07:30'da başlar, dünkü güncelleme hâlâ geçerli
    assert not gerekli_mi(an("2026-10-06T03:00"), basarili_dun)
    # Bugün başarıyla yapıldıysa saat başı kontroller bir şey yapmaz
    assert not gerekli_mi(an("2026-10-06T16:00"), {"zaman": "2026-10-06T07:31:00", "basarili": True})
    # Hata verdiyse yeniden denenir, ama günde en çok DENEME_SINIRI kez
    hatali = {"zaman": "2026-10-06T07:31:00", "basarili": False, "deneme": 1}
    assert gerekli_mi(an("2026-10-06T08:31"), hatali)
    assert not gerekli_mi(an("2026-10-06T12:00"), dict(hatali, deneme=DENEME_SINIRI))
    # Hiç kayıt yoksa yapılır; farklı saat ayarı da çalışır
    assert gerekli_mi(an("2026-10-06T10:00"), {})
    assert not gerekli_mi(an("2026-10-06T06:00"), {"zaman": "2026-10-05T06:30:00", "basarili": True}, 6, 15)


def test_elle_yazilmis_tanimlar_ve_endustri_sozlugu():
    import re

    from piyasa.sirket_profili import elle_yazilmis_tanimlar, endustri_adi, endustriler

    tanimlar = elle_yazilmis_tanimlar()
    assert len(tanimlar) >= 250
    for kod, metin in tanimlar.items():
        assert kod == kod.upper() and 60 <= len(metin) <= 400, kod
        assert not re.search("[âîûÂÎÛ]", metin), kod            # şapkalı harf kullanılmaz
        assert metin.endswith((".", ")")), kod
    assert endustri_adi("Semiconductors") == "Yarı iletkenler (çip)"
    assert endustri_adi(None) is None
    assert all(not re.search("[âîûÂÎÛ]", v) for v in endustriler().values())


SENATO_RAPORU = """<table class="table table-striped"><thead><tr class="header"><th>#</th></tr></thead><tbody>
<tr> <td>1</td> <td> 09/04/2026 </td> <td>Spouse</td> <td> <a href="https://finance.yahoo.com/quote/JPM">JPM</a> </td>
<td> JP Morgan Chase &amp; Co. Common Stock </td> <td>Stock</td> <td>Sale (Partial)</td> <td>$15,001 - $50,000</td> <td>--</td> </tr>
<tr> <td>2</td> <td> 09/05/2026 </td> <td>Self</td> <td> -- </td>
<td> US Treasury Bill </td> <td>Other Securities</td> <td>Purchase</td> <td>$1,001 - $15,000</td> <td>--</td> </tr>
<tr> <td>3</td> <td> 09/06/2026 </td> <td>Self</td> <td> <a href="#">BRK.B</a> </td>
<td> Berkshire Hathaway Inc. </td> <td>Stock</td> <td>Purchase</td> <td>Over $50,000,000</td> <td>--</td> </tr>
<tr> <td>4</td> <td> 09/07/2026 </td> <td>Self</td> <td> <a href="#">AAPL</a> </td>
<td> Apple Inc. </td> <td>Stock</td> <td>Exchange</td> <td>$1,001 - $15,000</td> <td>--</td> </tr>
</tbody></table>"""


def test_senato_raporu_ayristirma():
    from piyasa.toplama.senato import kayitlara_cevir, rapor_ayristir, senator_bul

    rapor = {"kimlik": "abc", "adres": "/search/view/ptr/abc/", "ad": "A. Mitchell", "soyad": "McConnell, Jr.",
             "tarih": "2026-09-21", "tur": "ptr"}
    senatorler = {"mcconnell": [{"ad": "Mitch McConnell", "ilk": "mitch", "eyalet": "KY", "parti": "R"}],
                  "smith": [{"ad": "Tina Smith", "ilk": "tina", "eyalet": "MN", "parti": "D"},
                            {"ad": "Jason Smith", "ilk": "jason", "eyalet": "MO", "parti": "R"}]}
    senator = senator_bul(rapor, senatorler)
    assert senator["ad"] == "Mitch McConnell"
    assert senator_bul({"ad": "Tina", "soyad": "Smith"}, senatorler)["eyalet"] == "MN"

    kayitlar = kayitlara_cevir(rapor, rapor_ayristir(SENATO_RAPORU), senator)
    # Hazine bonosu (hisse değil) ve değişim (exchange) alınmaz
    assert [k["ticker"] for k in kayitlar] == ["JPM", "BRK-B"]
    jpm, brk = kayitlar
    assert jpm["action"] == "sell" and (jpm["amount_min"], jpm["amount_max"]) == (15001, 50000)
    assert jpm["transaction_date"] == "2026-09-04" and jpm["disclosed_date"] == "2026-09-21"
    assert jpm["chamber"] == "Senato" and jpm["party"] == "R" and jpm["state"] == "KY"
    assert jpm["person_slug"] == "mitch-mcconnell" and jpm["asset_name"] == "JP Morgan Chase & Co. Common Stock"
    assert "(Spouse)" in jpm["security_name"]
    assert brk["action"] == "buy" and brk["amount_min"] == 50000000
    assert brk["source_url"] == "https://efdsearch.senate.gov/search/view/ptr/abc/"


def test_ihale_alici_adi_eslesmesi():
    from piyasa.toplama.ihaleler import ad_uyuyor_mu

    assert ad_uyuyor_mu("PALANTIR USG INC", "Palantir Technologies")
    assert ad_uyuyor_mu("APPLE INC.", "Apple")
    assert not ad_uyuyor_mu("APPLE HOSPITALITY REIT", "Apple")
    assert ad_uyuyor_mu("GENERAL DYNAMICS LAND SYSTEMS INC", "General Dynamics")
    assert not ad_uyuyor_mu("GENERAL ELECTRIC CO", "General Dynamics")
