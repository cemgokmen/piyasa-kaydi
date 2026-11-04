# Matriks, Teknik Analiz Modülleri (KHN Menüleri) Eğitim Dokümanı, 2020 (107 sayfa)

Dosya: `pdf/matriks-2020.pdf`. Sayfa numaraları PDF sayfasıdır. Metin 107 sayfanın tamamından çıkarıldı; ekran görüntüleri okunmadı.
Bu bir strateji kitabı değil, programın kullanım kılavuzudur. Doküman kendisi "yatırım önerisi değildir" der (s. 4) ve hiçbir kuralın başarısını iddia etmez.
Değeri iki yerdedir: programın hazır gelen beş göstergesi ve backtest uyarıları.

## Hazır sinyaller
- İndikatör Pozisyonları'nın beş hazır sütunu (s. 37): 5/22 ortalama kesişimi; RSI 30/70; yavaş stokastik çizgileri; fiyat osilatörü ve ortalaması; MACD ve sinyal çizgisi.
- Beşi birden AL ise satır maviye, SAT ise kırmızıya boyanır (s. 47).
- Hazır sistem `mtx_mov`: 3/10 basit ortalama kesişimi (s. 58–59). Tarama örneği: kapanışın 5 günlük ortalamayı kesmesi (s. 83).
- Gecikme: 5/14 üssel kesişiminde sinyalin "kalıcı" olması için 2 bar beklemek (s. 34–35).
- Fiyatın ortalama üstünde olması AL, altında olması SAT durumudur (s. 40). Kesişim tek gündür, durum ise sürer (s. 10).

## Backtest uyarıları ve bizdeki karşılığı

| Uyarı | Sayfa | Bizde |
|---|---|---|
| Sinyal, bar kapanana kadar geçicidir | 71, 97 | **Eksikti, eklendi.** Seans açıkken bugünkü sinyal "Geçici" yazılır ve oy vermez |
| Komisyon ve kayma girilmeli; 1–3 kademe kayıp olabilir | 71–73 | **Eksikti, eklendi.** Gidiş-dönüş binde 4'ü geçmeyen sonuç "Maliyeti karşılamıyor" olur. Kayma hariçtir |
| Az bar kullanmayın, göstergeler hatalı olur | 86 | Dönem sınaması buna göre yazıldı: gösterge bütün veriyle hesaplanır, dönem yalnızca sinyali seçer |
| Testi TL dışında (endeks, faiz, TÜFE, dolar) görün | 36, 65 | Kural sınaması grup ortalamasına göredir. Formasyon hedef oranları hâlâ nominal TL |
| Optimizasyon en yüksek getirili parametreyi seçer; walk-forward ayrı | 59–60, 67, 79 | Parametre aramıyoruz, kaynaktaki değerler sabit. Aşırı uyum riski bu yüzden düşük |
| Hareketli stop backtesti gerçekle örtüşmez | 62 | Kural sınamasında stop yok. Risk planındaki stoplar sınanmış değildir |
| Eski tarihli son sinyal yanıltır | 47 | Her kuralın `gecerlilik` süresi var |
| `LastValue` geleceği görebilir | 17 | Her kural geleceği görmeme testinden geçiyor |
| "Kâr hedefi ile SAT engelle" kullanmayın | 62–63 | Yok |

## Dokümandaki hatalar
- s. 62: 10 TL'den alınıp %1 hareketli stop konunca fiyat 11 TL olursa stop "9,9 TL" denmiş. Doğrusu 10,89 TL.
- s. 103: `fix(-8.8)` için −9 yazılmış, oysa metin fix'in küsuratı attığını söylüyor; −8 olmalı.
- s. 23: Dereceyi radyana çevirirken önce "180/π ile çarpılır" denmiş, sonraki satırda doğrusu (π/180) verilmiş.
- s. 101–102: `Input` örneği 100, 500, 150 değerleriyle yazılmış, açıklaması 1, 100, 10 diyor.

## Eklenmeyenler
- MOST (s. 88): adı geçiyor, formülü yok. `if(c>PREV,c-loss,c+loss)` (s. 104) `Prev` fonksiyonunun örneğidir, iddia değildir.
- Yazılım menüleri, alarm, emir gönderimi, şablon ve ekran anlatımları kural değildir.
- Fiyat osilatörünün periyodu dokümanda yok: 10/20 üssel ve 9 günlük ortalama bizim varsayımımızdır.

## Sınama (2026-11-04)

