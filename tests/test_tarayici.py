"""
Gerçek tarayıcıda (başsız Chrome) tıklama testleri: menüler, aramalar,
seçim kutuları, sıralama, süzme, tıklanabilir satırlar, fiyat grafiği.
Chrome ya da selenium yoksa atlanır.

    python -m pytest tests/test_tarayici.py
"""

import threading
from urllib.parse import parse_qs, urlparse

import pytest

selenium = pytest.importorskip("selenium")
from selenium import webdriver  # noqa: E402
from selenium.webdriver.common.action_chains import ActionChains  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402
from selenium.webdriver.common.keys import Keys  # noqa: E402
from selenium.webdriver.support import expected_conditions as EC  # noqa: E402
from selenium.webdriver.support.ui import Select, WebDriverWait  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402


@pytest.fixture(scope="module")
def sunucu(uygulama):
    srv = make_server("127.0.0.1", 0, uygulama, threaded=True)
    is_parcacigi = threading.Thread(target=srv.serve_forever, daemon=True)
    is_parcacigi.start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.fixture(scope="module")
def tarayici():
    ayar = webdriver.ChromeOptions()
    ayar.add_argument("--headless=new")
    ayar.add_argument("--window-size=1366,1000")
    ayar.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    try:
        surucu = webdriver.Chrome(options=ayar)
    except Exception as hata:  # Chrome kurulu değilse
        pytest.skip(f"Chrome başlatılamadı: {hata}")
    yield surucu
    surucu.quit()


def bekle(tarayici, kosul, sure=6):
    return WebDriverWait(tarayici, sure).until(kosul)


def tikla(tarayici, oge):
    """Öğeyi ekranın ortasına kaydırıp tıklar (yapışkan üst çubuk örtmesin)."""
    tarayici.execute_script("arguments[0].scrollIntoView({block: 'center'})", oge)
    oge.click()


def sorgu(tarayici):
    return {k: v[0] for k, v in parse_qs(urlparse(tarayici.current_url).query).items()}


@pytest.fixture(autouse=True)
def js_hatasi_olmasin(tarayici):
    """Her testten sonra tarayıcı konsolunda JavaScript hatası olmamalı."""
    tarayici.get_log("browser")  # önceki kayıtları temizle
    yield
    hatalar = [
        k for k in tarayici.get_log("browser")
        if k["level"] == "SEVERE"
        and "fonts.g" not in k["message"]      # çevrimdışı yazı tipi isteği
        and "/api/fiyat/YOK" not in k["message"]  # bilerek 404 dönen fiyat
    ]
    assert not hatalar, hatalar


def test_ana_menu_baglantilari(tarayici, sunucu):
    beklenen = {
        "Siyasetçiler": "Siyasetçilerin hisse işlemleri",
        "Yöneticiler": "Şirket yöneticilerinin işlemleri",
        "Fonlar": "Fonlar ve bankalar",
        "Emtialar": "Emtialar",
        "Günlük özet": "",
        "Sinyaller": "Sinyaller",
        "Ana sayfa": "ABD'de kim hangi hisseyi aldı, sattı?",
    }
    tarayici.get(sunucu + "/")
    for etiket, baslik in beklenen.items():
        tarayici.find_element(By.CSS_SELECTOR, ".ana-menu").find_element(By.LINK_TEXT, etiket).click()
        bekle(tarayici, EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), baslik))
        aktif = tarayici.find_element(By.CSS_SELECTOR, '.ana-menu [aria-current="page"]')
        assert aktif.text == etiket


