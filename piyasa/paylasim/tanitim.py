"""
Tanıtım gönderisi: sitenin önemli bölümlerini anlatan slaytlar (1600×900), X zinciri metinleri,
profil kapağı (1500×500) ve profil fotoğrafı (400×400).

Slaytlar sitenin gerçek ekran görüntüleriyle hazırlanır:
    python -m piyasa tanitim        sayfaların ekran görüntüsünü alır ve görselleri data/tanitim/ altına üretir

Gerekenler: site çalışıyor olmalı (http://127.0.0.1:5001) ve Chrome ile selenium kurulu olmalı.
Görseller yalnızca yerel paylaşım sayfasından (/paylasim/tanitim) indirilir.
"""

import sys
import time

from piyasa.ayarlar import VERI_DIZINI

KLASOR = VERI_DIZINI / "tanitim"
SITE = "http://127.0.0.1:5001"

# Ekran görüntüsü alınacak sayfalar: (ad, adres, en üste kaydırılacak öğe)
EKRANLAR = [
    ("anasayfa", "/", None),
    ("bist", "/bist", None),
    ("bist_hisse", "/bist/THYAO", None),
    ("hisse", "/hisse/NVDA", None),
    ("siyasetci", "/kisi/nancy-pelosi", None),
    ("sinyaller", "/sinyaller", None),
    ("ozet", "/gunluk-ozet", ".ozet-manset"),
    ("karsilastir", "/yatirim-karsilastir", ".kars-sonuc"),
    ("canli", "/canli", None),
]

SLAYTLAR = [
    {"ad": "01-kapak", "tur": "kapak", "ekran": "anasayfa",
     "ust": "piyasakaydi.com",
     "baslik": "Kim aldı, kim sattı?",
     "alt": "Borsa İstanbul'dan Wall Street'e; şirket yöneticilerinin, büyük ortakların ve siyasetçilerin "
            "hisse işlemleri. Resmi kaynaklardan, sade Türkçe."},
    {"ad": "02-bist", "ekran": "bist", "ust": "Borsa İstanbul",
     "baslik": "KAP'ta kim ne aldı?",
     "maddeler": ["650 hissenin fiyatı, sektörü ve günün hareketi",
                  "Yöneticilerin ve büyük ortakların bildirdiği alım satımlar",
                  "Şirketlerin kendi hisselerini geri alımları"]},
    {"ad": "03-hisse", "ekran": "bist_hisse", "ust": "Hisse sayfaları",
     "baslik": "Her hisse tek sayfada",
     "maddeler": ["Şirket ne iş yapar, temel rakamlar ve fiyat grafiği",
                  "Hisseyi kimler tutuyor: ortaklar ve fonlar",
                  "İçeriden işlemler ve KAP açıklamaları"]},
    {"ad": "04-siyasetci", "ekran": "siyasetci", "ust": "ABD Kongresi",
     "baslik": "Siyasetçiler ne alıyor?",
     "maddeler": ["133 Kongre üyesinin yasal hisse bildirimleri",
                  "Aldıkları hisseler sonra piyasayı yendi mi?",
                  "Komitesinin denetlediği sektörde işlem yapanlar"]},
    {"ad": "05-sinyaller", "ekran": "sinyaller", "ust": "Sinyaller",
     "baslik": "Aynı hisseye kim yöneldi?",
     "maddeler": ["Yöneticiler, siyasetçiler ve dev fonlar aynı hissede buluşunca",
                  "Bu sinyaller geçmişte işe yaradı mı? İstatistikle sınanır"]},
    {"ad": "06-ozet", "ekran": "ozet", "ust": "Günün özeti",
     "baslik": "Günün özeti, tek sayfada",
     "maddeler": ["Piyasa göstergeleri ve günün manşeti",
                  "Yedi kaynaktan konularına göre finans haberleri",
                  "Borsa İstanbul ve ABD'de günün önemli işlemleri"]},
    {"ad": "07-karsilastir", "ekran": "karsilastir", "ust": "Yatırım karşılaştırma",
     "baslik": "10 yıl önce yatırsaydınız?",
     "maddeler": ["Dolar, altın, borsa, Bitcoin ve istediğiniz hisse",
                  "Enflasyondan arındırılmış gerçek getiri",
                  "Tek seferlik ya da her ay düzenli yatırım"]},
    {"ad": "08-canli", "ekran": "canli", "ust": "Canlı akış",
     "baslik": "Bildirimler, yayımlandıkça",
     "maddeler": ["ABD'de yönetici bildirimleri ve KAP açıklamaları tek akışta",
                  "Borsa İstanbul'da günün en çok yükselenleri ve düşenleri"]},
    {"ad": "09-kapanis", "tur": "kapanis", "ekran": "hisse", "ust": "",
     "baslik": "piyasakaydi.com",
     "alt": "Ücretsiz · Türkçe · Resmi kaynaklardan (KAP, SEC, ABD Kongresi)"},
]