Kullanıcının uyarısı doğrulandı ve sınama dönemlere ayrıldı: 11 Eylül – 30 Ekim 2026'da endeks yaklaşık %25,6 düştü, bunu haberler fon soruşturmasına bağlıyor; 2 Mart 2026'da da İran savaşı sert düşüş getirmişti. Dönem sınırları sonuçlara bakılmadan yazıldı (`piyasa/analiz/ajan/donemler.py`):

- **Olağan dönem** 2020-11 – 2026-02-27: karar buradan çıkar.
- **Önceki yıllar** 2012 – 2020-10: bağımsız ikinci sınama.
- **Savaş ve fon krizi** 2026-03-02 sonrası: yalnızca karşılaştırma. Örnek küçük, yaklaşık 33 hafta.

Aynı anda iki hata da düzeltildi; ikisi de eski sonuçları etkiliyordu:
1. Yahoo bazı bedelsizleri işlemiyor (CCOLA 815 → 75, FENER, HEKTS, EUREN, TUKAS, CVKMD; ayrıca AYGAZ'da sıçrama). BIST'te günlük sınır %10 olduğu için %15'ten büyük sıçrama geçmişe yansıtılıyor. Bu düzeltme hisse raporunu ve taramayı da düzeltti.
2. 20–60 günlük getiriler haftalık örnekte çakışıyordu, p değerleri fazla iyimserdi. Newey-West kullanılıyor.

| Kanıt alan sinyal (olağan dönem) | Olağan | Önceki yıllar | Savaş ve fon krizi | Etiket |
|---|---|---|---|---|
| Gedik: 20/50 aşağı kesişimi | +%2,07 (Holm 0,011) | +%0,56 (p 0,045) | −%0,86 (p 0,45) | **Çalışıyor** |
| Matriks: beş gösterge SAT | +%0,95 (p 0,010) | +%0,48 (p 0,044) | −%0,54 (p 0,30) | Zayıf, tekrarladı |
| Matriks: 5/14 aşağı kesişimi | +%0,76 (p 0,002) | +%0,23 (p 0,075) | −%0,06 | Zayıf, aynı yön |
| Matriks: 5/14, 2 gün gecikmeli | +%0,47 (p 0,022) | +%0,20 (p 0,10) | +%0,30 | Zayıf, aynı yön |
| Gedik: 50 günlüğün altına iniş | +%0,81 (p 0,045) | +%0,26 (p 0,22) | −%0,14 | Zayıf, aynı yön |
| Altay: Williams, trend yönünde SAT | +%0,76 (p 0,049) | +%0,16 (p 0,42) | −%1,40 | Zayıf, aynı yön |
| Altay: Stokastik, trend yönünde AL | +%1,01 (p 0,027) | −%0,02 | +%1,33 (p 0,60) | Zayıf, **tekrarlamadı: oy yok** |

SAT'ta artı, hissenin aynı günkü gruptan geride kaldığı anlamına gelir. Açığa satış önerisi değildir: "elindeyse çık, alma" olarak okunur.

Okuma:
- **AL tarafında tekrarlayan tek kural yok.** Kanıtların hepsi SAT tarafında ve çoğu aynı olgunun değişik ölçümü: düşen ortalamalı hisse grubun gerisinde kalmaya devam ediyor. Birbirinden bağımsız 6 kanıt sayılmamalı.
- Kullanıcının uyarısı SAT kuralları için doğru çıktı: olağan dönemdeki avantaj savaş ve fon krizinde kayboldu. Sadece dönemi çıkarmak ise AL kurallarını kurtarmadı.
- Gecikme iddiası (s. 34) desteklenmedi: 2 gün beklemek SAT kazancını +%0,76'dan +%0,47'ye düşürdü.
- Duyarlılık: Şubat 2023 depremi ile 19 Mart 2025 şoku da çıkarılınca 20/50 "Çalışıyor" kaldı (+%2,17). `gedik.fiyat_ho50` ve `altay.williams_trend` ise "zayıf"tan şansa düştü. Bu sınama elle çalıştırıldı, sayfada yok.
- 64 sınamada 8 ham p < 0,05 var; yalnızca şansla yaklaşık 3 beklenir. Evren bugünkü BIST 100 olduğu için 2012–2020 sonucunda sağkalım yanlılığı daha da güçlüdür; grup kıyası bunu azaltır, sıfırlamaz.

Eski yıllarda ters çıkanlar: MACD'nin sıfır altında kesişimi AL (−%0,99, Holm'u geçti, ters), RSI 30 dönüşü AL (−%0,55).
