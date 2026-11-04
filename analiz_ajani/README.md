# Analiz ajanı

Analiz ajanının öğrendiği kaynaklar.

- `pdf/` tezler, kitaplar ve eğitim dosyalarının aslı. Telif ve boyut nedeniyle git'e girmez; bu klasör yalnızca bu Mac'te ve iCloud'da durur.
- `notlar/` her kaynaktan çıkarılan notlar ve sınama sonuçları (`<yazar>-<yıl>.md`, sayfa numaralarıyla).

## Yeni kaynak ekleme

1. Dosya `pdf/` klasörüne konur, notlar `notlar/<yazar>-<yıl>.md` dosyasına yazılır.
2. Sınanabilir iddialar `piyasa/analiz/ajan/kaynaklar/<yazar><yıl>.py` dosyasına `@kural` ile eklenir. Dosya kendiliğinden yüklenir.
3. `python -m piyasa ajan-sina` kuralları sınar. Sonuç `/analiz` ve hisse raporunda kaynağıyla görünür.

Kaynağın söylediği iddiadır, doğru kabul edilmez. Teknik puan ve destek/direnç gücü ancak sınamada iyileşiyorsa değiştirilir;
sonuç not dosyasına yazılır.

## Sınama dönemleri

Karar olağan dönemden çıkar; İran savaşı (Mart 2026) ve fon soruşturması (Eylül 2026) dışarıdadır. 2012–2020 bağımsız ikinci sınamadır,
orada ters çıkan kural oy vermez. Sınırlar `piyasa/analiz/ajan/donemler.py` dosyasındadır ve sonuca bakılarak değiştirilmez.

## Kaynaklar

| Kaynak | Dosya | Notlar |
|---|---|---|
| Erdinç Altay, *Portföy Yönetiminde Karar Alma Aracı Olarak Teknik Analizin Kullanımı*, İÜ SBE YL tezi, 1997 | `pdf/altay-1997.pdf` | `notlar/altay-1997.md` |
| Gedik Yatırım, *Teknik Analiz Eğitim Sunumu*, Şubat 2021 | `pdf/gedik-2021.pdf` | `notlar/gedik-2021.md` |
| Matriks, *Teknik Analiz Modülleri (KHN Menüleri) Eğitim Dokümanı*, 2020 | `pdf/matriks-2020.pdf` | `notlar/matriks-2020.md` |
| Cemile Budak, *Teknik Analiz İndikatörlerinin Performans Karşılaştırması*, Marmara Üni. YL tezi, 2019 | `pdf/budak-2019.pdf` | `notlar/budak-2019.md` |
