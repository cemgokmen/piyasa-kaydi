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

## Kurulum

```bash
git clone https://github.com/cemgokmen/piyasa-kaydi.git
cd piyasa-kaydi

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
python database.py
```

`python database.py` tabloları oluşturur. Eski bir veritabanında
çalıştırılırsa eksik sütunları da ekler.

SEC, kendisine istek atan herkesin kimlik bildirmesini istiyor. Kendi adını
ve e-posta adresini ortam değişkeniyle ver:

```bash
export SEC_USER_AGENT="PiyasaKaydi ad@ornek.com"
```

Varsayılan değer `ayarlar.py` içinde.

## Veri çekme

**Yönetici işlemleri** — son 90 günde eksik olan günleri tamamlar:

```bash
python gecmis_veri.py
python supheli_bul.py
```

Kişi adresleri (`person_slug`) kayıt sırasında doldurulur. Bu özellikten
önce çekilmiş kayıtlar için bir kez `python slug_ekle.py` çalıştır.

İlk çalıştırma birkaç saat sürer. Yarıda kesilirse tekrar çalıştır,
tamamlanan günleri atlar.

**Fon pozisyonları** — çeyrekte bir yeterli:

```bash
python fon_toplayici.py
python cusip_ticker_bul.py
```

13F bildirimleri Şubat, Mayıs, Ağustos ve Kasım aylarının ortasında
yayımlanır.

## Çalıştırma

```bash
python app.py
```

`http://127.0.0.1:5001`

## Yapı

```
app.py               Flask sitesi: ana sayfa, hisse, kişi ve fon sayfaları
database.py          SQLite bağlantısı ve şema (data/kayitlar.db)
ayarlar.py           Ortak ayarlar (SEC_USER_AGENT)
slug.py              İsimleri adres dostu metne çevirir

toplayici.py         Son iş gününün Form 4 bildirimlerini çeker
gecmis_veri.py       Son 90 günün eksik günlerini tamamlar
supheli_bul.py       Anormal fiyatlı kayıtları işaretler (sitede gizlenir)
slug_ekle.py         Eski kayıtlara kişi adresi ekler
sutun_ekle.py        Eski veritabanına eksik sütunları ekler

fon_listesi.py       Takip edilen fonların adları
fon_ara.py           SEC'te isimle 13F veren kurum arar
fon_cik_bul.py       Fon adlarından CIK numaralarını bulur → data/fonlar.json
fon_toplayici.py     Fonların son 4 çeyreklik 13F bildirimlerini çeker
cusip_ticker_bul.py  CUSIP numaralarını hisse kodlarına eşler

destek_direnc.py     Destek/direnç modeli (deneysel, siteye bağlı değil)
sr_dene.py           Modeli birkaç hissede çalıştırır
sr_tarama.py         Modeli geniş bir hisse grubunda istatistiksel olarak sınar

templates/, static/  Sayfa şablonları, CSS ve JS
deneme/              İlk denemeler ve tek seferlik düzeltme scriptleri
data/                Veritabanı ve fon listesi
```

## Destek / direnç modeli (deneysel)

`destek_direnc.py` fiyat geçmişinden destek ve direnç bölgeleri çıkarır ve
her bölgenin geçmişte gerçekten tutunup tutunmadığını şansla karşılaştırır:
aynı seride rastgele çizilen seviyelerin tutunma oranı "şans oranı" kabul
edilir, bölgenin z-skoru buna göre hesaplanır.

```bash
python sr_dene.py AAPL NVDA          # günlük, son 5 yıl
python sr_tarama.py                  # haftalık, tüm geçmiş, 40 hisse
python sr_tarama.py 1d 5y            # günlük
```

Mesafeler ATR cinsindendir; günlük, haftalık ve aylık mumlar desteklenir.
Bu da yatırım tavsiyesi değildir.
