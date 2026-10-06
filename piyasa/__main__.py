"""
Piyasa Kaydı komut satırı.

Kullanım:
    python -m piyasa site                 siteyi başlatır (http://127.0.0.1:5001)
    python -m piyasa guncelle             tüm veriyi günceller (Form 4 + Kongre + emtia + bakım)

    python -m piyasa form4                son 90 günün eksik Form 4 günlerini indirir
    python -m piyasa kongre [yıl ...]     Temsilciler Meclisi işlemlerini indirir
    python -m piyasa fon                  fonların 13F bildirimlerini indirir
    python -m piyasa emtia                emtia verilerini indirir (CFTC, EIA, FRED)
    python -m piyasa fiyatlar             işlem yapılan hisselerin günlük fiyatlarını indirir
    python -m piyasa sirketler            şirket sektörleri ve Meclis komite üyelikleri
    python -m piyasa yurutme              Başkan ve Başkan Yardımcısının OGE bildirimleri
    python -m piyasa analiz               işlem sonrası getirileri hesaplar
    python -m piyasa cusip                13F CUSIP numaralarını hisse kodlarına eşler
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
    "fon": "piyasa.toplama.fon13f",
    "emtia": "piyasa.toplama.emtia",
    "fiyatlar": "piyasa.toplama.fiyat_gecmisi",
    "sirketler": "piyasa.toplama.sirketler",
    "yurutme": "piyasa.toplama.yurutme",
    "analiz": "piyasa.analiz.getiri",
    "cusip": "piyasa.toplama.cusip",
    "supheli": "piyasa.bakim.supheli",
    "slug": "piyasa.bakim.slug_ekle",
    "veritabani": "piyasa.bakim.sutun_ekle",
    "fon-ara": "piyasa.toplama.fon_ara",
    "fon-cik": "piyasa.toplama.fon_cik",
    "sr-dene": "piyasa.analiz.sr_dene",
    "sr-tarama": "piyasa.analiz.sr_tarama",
}

# 'guncelle' sırayla çalıştırılan adımlar
GUNCELLEME = ["form4", "kongre", "emtia", "slug", "supheli", "sirketler", "yurutme", "fiyatlar", "analiz"]


def calistir(komut, argumanlar):
    modul = importlib.import_module(KOMUTLAR[komut])
    # Modüller argümanlarını sys.argv'den okuyor
    sys.argv = [f"piyasa {komut}", *argumanlar]
    modul.main()


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "yardim"):
        print(__doc__)
        return

    komut, argumanlar = sys.argv[1], sys.argv[2:]

    if komut == "site":
        from piyasa.web import create_app
        create_app().run(debug="--uretim" not in argumanlar, port=5001)
    elif komut == "guncelle":
        for adim in GUNCELLEME:
            print(f"\n=== {adim} ===")
            calistir(adim, [])
    elif komut in KOMUTLAR:
        calistir(komut, argumanlar)
    else:
        print(f"Bilinmeyen komut: {komut}\n")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
