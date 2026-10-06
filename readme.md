# Piyasa Kaydı

ABD borsalarındaki resmî bildirimleri Türkçeleştirip okunur hale getiren bir
şeffaflık sitesi. Şirket yöneticilerinin hisse alım satımlarını ve büyük
fonların portföy pozisyonlarını gösterir.

Veriler doğrudan SEC EDGAR'dan çekilir. Her kaydın yanında kaynak belgeye
bağlantı vardır.

**Bu sitede yatırım tavsiyesi verilmez.** Yalnızca kamuya açık bildirimler
derlenir ve gösterilir.

## Ne gösteriyor

**Yönetici işlemleri (Form 4)**
Şirket yöneticileri ve %10'un üzerindeki ortaklar, hisse alım satımlarını
SEC'e bildirmek zorunda. Site yalnızca açık piyasa işlemlerini gösterir;
maaş kapsamında verilen hisseler ve opsiyon kullanımları listeye dahil
edilmez.

Her kayıtta işlem tarihi, bildirim tarihi ve aradaki **bildirim gecikmesi**
görünür.

**Fon ve banka pozisyonları (13F)**
100 milyon doların üzerinde varlık yöneten kurumlar, çeyreklik olarak
portföylerini bildirir. Site 34 büyük fon ve bankayı takip eder; çeyrekler
arası farkı hesaplayarak hangi hisseye girildiğini, hangisinden çıkıldığını
ve pozisyon değişimlerini gösterir.

**Emtialar**
Altın, gümüş, platin, bakır, WTI ve Brent petrol, doğal gaz, buğday ve mısır:
güncel fiyat, 1 gün – 10 yıl değişimler, hacim; büyük fonların net pozisyonu
(CFTC), ABD petrol ve doğal gaz stokları (EIA), Fed faiz kararları ve tahvil
faizleri (FRED), konuya göre etiketlenmiş Türkçe haberler (Google Haberler).
Altın sayfasında gram altının TL fiyatı da hesaplanır.

## Kurulum

```bash
git clone https://github.com/cemgokmen/piyasa-kaydi.git
cd piyasa-kaydi

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
python -m piyasa veritabani
```

`veritabani` komutu tabloları oluşturur; eski bir veritabanında eksik
sütunları da ekler.

SEC, kendisine istek atan herkesin kimlik bildirmesini istiyor. Kendi adını
ve e-posta adresini ortam değişkeniyle ver:

```bash
export SEC_USER_AGENT="PiyasaKaydi ad@ornek.com"
```

Varsayılan değer `piyasa/ayarlar.py` içinde.

## Kullanım

Bütün işler tek bir komut üzerinden yapılır. Komut listesi:
`python -m piyasa yardim`

```bash
python -m piyasa site          # siteyi başlatır → http://127.0.0.1:5001
python -m piyasa guncelle      # Form 4 + Kongre verisini günceller, şüphelileri işaretler
```

**Yönetici işlemleri (Form 4)** — son 90 günde eksik olan günleri, en
yeniden başlayarak tamamlar. Yarıda kesilirse tekrar çalıştır, tamamlanan
günleri atlar:

```bash
python -m piyasa form4
python -m piyasa supheli
```

**Kongre üyelerinin işlemleri** — varsayılan bu yıl; yıl verilebilir.
İşlenmiş bildirimleri atlar:

```bash
python -m piyasa kongre 2025 2026
```

**Emtia verileri** — fon konumları (CFTC, haftalık), stoklar (EIA, haftalık),
faizler (FRED, günlük). Fiyatlar ve haberler site açıkken canlı alınır:

```bash
python -m piyasa emtia
```

**Fon pozisyonları (13F)** — çeyrekte bir yeterli. Bildirimler Şubat, Mayıs,
Ağustos ve Kasım aylarının ortasında yayımlanır:

```bash
python -m piyasa fon
python -m piyasa cusip
```

