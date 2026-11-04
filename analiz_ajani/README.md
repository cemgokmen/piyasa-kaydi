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

## Kaynaklar

| Kaynak | Dosya | Notlar |
|---|---|---|
| Erdinç Altay, *Portföy Yönetiminde Karar Alma Aracı Olarak Teknik Analizin Kullanımı*, İÜ SBE YL tezi, 1997 | `pdf/altay-1997.pdf` | `notlar/altay-1997.md` |
| Gedik Yatırım, *Teknik Analiz Eğitim Sunumu*, Şubat 2021 | `pdf/gedik-2021.pdf` | `notlar/gedik-2021.md` |