def test_ana_sayfa_kartlari_ve_arama(tarayici, sunucu):
    tarayici.get(sunucu + "/")
    for kart in range(3):
        kartlar = tarayici.find_elements(By.CSS_SELECTOR, ".kaynak-kart")
        adres = kartlar[kart].get_attribute("href")
        kartlar[kart].click()
        bekle(tarayici, EC.url_to_be(adres))
        tarayici.back()

    tarayici.find_element(By.CSS_SELECTOR, ".hisse-kart").click()
    bekle(tarayici, EC.url_contains("/hisse/"))

    tarayici.get(sunucu + "/")
    kutu = tarayici.find_element(By.CSS_SELECTOR, ".giris-arama input[name=q]")
    kutu.send_keys("NVDA")
    tarayici.find_element(By.CSS_SELECTOR, ".giris-arama button").click()
    bekle(tarayici, EC.url_contains("/islemler"))
    assert sorgu(tarayici)["q"] == "NVDA"
    assert tarayici.find_elements(By.CSS_SELECTOR, ".islem-tablosu tbody tr")


def test_ust_arama_ve_kisayol(tarayici, sunucu):
    tarayici.get(sunucu + "/fonlar")
    # Başsız Chrome tuşu makinenin klavye düzenine göre çeviriyor (Türkçe
    # Q'da "/" → "&"); olayı doğrudan göndermek düzenden bağımsız
    tarayici.execute_script("document.dispatchEvent(new KeyboardEvent('keydown', {key: '/'}))")
    odak = tarayici.switch_to.active_element
    assert odak.get_attribute("id") == "genel-arama"
    odak.send_keys("Jane")
    # Öneri listesi açılır; hiçbirini seçmeden Enter normal arama yapar
    bekle(tarayici, EC.visibility_of_element_located((By.CSS_SELECTOR, ".ust-arama .oneri-listesi")))
    odak.send_keys(Keys.ENTER)
    bekle(tarayici, EC.url_contains("q=Jane"))
    assert "Jane Senator" in tarayici.page_source


def test_islem_filtreleri(tarayici, sunucu):
    tarayici.get(sunucu + "/islemler?kaynak=yonetici")
    for ad, deger in (("islem", "buy"), ("donem", "90"), ("sira", "tutar"), ("kaynak", "siyasetci")):
        secim = tarayici.find_element(By.CSS_SELECTOR, f'#filtre-formu select[name="{ad}"]')
        Select(secim).select_by_value(deger)
        bekle(tarayici, lambda t, ad=ad, deger=deger: sorgu(t).get(ad) == deger)

    # Arama kutusu Enter ile gönderilir
    kutu = tarayici.find_element(By.ID, "search")
    kutu.send_keys("Jane", Keys.ENTER)
    bekle(tarayici, lambda t: sorgu(t).get("q") == "Jane")

    tarayici.find_element(By.LINK_TEXT, "Filtreleri temizle").click()
    bekle(tarayici, lambda t: "q" not in sorgu(t))


def test_sayfalama_dugmeleri(tarayici, sunucu):
    tarayici.get(sunucu + "/islemler?kaynak=yonetici")
    tarayici.find_element(By.LINK_TEXT, "Sonraki →").click()
    bekle(tarayici, EC.text_to_be_present_in_element((By.CLASS_NAME, "sayfa-bilgi"), "Sayfa 2 / 2"))
    assert sorgu(tarayici)["kaynak"] == "yonetici"
    tarayici.find_element(By.LINK_TEXT, "← Önceki").click()
    bekle(tarayici, EC.text_to_be_present_in_element((By.CLASS_NAME, "sayfa-bilgi"), "Sayfa 1 / 2"))


def test_tablo_baglantilari(tarayici, sunucu):
    tarayici.get(sunucu + "/islemler?kaynak=siyasetci")
    satir = tarayici.find_element(By.CSS_SELECTOR, ".islem-tablosu tbody tr")
    belge = satir.find_element(By.CLASS_NAME, "kaynak")
    assert belge.get_attribute("target") == "_blank"
    assert belge.get_attribute("href").startswith("https://")

    satir.find_element(By.CLASS_NAME, "ticker").click()
    bekle(tarayici, EC.url_contains("/hisse/"))
    tarayici.back()
    tarayici.find_element(By.CSS_SELECTOR, ".islem-tablosu .kisi-ad").click()
    bekle(tarayici, EC.url_contains("/kisi/"))