## Testler

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Testler gerçek veritabanına ve internete dokunmaz; geçici bir örnek
veritabanı kurulur, fiyat servisi sahte veriyle değiştirilir.

- `tests/test_sayfalar.py` — her sayfa, 404'ler ve sitedeki bütün iç
  bağlantıların gezilmesi
- `tests/test_bicim.py` — tutar/tarih biçimleri, fiyat değişimi hesabı,
  Kongre bildirimi yardımcıları
- `tests/test_tarayici.py` — başsız Chrome'da menüler, arama, seçim
  kutuları, sıralama, süzme, tıklanabilir satırlar, fiyat grafiği ve
  telefon görünümü. Chrome yoksa atlanır.

## Yapı

```
app.py                     Siteyi başlatır (python app.py)
piyasa/
  __main__.py              Komut satırı: python -m piyasa <komut>
  ayarlar.py               Dosya yolları, SEC_USER_AGENT
  veritabani.py            SQLite bağlantısı ve şema (data/kayitlar.db)
  slug.py                  İsimleri adres dostu metne çevirir

  toplama/                 Resmî kaynaklardan veri indirenler
    form4.py               Form 4 ayrıştırma; son iş gününü indirir
    form4_gecmis.py        Eksik günleri paralel indirir
    kongre.py              House Clerk işlem bildirimleri (PDF)
    fon13f.py              Fonların 13F bildirimleri
    cusip.py               CUSIP → hisse kodu eşlemesi
    emtia.py               CFTC fon konumları, EIA stokları, FRED faizleri
    fon_listesi.py, fon_cik.py, fon_ara.py   Fon listesi ve CIK bulma

  bakim/                   Veritabanı bakımı
    supheli.py             Anormal fiyatlı kayıtları işaretler
    slug_ekle.py           Eski kayıtlara kişi adresi ekler
    sutun_ekle.py          Tabloları oluşturur, eksik sütunları ekler

  emtia/                   Emtialar
    tanimlar.py            Takip edilen emtialar, kodlar, birimler, etkenler
    sorgular.py            Fon konumu, stok ve faiz hesapları
    haberler.py            Türkçe haberler (Google Haberler RSS, 30 dk önbellek)

  analiz/                  Deneysel analizler (siteye bağlı değil)
    destek_direnc.py       Destek/direnç modeli
    sr_dene.py, sr_tarama.py

  web/                     Flask sitesi
    __init__.py            create_app()
    rotalar.py             Sayfalar (Blueprint); SQL içermez
    emtia_rotalari.py      Emtia sayfaları (Blueprint)
    sorgular.py            Bütün veritabanı sorguları
    bicim.py               Tutar, tarih biçimleri ve şablon süzgeçleri
    fiyat.py               Yahoo Finance fiyatları ve değişimler (15 dk önbellek)
    templates/, static/    Şablonlar, CSS, JS (grafik.js: ortak SVG grafik çizici)

tests/                     pytest testleri

deneme/                    İlk denemeler ve tek seferlik scriptler
data/                      Veritabanı ve fon listesi
```

## Destek / direnç modeli (deneysel)

`piyasa/analiz/destek_direnc.py` fiyat geçmişinden destek ve direnç bölgeleri çıkarır ve
her bölgenin geçmişte gerçekten tutunup tutunmadığını şansla karşılaştırır:
aynı seride rastgele çizilen seviyelerin tutunma oranı "şans oranı" kabul
edilir, bölgenin z-skoru buna göre hesaplanır.

```bash
python -m piyasa sr-dene AAPL NVDA      # günlük, son 5 yıl
python -m piyasa sr-tarama              # haftalık, tüm geçmiş, 40 hisse
python -m piyasa sr-tarama 1d 5y        # günlük
```

Mesafeler ATR cinsindendir; günlük, haftalık ve aylık mumlar desteklenir.
Bu da yatırım tavsiyesi değildir.
