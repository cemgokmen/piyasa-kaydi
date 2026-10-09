"""Borsa İstanbul: KAP bildirimlerinin ayrıştırılması ve BIST sayfaları."""

from piyasa.bicim import tr_baslik, tr_cumle
from piyasa.bist.sorgular import kisa_unvan
from piyasa.toplama import kap


def test_spk_cumlesi():
    metin = ("01.10.2026 tarihinde GERSAN ELEKTRİK TİCARET VE SANAYİ A.Ş. payları ile ilgili olarak 19,23 TL fiyattan "
             "1.250.000 TL toplam nominal tutarlı alış işlemi Erkan İzgi tarafınca gerçekleştirilmiştir. Bu işlemle "
             "birlikte sermayesindeki paylarım/oy haklarım 01.10.2026 tarihi itibariyle % 11,83 sınırına ulaşmıştır.")
    b = kap.pay_islemi_coz(metin, "GERSAN")
    assert (b["kisi"], b["kisi_turu"], b["islem"], b["islem_tarihi"]) == ("Erkan İzgi", "kisi", "buy", "2026-10-01")
    assert b["nominal"] == 1_250_000 and b["fiyat"] == 19.23 and b["oran_sonra"] == 11.83
    assert b["tutar"] == 1_250_000 * 19.23


def test_fiyat_araligi_ortalama_ve_fon():
    metin = ("30/09/2026 tarihinde LOGO YAZILIM A.Ş. payları ile ilgili olarak 136,1-137,0 TL fiyat aralığından 166.342 "
             "toplam nominal tutarlı satış işlemi kurucusu olduğumuz yatırım fonları tarafından gerçekleştirilmiştir. "
             "Payları toplamı %3 sınırının altına düşmüştür.")
    b = kap.pay_islemi_coz(metin, "İŞ PORTFÖY YÖNETİMİ A.Ş.")
    assert (b["kisi"], b["kisi_turu"], b["islem"]) == ("İŞ PORTFÖY YÖNETİMİ A.Ş.", "fon", "sell")
    assert (b["fiyat_alt"], b["fiyat_ust"], b["fiyat"]) == (136.1, 137.0, 136.55)
    # "ortalama" fiyat yazıyorsa aralığın ortası yerine o kullanılır
    metin = ("08/10/2026 tarihinde FLAP A.Ş. payları ile ilgili olarak 11,14 – 11,29 TL fiyat aralığından ortalama 11,21 "
             "TL fiyatla, 118.118 TL nominal tutarlı alış işlemi tarafımca gerçekleştirilmiştir.")
    b = kap.pay_islemi_coz(metin, "GÜRKAN GENÇLER")
    assert b["fiyat"] == 11.21 and b["kisi"] == "GÜRKAN GENÇLER"


def test_ortagin_bildirimi_ozetten_kisi():
    metin = ("08.10.2026 tarihinde Gülermak A.Ş. payları ile ilgili olarak 130,46 – 131,99 TL fiyat aralığından 126.164 "
             "toplam nominal tutarlı alış işlemi ortaklığımızca gerçekleştirilmiştir. Payımız %47,34'e ulaşmıştır.")
    b = kap.pay_islemi_coz(metin, "GÜLERMAK AĞIR SANAYİ", "Gülermak Emlak Yapı İnşaat Yatırım A.Ş. pay alım bildirimi")
    assert b["kisi"] == "Gülermak Emlak Yapı İnşaat Yatırım A.Ş." and b["kisi_turu"] == "sirket"
    assert b["oran_sonra"] == 47.34


def test_mkk_aktarimi_ve_formu():
    metin = ("Sermaye Piyasası Kurulu'nun Seri: II, No:15.1 Sayılı Tebliği kapsamında Cevahir Taahhüt İnşaat ve Ticaret A.Ş. "
             "tarafından Kuruluşumuza gönderilen pay alım satım işlemlerine ilişkin açıklama ekte yer almaktadır.")
    b = kap.pay_islemi_coz(metin, "KAMUYU AYDINLATMA PLATFORMU")
    assert b["kisi"] == "Cevahir Taahhüt İnşaat ve Ticaret A.Ş" and b["islem"] is None
    form = ("Ad Soyad / Ticaret Ünvanı : MEHMET ÖRNEK\nGörevi : YÖNETİM KURULU ÜYESİ\n"
            "Varsa Birlikte Hareket Eden Diğer Gerçek-Tüzel Kişiler :\n"
            "08/10/2026 0 25.000 -25.000 1.000.000 975.000 5 5 4,88 4,88\n")
    b = kap.form_coz(form, "KAMUYU AYDINLATMA PLATFORMU")
    assert (b["kisi"], b["gorev"], b["islem"], b["nominal"], b["oran_sonra"]) == \
        ("Mehmet Örnek", "YÖNETİM KURULU ÜYESİ", "sell", 25_000, 4.88)


def test_geri_alim_tablosu():
    hucre = '<td><div class="gwt-HTML control-label">{}</div></td>'
    satir = lambda *h: "<tr>" + "".join(hucre.format(x) for x in h) + "</tr>"  # noqa: E731
    sayfa = ("<table>" + satir("İşleme Konu Pay", "İşlem Tarihi", "İşleme Konu Payların Nominal Tutarı (TL)",
                               "Sermayeye Oranı (%)", "İşlem Fiyatı (TL/Adet)",
                               "Program Çerçevesinde Daha Önce Geri Alınan Payların Nominal Tutarı (TL)")
             + satir("B Grubu, KZGYO", "02.10.2026", "130.000", "0,065", "15,28", "0")
             + satir("B Grubu, KZGYO", "05.10.2026", "13.526", "0,00676", "15,98", "130.000") + "</table>")
    assert kap.geri_alim_tablosu(sayfa) == [
        {"islem_tarihi": "2026-10-02", "nominal": 130_000, "fiyat": 15.28, "oran": 0.065},
        {"islem_tarihi": "2026-10-05", "nominal": 13_526, "fiyat": 15.98, "oran": 0.00676},
    ]