def test_siyasetci_tablosu(tarayici, sunucu):
    tarayici.get(sunucu + "/siyasetciler")
    adlar = lambda: [h.get_attribute("textContent") for h in tarayici.find_elements(  # noqa: E731
        By.CSS_SELECTOR, "#siyasetci-tablosu tbody tr:not([hidden]) .kisi-ad")]

    # Sıralama: Üye başlığı A→Z / Z→A
    uye = tarayici.find_element(By.XPATH, "//th[normalize-space()='Üye']")
    uye.click()
    ilk = adlar()
    uye.click()
    assert adlar() == list(reversed(ilk))

    # Süzme
    tarayici.find_element(By.ID, "tablo-suz").send_keys("jane")
    bekle(tarayici, lambda t: adlar() == ["Jane Senator"])

    # Parti seçimi
    tarayici.find_element(By.PARTIAL_LINK_TEXT, "Cumhuriyetçi").click()
    bekle(tarayici, lambda t: sorgu(t).get("parti") == "R")
    assert adlar() == ["Bob Rep"]

    # Satırın boş bir yerine tıklamak kişi sayfasını açar
    tarayici.find_element(By.CSS_SELECTOR, "#siyasetci-tablosu tbody tr td:nth-child(2)").click()
    bekle(tarayici, EC.url_contains("/kisi/bob-rep"))


def test_hisse_fiyat_paneli(tarayici, sunucu):
    tarayici.get(sunucu + "/hisse/NVDA")
    bekle(tarayici, lambda t: "$" in t.find_element(By.CSS_SELECTOR, '[data-alan="fiyat"]').text)
    degisimler = tarayici.find_elements(By.CSS_SELECTOR, ".degisim .degisim-deger")
    assert len(degisimler) == 6
    assert all("%" in d.text for d in degisimler)
    hacim = tarayici.find_element(By.CSS_SELECTOR, '[data-alan="hacim"]')
    assert hacim.is_displayed() and "20 günlük ortalama" in hacim.text
    assert tarayici.find_elements(By.CSS_SELECTOR, ".fiyat-grafik .hacim-cubuklari rect")

    grafik = tarayici.find_element(By.CSS_SELECTOR, ".fiyat-grafik svg")
    for aralik in ("1a", "5y", "10y", "1y"):
        dugme = tarayici.find_element(By.CSS_SELECTOR, f'[data-aralik="{aralik}"]')
        dugme.click()
        assert dugme.get_attribute("aria-pressed") == "true"
        yeni = tarayici.find_element(By.CSS_SELECTOR, ".fiyat-grafik svg")
        assert yeni != grafik
        grafik = yeni

    # Fare grafiğin üzerine gelince ipucu görünür, çıkınca kaybolur
    ActionChains(tarayici).move_to_element(grafik).perform()
    ipucu = tarayici.find_element(By.CLASS_NAME, "grafik-ipucu")
    bekle(tarayici, lambda t: ipucu.is_displayed())
    assert "$" in ipucu.text
    ActionChains(tarayici).move_to_element(tarayici.find_element(By.TAG_NAME, "h1")).perform()
    bekle(tarayici, lambda t: not ipucu.is_displayed())

    # Bölüm menüsü sayfa içi bağlantıları
    tarayici.find_element(By.CSS_SELECTOR, '.bolum-menu a[href="#fonlar"]').click()
    bekle(tarayici, EC.url_contains("#fonlar"))
    tarayici.find_element(By.CSS_SELECTOR, "#fonlar tr.tiklanir td:nth-child(2)").click()
    bekle(tarayici, EC.url_contains("/fon/ornek-fon"))


def test_fiyati_olmayan_hisse(tarayici, sunucu):
    tarayici.get(sunucu + "/hisse/YOK")
    hata = tarayici.find_element(By.CSS_SELECTOR, '[data-alan="hata"]')
    bekle(tarayici, lambda t: hata.is_displayed())
    assert "bulunamadı" in hata.text
    assert not tarayici.find_element(By.CLASS_NAME, "fiyat-grafik-kap").is_displayed()
    # Fiyat olmasa da sayfanın geri kalanı çalışır
    assert tarayici.find_elements(By.CSS_SELECTOR, ".islem-tablosu tbody tr")