# X zinciri: (metin, slayt adları). Bir gönderide en çok 4 görsel.
ZINCIR = [
    ("Piyasa Kaydı yayında: piyasakaydi.com\n\n"
     "Şirket yöneticileri, büyük ortaklar ve siyasetçiler hisse alıp sattığında bunu yasa gereği açıklamak zorunda. "
     "Biz bu bildirimleri KAP'tan, SEC'ten ve ABD Kongresi'nden topluyor, sade Türkçe ile tek yerde sunuyoruz.\n\n"
     "Neler var, kısaca 🧵",
     ["01-kapak", "02-bist", "03-hisse", "04-siyasetci"]),
    ("Borsa İstanbul'da 650 hisse: KAP'a bildirilen içeriden alım satımlar, geri alımlar ve hisseyi kimlerin tuttuğu.\n\n"
     "ABD'de şirket yöneticilerinin Form 4 bildirimleri ve 133 Kongre üyesinin hisse işlemleri; "
     "aldıkları hisselerin sonra piyasayı yenip yenmediğiyle birlikte.",
     ["05-sinyaller", "06-ozet", "07-karsilastir", "08-canli"]),
    ("Her gün güncellenen günün özeti, yedi kaynaktan finans haberleri, canlı akış ve "
     "\"10 yıl önce yatırsaydınız?\" karşılaştırması.\n\n"
     "Ücretsiz, üyelik gerektirmez. Yatırım tavsiyesi değildir.\n\npiyasakaydi.com",
     ["09-kapanis"]),
]

PROFIL = {
    "ad": "Piyasa Kaydı",
    "kullanici": "@piyasakaydi",
    "bio_secenekleri": [
        "Kim aldı, kim sattı? Borsa İstanbul ve ABD'de yönetici, büyük ortak ve siyasetçi hisse işlemleri; "
        "günün finans haberleri. Yatırım tavsiyesi değildir.",
        "KAP, SEC ve ABD Kongresi bildirimlerinden içeriden işlemler, geri alımlar ve günün piyasa haberleri. "
        "Sade Türkçe, her gün. Yatırım tavsiyesi değildir.",
        "Borsada içeriden kim ne aldı? Yönetici ve büyük ortak işlemleri, siyasetçilerin hisseleri, günün özeti. "
        "Yatırım tavsiyesi değildir.",
    ],
    "konum": "İstanbul",
    "site": "piyasakaydi.com",
    "sabit_gonderi": "Tanıtım zincirinin ilk gönderisini profilde sabitleyin.",
}


def ekran_goruntuleri(surucu):
    (KLASOR / "ekran").mkdir(parents=True, exist_ok=True)
    surucu.set_window_size(1440, 900)
    surucu.get(SITE + "/")
    surucu.execute_script("localStorage.setItem('tema', 'koyu')")
    for ad, adres, oge in EKRANLAR:
        surucu.get(SITE + adres)
        time.sleep(2.5)
        surucu.execute_script("""
            document.querySelectorAll('.geri, .alt-gezinti, .serit').forEach(e => e.style.display = 'none');
            window.scrollTo(0, 0);
            const o = arguments[0] && document.querySelector(arguments[0]);
            if (o) window.scrollTo(0, o.getBoundingClientRect().top + scrollY - 90);""", oge)
        time.sleep(0.8)
        surucu.save_screenshot(str(KLASOR / "ekran" / f"{ad}.png"))
        print(f"  ekran: {ad}", flush=True)


def gorselleri_uret(surucu):
    """Slaytlar ve profil görselleri: yerel sitedeki slayt sayfaları tam boyutta fotoğraflanır."""
    isler = [(s["ad"], 1600, 900) for s in SLAYTLAR] + [("profil-kapak", 1500, 500), ("profil-foto", 400, 400)]
    for ad, en, boy in isler:
        surucu.set_window_size(en, boy + 200)
        surucu.get(f"{SITE}/paylasim/tanitim/slayt/{ad}")
        time.sleep(1.2)
        oge = surucu.find_element("css selector", "#slayt")
        oge.screenshot(str(KLASOR / f"{ad}.png"))
        print(f"  görsel: {ad}", flush=True)


def main():
    try:
        from selenium import webdriver
    except ImportError:
        print("selenium kurulu değil: pip install -r requirements-dev.txt")
        sys.exit(1)
    ayar = webdriver.ChromeOptions()
    ayar.add_argument("--headless=new")
    ayar.add_argument("--hide-scrollbars")
    ayar.add_argument("--force-device-scale-factor=2")       # net görseller (2×)
    surucu = webdriver.Chrome(options=ayar)
    try:
        KLASOR.mkdir(parents=True, exist_ok=True)
        ekran_goruntuleri(surucu)
        gorselleri_uret(surucu)
    finally:
        surucu.quit()
    print(f"Tanıtım görselleri hazır: {KLASOR}")


if __name__ == "__main__":
    main()