def test_endeks_ve_sirket_listesi():
    sayfa = ('x{\\"code\\":\\"XU100\\",\\"content\\":[{\\"stockCode\\":\\"AKBNK\\",\\"title\\":\\"AKBANK T.A.Ş.\\",'
             '\\"mkkMemberOid\\":\\"1\\"}],\\"name\\":\\"BIST 100\\"}')
    assert kap.endeks_bilesenleri(sayfa, "XU100")[0]["stockCode"] == "AKBNK"
    sayfa = ('{"mkkMemberOid":"9","kapMemberTitle":"KARDEMİR A.Ş.","relatedMemberTitle":"X",'
             '"stockCode":"KRDMA, KRDMB, KRDMD","cityName":"KARABÜK","kapMemberType":"IGS"}')
    assert [s["kod"] for s in kap.bist_sirketleri(sayfa)] == ["KRDMA", "KRDMB", "KRDMD"]


def test_ilgili_kod():
    portfoy = {"stockCode": "AKP", "companyTitle": "AK PORTFÖY YÖNETİMİ A.Ş.", "relatedStocks": "FORTE"}
    assert kap.ilgili_kod(portfoy) == "FORTE"
    kap_aktarimi = {"stockCode": None, "companyTitle": "KAMUYU AYDINLATMA PLATFORMU", "relatedStocks": "TKFEN"}
    assert kap.ilgili_kod(kap_aktarimi) == "TKFEN"
    assert kap.ilgili_kod({"stockCode": "THYAO", "companyTitle": "TÜRK HAVA YOLLARI", "relatedStocks": None}) == "THYAO"


def test_turkce_bicim():
    assert tr_baslik("TÜRK HAVA YOLLARI A.O.") == "Türk Hava Yolları A.O."
    assert tr_baslik("BG HOLDİNG A.Ş.") == "BG Holding A.Ş."
    assert tr_baslik("İSKENDERUN DEMİR VE ÇELİK A.Ş.") == "İskenderun Demir ve Çelik A.Ş."
    assert tr_cumle("YÖNETİM KURULU BAŞKANI") == "Yönetim kurulu başkanı"
    assert kisa_unvan("Aselsan Elektronik Sanayi ve Ticaret A.Ş.") == "Aselsan Elektronik"


def test_bist_sayfalari(istemci):
    html = istemci.get("/bist").get_data(as_text=True)
    for metin in ("Borsa İstanbul", "KAP'ta kim aldı, kim sattı?", "Ahmet Örnek", "Yönetim kurulu üyesi",
                  "Kendi payını geri alan şirketler", "ASELS", "Hisseler", "Türk Hava Yolları A.O.",
                  "En çok yükselenler", "Teknoloji"):
        assert metin in html, metin
    # Fon eşik bildirimleri ayrı sekmede
    assert "Ak Portföy Yönetimi A.Ş." in html
    html = istemci.get("/bist/THYAO").get_data(as_text=True)
    for metin in ("Türk Hava Yolları", "BIST 30", "Yöneticiler ve büyük ortaklar ne yaptı?", "Ahmet Örnek",
                  "Fonların eşik bildirimleri", "Yeni uçak siparişi", "https://www.kap.org.tr/tr/Bildirim/1001"):
        assert metin in html, metin
    html = istemci.get("/bist/ASELS").get_data(as_text=True)
    assert "Şirket kendi payını geri alıyor" in html
    # Sektör etiketi, özet şeridi ve aynı sektördeki şirketler
    assert "Savunma" in html and "Aynı sektördeki şirketler" in html and "/bist/OTKAR" in html
    assert "ozet-serit" in html
    # Sektör ve endeks süzgeci
    html = istemci.get("/bist?sektor=TEKNOLOJİ").get_data(as_text=True)
    assert "/bist/ASELS" in html and 'href="/bist/THYAO"' not in html.split('id="hisseler"')[1].split('id="iceriden"')[0]
    assert "/bist/THYAO" in istemci.get("/bist?liste=xu030").get_data(as_text=True)
    # BIST 100 dışındaki şirketin de sayfası var (KAP listesinden)
    assert "Flap Kongre" in istemci.get("/bist/FLAP").get_data(as_text=True)
    assert istemci.get("/bist/YOKBOYLE").status_code == 404
    assert istemci.get("/bist/../etc").status_code == 404
    assert istemci.get("/api/bist/THYAO/fiyat").status_code == 200


def test_bist_arama(istemci):
    oneriler = istemci.get("/api/oneri?q=thyao").get_json()["oneriler"]
    assert oneriler[0]["adres"] == "/bist/THYAO"
    assert istemci.get("/api/oneri?q=aselsan").get_json()["oneriler"][0]["adres"] == "/bist/ASELS"


def test_haberlerde_hisse_kodlari(uygulama):
    from piyasa.web.hisse_kodlari import _kodlar, hisse_kodlari
    _kodlar.temizle()
    assert hisse_kodlari("THYAO ve ASELS zirvede, BIST 100 rekor") == [("THYAO", "/bist/THYAO"), ("ASELS", "/bist/ASELS")]
    assert hisse_kodlari("Nvidia (NVDA) yükseldi") == [("NVDA", "/hisse/NVDA")]
    assert hisse_kodlari("ALTIN ve DOLAR") == []