def test_fon_sayfasi(tarayici, sunucu):
    tarayici.get(sunucu + "/fonlar")
    tarayici.find_element(By.LINK_TEXT, "Örnek Fon").click()
    bekle(tarayici, EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Örnek Fon"))
    tarayici.find_element(By.LINK_TEXT, "CIKS").click()
    bekle(tarayici, EC.url_contains("/hisse/CIKS"))
    tarayici.find_element(By.LINK_TEXT, "Fonlar").click()
    bekle(tarayici, EC.url_contains("/fonlar"))


def test_telefon_gorunumu_tasmaz(tarayici, sunucu):
    tarayici.set_window_size(500, 900)
    try:
        for adres in ("/", "/islemler?kaynak=siyasetci", "/siyasetciler", "/hisse/NVDA",
                      "/emtialar", "/emtia/brent", "/siyasetciler/performans",
                      "/siyasetciler/cikar-catismasi", "/sinyaller", "/gunluk-ozet"):
            tarayici.get(sunucu + adres)
            genislik = tarayici.execute_script("return document.documentElement.scrollWidth")
            pencere = tarayici.execute_script("return window.innerWidth")
            assert genislik <= pencere, f"{adres}: sayfa {genislik}px, pencere {pencere}px"
    finally:
        tarayici.set_window_size(1366, 1000)


def test_geri_dugmesi_onceki_sayfaya_doner(tarayici, sunucu):
    # Filtreli listeden bir hisseye gidip geri dönünce aynı filtreler gelmeli
    tarayici.get(sunucu + "/islemler?kaynak=yonetici&islem=buy&sira=tutar")
    onceki = tarayici.current_url
    tarayici.find_element(By.CSS_SELECTOR, ".islem-tablosu .ticker").click()
    bekle(tarayici, EC.url_contains("/hisse/"))
    tikla(tarayici, tarayici.find_element(By.CSS_SELECTOR, "a.geri"))
    bekle(tarayici, EC.url_to_be(onceki))

    # Birkaç adım: ana sayfa → siyasetçiler → kişi → hisse, sonra geri geri
    tarayici.get(sunucu + "/")
    tarayici.find_element(By.CSS_SELECTOR, ".ana-menu").find_element(By.LINK_TEXT, "Siyasetçiler").click()
    bekle(tarayici, EC.url_contains("/siyasetciler"))
    tarayici.find_element(By.LINK_TEXT, "Jane Senator").click()
    bekle(tarayici, EC.url_contains("/kisi/jane-senator"))
    tarayici.find_element(By.CSS_SELECTOR, ".islem-tablosu .ticker").click()
    bekle(tarayici, EC.url_contains("/hisse/"))
    for beklenen in ("/kisi/jane-senator", "/siyasetciler", sunucu + "/"):
        tikla(tarayici, tarayici.find_element(By.CSS_SELECTOR, "a.geri"))
        bekle(tarayici, EC.url_contains(beklenen) if beklenen != sunucu + "/"
              else EC.url_to_be(beklenen))

    # Ana sayfada geri düğmesi yok
    assert not tarayici.find_elements(By.CSS_SELECTOR, "a.geri")


def test_geri_dugmesi_dogrudan_acilan_sayfada_ust_sayfaya_gider(tarayici, sunucu):
    # Geçmiş yokken (bağlantı dışarıdan açıldı) üst sayfaya gitmeli
    for adres, ust in (("/fon/ornek-fon", "/fonlar"), ("/kisi/jane-senator", "/siyasetciler"),
                       ("/hisse/NVDA", "/islemler")):
        tarayici.get("about:blank")
        tarayici.get(sunucu + adres)
        tikla(tarayici, tarayici.find_element(By.CSS_SELECTOR, "a.geri"))
        bekle(tarayici, EC.url_contains(ust))


def test_emtia_sayfalari(tarayici, sunucu):
    tarayici.get(sunucu + "/emtialar")
    tarayici.find_element(By.XPATH, "//a[contains(@class,'emtia-kart')][.//span[text()='Brent petrol']]").click()
    bekle(tarayici, EC.url_contains("/emtia/brent"))

    # Fiyat paneli, hacim ve grafik
    bekle(tarayici, lambda t: "$/varil" in t.find_element(By.CSS_SELECTOR, '[data-alan="fiyat"]').text)
    assert tarayici.find_element(By.CSS_SELECTOR, '[data-alan="hacim"]').is_displayed()

    # Fon konumu (çubuk) ve stok (çizgi) grafikleri çizilmiş olmalı
    assert tarayici.find_elements(By.CSS_SELECTOR, '[data-grafik-veri="cot-verisi"] rect.cubuk-arti')
    assert tarayici.find_elements(By.CSS_SELECTOR, '[data-grafik-veri="eia-verisi"] polyline')
    stok = tarayici.find_element(By.CSS_SELECTOR, '[data-grafik-veri="eia-verisi"] svg')
    ActionChains(tarayici).move_to_element(stok).perform()
    ipucu = tarayici.find_element(By.CSS_SELECTOR, '[data-grafik-veri="eia-verisi"] .grafik-ipucu')
    bekle(tarayici, lambda t: ipucu.is_displayed())
    assert "milyon varil" in ipucu.text

    # Bölüm menüsü ve haber bağlantıları
    tikla(tarayici, tarayici.find_element(By.CSS_SELECTOR, '.bolum-menu a[href="#haberler"]'))
    bekle(tarayici, EC.url_contains("#haberler"))
    haber = tarayici.find_element(By.CSS_SELECTOR, ".haberler a")
    assert haber.get_attribute("target") == "_blank"

    # Diğer emtialar ve geri düğmesi
    tikla(tarayici, tarayici.find_element(By.LINK_TEXT, "Altın"))
    bekle(tarayici, EC.url_contains("/emtia/altin"))
    tikla(tarayici, tarayici.find_element(By.CSS_SELECTOR, "a.geri"))
    bekle(tarayici, EC.url_contains("/emtia/brent"))

    # Fon tablosu satırı detay sayfasına gider
    tarayici.get(sunucu + "/emtialar")
    tikla(tarayici, tarayici.find_element(By.CSS_SELECTOR, "tr.tiklanir td:nth-child(2)"))
    bekle(tarayici, EC.url_contains("#arz-talep"))



def test_ana_menu_tasmaz(tarayici, sunucu):
    tarayici.get(sunucu + "/")
    menu = tarayici.find_element(By.CSS_SELECTOR, ".ana-menu")
    assert tarayici.execute_script("return arguments[0].scrollWidth <= arguments[0].clientWidth", menu)


def test_siyaset_sekmeleri_ve_performans(tarayici, sunucu):
    tarayici.get(sunucu + "/siyasetciler")
    tarayici.find_element(By.LINK_TEXT, "Kim piyasayı yendi?").click()
    bekle(tarayici, EC.url_contains("/siyasetciler/performans"))
    assert tarayici.find_element(By.CSS_SELECTOR, '.sekmeler [aria-current="page"]').text == "Kim piyasayı yendi?"
    tikla(tarayici, tarayici.find_element(By.CSS_SELECTOR, "#performans-tablosu tr.tiklanir td:nth-child(4)"))
    bekle(tarayici, EC.url_contains("/kisi/jane-senator"))

    tarayici.get(sunucu + "/siyasetciler/performans")
    tarayici.find_element(By.LINK_TEXT, "Çıkar çatışması").click()
    bekle(tarayici, EC.url_contains("/cikar-catismasi"))
    rozet = tarayici.find_element(By.CSS_SELECTOR, ".rozet-cakisma")
    assert "Teknoloji" in rozet.get_attribute("title")


def test_sinyaller_sayfasi(tarayici, sunucu):
    tarayici.get(sunucu + "/sinyaller")
    tikla(tarayici, tarayici.find_element(By.CSS_SELECTOR, '.sayfa-ust .bolum-menu a[href="#basari"]'))
    bekle(tarayici, EC.url_contains("#basari"))
    acilir = tarayici.find_elements(By.CSS_SELECTOR, "details.acilir summary")
    if acilir:
        tikla(tarayici, acilir[0])
        assert tarayici.find_element(By.CSS_SELECTOR, "details.acilir").get_attribute("open") is not None


def test_gunluk_ozet(tarayici, sunucu):
    tarayici.get(sunucu + "/gunluk-ozet")
    baslik = tarayici.find_element(By.TAG_NAME, "h1").text
    assert tarayici.find_element(By.ID, "ozet-metni").get_attribute("value").startswith("Piyasa Kaydı")

    # Kopyala: pano izni olsun olmasın kullanıcıya bir durum mesajı gösterilir
    tarayici.find_element(By.ID, "kopyala").click()
    bekle(tarayici, lambda t: t.find_element(By.ID, "kopyala-durum").text != "")

    # Önceki gün, sonra gün seçimiyle geri
    onceki = tarayici.find_elements(By.CSS_SELECTOR, 'a[rel="prev"]')
    if onceki:
        tikla(tarayici, onceki[0])
        bekle(tarayici, lambda t: t.find_element(By.TAG_NAME, "h1").text != baslik)
        secim = Select(tarayici.find_element(By.ID, "gun-sec"))
        secim.select_by_index(0)
        bekle(tarayici, lambda t: t.find_element(By.TAG_NAME, "h1").text == baslik)



def test_arama_onerileri_listesi(tarayici, sunucu):
    tarayici.get(sunucu + "/fonlar")
    kutu = tarayici.find_element(By.ID, "genel-arama")
    liste = tarayici.find_element(By.CSS_SELECTOR, ".ust-arama .oneri-listesi")

    # Yazarken liste açılır, ilk öneri NVDA; eşleşen kısım vurgulanır
    kutu.send_keys("nvid")
    bekle(tarayici, lambda t: liste.is_displayed() and "NVDA" in liste.text)
    assert kutu.get_attribute("aria-expanded") == "true"
    assert liste.find_element(By.CSS_SELECTOR, "mark").text.lower() == "nvid"

    # Esc kapatır
    kutu.send_keys(Keys.ESCAPE)
    bekle(tarayici, lambda t: not liste.is_displayed())

    # Klavye: ↓ ilk öneriyi seçer, Enter sayfasını açar
    kutu.send_keys("a")
    bekle(tarayici, lambda t: liste.is_displayed())
    kutu.clear()
    kutu.send_keys("nvid")
    bekle(tarayici, lambda t: liste.is_displayed() and "NVDA" in liste.text)
    kutu.send_keys(Keys.ARROW_DOWN)
    assert kutu.get_attribute("aria-activedescendant")
    kutu.send_keys(Keys.ENTER)
    bekle(tarayici, EC.url_contains("/hisse/NVDA"))

    # Fare: ana sayfadaki büyük arama kutusunda bir kişiye tıklama
    tarayici.get(sunucu + "/")
    kutu = tarayici.find_element(By.CSS_SELECTOR, ".giris-arama input")
    kutu.send_keys("jane")
    oge = bekle(tarayici, EC.visibility_of_element_located(
        (By.XPATH, "//ul[contains(@class,'oneri-listesi')]//li[contains(., 'Jane Senator')]")))
    oge.click()
    bekle(tarayici, EC.url_contains("/kisi/jane-senator"))

    # "Bütün işlemlerde ara" seçeneği formu gönderir
    tarayici.get(sunucu + "/")
    kutu = tarayici.find_element(By.CSS_SELECTOR, ".giris-arama input")
    kutu.send_keys("nvidia")
    hepsi = bekle(tarayici, EC.visibility_of_element_located((By.CSS_SELECTOR, ".giris-arama .oneri-hepsi")))
    hepsi.click()
    bekle(tarayici, lambda t: sorgu(t).get("q") == "nvidia")
