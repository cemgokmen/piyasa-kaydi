"""
Piyasa Kaydı komut satırı.

Kullanım:
    python -m piyasa site                 siteyi başlatır (http://127.0.0.1:5001)
    python -m piyasa site --ag            aynı Wi-Fi'daki telefondan da açılabilir
    python -m piyasa yayin                sitenin yayın sürümü (gunicorn); --kur ile Mac açılınca başlar
    python -m piyasa guncelle             tüm veriyi günceller (Form 4 + Kongre + emtia + bakım)
    python -m piyasa zamanla              güncellemeyi her sabah 07:30'da otomatik çalıştırır
                                          (--saat 6:15 ile saat, --kaldir ile kapatma)

    python -m piyasa form4                son 90 günün eksik Form 4 günlerini indirir
    python -m piyasa kongre [yıl ...]     Temsilciler Meclisi işlemlerini indirir
    python -m piyasa senato [yıl ...]     Senato işlemlerini indirir (yıl yoksa son 60 gün)
    python -m piyasa ihaleler [--hepsi]   şirketlere verilen devlet sözleşmeleri (USAspending.gov)
    python -m piyasa fon                  fonların 13F bildirimlerini indirir
    python -m piyasa emtia                emtia verilerini indirir (CFTC, EIA, FRED)
    python -m piyasa fiyatlar             işlem yapılan hisselerin günlük fiyatlarını indirir
    python -m piyasa sirketler            şirket sektörleri ve Meclis komite üyelikleri
    python -m piyasa yurutme              Başkan ve Başkan Yardımcısının OGE bildirimleri
    python -m piyasa yurutme-portfoy      yıllık bildirimden hisse portföyü ve işlemleri
    python -m piyasa analiz               işlem sonrası getirileri hesaplar
    python -m piyasa cusip                13F CUSIP numaralarını hisse kodlarına eşler
    python -m piyasa profiller [sayı]     hisse sayfalarındaki "Şirket hakkında" bilgisini doldurur
    python -m piyasa supheli              anormal fiyatlı kayıtları işaretler
    python -m piyasa slug                 eski kayıtlara kişi adresi ekler
    python -m piyasa veritabani           tabloları oluşturur / eksik sütunları ekler

    python -m piyasa fon-ara <isim>       SEC'te 13F veren kurum arar
    python -m piyasa fon-cik              fon listesinden CIK numaralarını bulur
    python -m piyasa sr-dene [kod ...]    destek/direnç modelini birkaç hissede dener
    python -m piyasa sr-tarama [aralık dönem]   modeli geniş bir hisse grubunda sınar
"""

import importlib
import sys

KOMUTLAR = {
    "form4": "piyasa.toplama.form4_gecmis",
    "form4-bugun": "piyasa.toplama.form4",
    "kongre": "piyasa.toplama.kongre",
    "senato": "piyasa.toplama.senato",
    "ihaleler": "piyasa.toplama.ihaleler",
    "fon": "piyasa.toplama.fon13f",
    "emtia": "piyasa.toplama.emtia",
    "fiyatlar": "piyasa.toplama.fiyat_gecmisi",
    "sirketler": "piyasa.toplama.sirketler",
    "yurutme": "piyasa.toplama.yurutme",
    "yurutme-portfoy": "piyasa.toplama.oge_yillik",
    "analiz": "piyasa.analiz.getiri",
    "zamanla": "piyasa.zamanlama",
    "yayin": "piyasa.yayin",
    "cusip": "piyasa.toplama.cusip",
    "profiller": "piyasa.toplama.profiller",
    "supheli": "piyasa.bakim.supheli",
    "slug": "piyasa.bakim.slug_ekle",
    "veritabani": "piyasa.bakim.sutun_ekle",
    "fon-ara": "piyasa.toplama.fon_ara",
    "fon-cik": "piyasa.toplama.fon_cik",
    "sr-dene": "piyasa.analiz.sr_dene",
    "sr-tarama": "piyasa.analiz.sr_tarama",
}

