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

SEC, kendisine istek atan herkesin kimlik bildirmesini istiyor. Aşağıdaki
dosyalarda `USER_AGENT` satırını kendi e-posta adresinle değiştir:

`toplayici.py`, `fon_toplayici.py`, `fon_cik_bul.py`, `fon_ara.py`

## Veri çekme

**Yönetici işlemleri** — son 90 günde eksik olan günleri tamamlar:

```bash
python gecmis_veri.py
python supheli_bul.py
python slug_ekle.py
```

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