# 'guncelle' sırayla çalıştırılan adımlar
GUNCELLEME = ["form4", "kongre", "senato", "emtia", "slug", "supheli", "sirketler", "yurutme", "yurutme-portfoy", "fiyatlar", "profiller", "ihaleler", "analiz"]


def yerel_ip():
    """Bilgisayarın yerel ağdaki adresi (ör. 192.168.1.20)."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))   # paket gönderilmez; yalnızca çıkış arayüzü seçilir
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def calistir(komut, argumanlar):
    modul = importlib.import_module(KOMUTLAR[komut])
    # Modüller argümanlarını sys.argv'den okuyor
    sys.argv = [f"piyasa {komut}", *argumanlar]
    modul.main()


def guncelle(argumanlar=()):
    """
    Bütün adımları sırayla çalıştırır. Bir adım hata verirse (ör. bir kaynağa
    geçici olarak ulaşılamazsa) kalan adımlar yine çalışır; sonunda hata
    veren adımlar listelenir ve komut hata koduyla biter.

    --gerekirse [7:30]: günün güncellemesi zaten yapıldıysa hiçbir şey yapmadan
    çıkar (zamanlanmış görev bunu saat başı çalıştırır; bkz. piyasa/zamanlama.py).
    """
    from datetime import datetime

    from piyasa import zamanlama

    saat, dakika = 7, 30
    if "--gerekirse" in argumanlar:
        sira = list(argumanlar).index("--gerekirse")
        if sira + 1 < len(argumanlar) and ":" in argumanlar[sira + 1]:
            saat, dakika = (int(x) for x in argumanlar[sira + 1].split(":"))
        if not zamanlama.gerekli_mi(datetime.now(), zamanlama.durum_oku(), saat, dakika):
            return

    with zamanlama.tek_guncelleme() as kilit:
        if not kilit:
            print("Başka bir güncelleme sürüyor; bu çalıştırma atlandı.", flush=True)
            return
        hatalar = adimlari_calistir()
    zamanlama.durum_yaz(datetime.now(), not hatalar, hatalar, saat, dakika)
    if hatalar:
        print(f"\nHata veren adımlar: {', '.join(hatalar)}", flush=True)
        sys.exit(1)
    print(f"\n##### Güncelleme bitti: {datetime.now():%Y-%m-%d %H:%M} #####", flush=True)


def adimlari_calistir():
    """GUNCELLEME adımlarını sırayla çalıştırır; hata veren adımların listesini döndürür."""
    import time
    import traceback
    from datetime import datetime

    print(f"\n##### Güncelleme başladı: {datetime.now():%Y-%m-%d %H:%M} #####", flush=True)
    hatalar = []
    for adim in GUNCELLEME:
        baslangic = time.time()
        print(f"\n=== {adim} ===", flush=True)
        try:
            calistir(adim, [])
        except Exception:
            traceback.print_exc()
            hatalar.append(adim)
        print(f"--- {adim}: {time.time() - baslangic:.0f} sn", flush=True)

    return hatalar


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "yardim"):
        print(__doc__)
        return

    komut, argumanlar = sys.argv[1], sys.argv[2:]

    if komut == "site":
        from piyasa.web import create_app
        if "--ag" in argumanlar:
            # Aynı Wi-Fi'daki telefon ve bilgisayarlar açabilsin. Hata ayıklayıcı
            # ağda kod çalıştırmaya izin verdiği için bu modda kapalıdır.
            ip = yerel_ip()
            print(f"\nAynı Wi-Fi'daki cihazlardan açın:  http://{ip}:5001\n")
            create_app().run(host="0.0.0.0", port=5001, debug=False, threaded=True)
        else:
            create_app().run(debug="--uretim" not in argumanlar, port=5001)
    elif komut == "guncelle":
        guncelle(argumanlar)
    elif komut in KOMUTLAR:
        calistir(komut, argumanlar)
    else:
        print(f"Bilinmeyen komut: {komut}\n")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
