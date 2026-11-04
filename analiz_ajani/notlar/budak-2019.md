# Cemile Budak, Teknik Analiz İndikatörlerinin Performans Karşılaştırması Üzerine Bir Araştırma, Marmara Üni. YL tezi, 2019 (120 sayfa)

Dosya: `pdf/budak-2019.pdf`. Sayfa numaraları PDF sayfasıdır (tezin basılı numarası = PDF − 15). Okunan: 2.7 gösterge bölümü, araştırmalar, uygulama, sıralama tabloları, sonuç. Küme ve Electre yönteminin ders anlatımı (s. 61–72) ve dendrogram ayrıntısı yalnızca göz gezdirildi; grafikler okunmadı.

## Tezin yaptığı
- 28 BIST 30 hissesi, 01.11.2017 – 03.12.2018, TradingView grafikleri üzerinde 27 gösterge (s. 76–78).
- Bir sinyalden sonraki sinyale fiyat doğru yönde gittiyse "doğru" sayılır; yanlışlar dahil edilmez, getiri hesaplanmaz (s. 75, 78–79). Sayımı tek kişi gözle yapmıştır (s. 112).
- Doğru sinyal sayılarıyla hisseler kümelenir (Ward), her kümede göstergeler Electre ile sıralanır. Sonuç: DEMA, %R, CCI öne çıkar, MFI hep sonuncudur (s. 111).
- Tezin kendi sınırları: tek yıl, trend ayrımı yok, tek değerlendirici (s. 114).

## Değerlendirme: sıralama başarıyı değil sinyal sıklığını ölçüyor
- Birinci küme Tablo 6'da satır toplamı ile Tablo 10 sırası arasında Spearman 0,96. DEMA 274 doğru sinyalle birinci, MFI 43 ile sonuncu. Tez bunu "en çok yatırım fırsatı" diye tanımlar (s. 76), okur ise "en iyi gösterge" diye anlar.
- Tezin ölçütünü kendi verimizde, aynı dönem ve hisselerde tekrarladım (Yahoo, kapanışlar, gözle değil kodla):

| Gösterge | Sinyal | Doğru | Oran |
|---|---:|---:|---:|
| DEMA (9) | 2061 | 655 | %32 |
| 9 günlük ortalama | 1325 | 372 | %28 |
| %R | 966 | 590 | %61 |
| Bollinger | 584 | 364 | %62 |
| Stokastik 20/80 | 489 | 263 | %54 |
| MFI | 90 | 63 | %70 |
| RSI 30/70 | 120 | 88 | %73 |

  Doğru sayısında DEMA birinci, oranda MFI ve RSI öndedir; yani tezin birinciliği sıklıktan gelir. Oran da tek başına kanıt değildir: endeksin %16 düştüğü bu yılda SAT tarafı kolay "doğru" olur ve kazanç büyüklüğü ölçülmez.

## Tezdeki iç tutarsızlıklar
- **Küme numaraları karışmış.** Tablo 3'te (s. 103) 1. küme KCHOL, ISCTR, VAKBN… ve 3. küme AKBNK, BIMAS… Electre'de (s. 105–106) ve sonuçta (s. 113) ise 1. küme AKBNK, BIMAS…. "Mali kuruluşlar için DEMA, %R, CCI, DI" önerisi, Tablo 3'te mali ağırlıklı olan kümenin değil, tezin kendi Tablo 4'üne göre 13 hisseden yalnızca 4'ü mali olan AKBNK grubunun sonucudur.
- "Madencilik sektörünün tamamı 3. kümede" denir (s. 113–114), ama KOZAL ve KOZAA aynı paragrafta 1. kümededir.
- EKGYO Tablo 3 açıklamasında imalat, Tablo 4'te mali kuruluştur (s. 103–104). KOZAL, Koza Altın olduğu hâlde "kömür madenciliği" yazılmıştır.
- Bölüm 2'de RSI ve IMI aşırı bölgeden çıkışta sinyal verir (s. 45, 53); uygulamada aşırı bölgeye girişte (s. 87, 93). CCI'da da aynı fark var (s. 39, 84). MFI metninde iki yön de "satım" yazılmış (s. 90). Grafik 39'un başlığı DEMA yerine CCI'dır (s. 85).

## Koda geçenler (`kaynaklar/budak2019.py`)
17 yeni kural: DEMA, 9 günlük ortalama, %R, RSI aşırı bölgeye giriş, Bollinger'a değme, Aroon, Chaikin osilatörü, CMF, CMO, DMI, EOM, IMI, MFI, fiyat osilatörü, SMI, TRIX, regresyon eğimi.

Tez bu periyotları vermiyor, grafikleri TradingView'de çizdiğini söylüyor. Şu değerler o programın varsayılanları olduğunu hatırladığım, doğrulanmamış varsayımlardır: DEMA 9, Aroon 14, IMI 14, fiyat osilatörü 10/21, SMI 10/3/3, TRIX 18, EOM 14, regresyon 14. Tezde açıkça yazanlar: 9 günlük ortalama, Bollinger 20, CMF 21, CMO 14, DMI 14, MFI 14.

Eklenmeyenler:
- MACD, momentum, RSI 30/70, stokastik, CCI ±100: bizde zaten var.
- Talep Endeksi, RMI, RWI: tezde formül ya da uygulanabilir tanım yok (DI tezde üst sırada olsa da). Fiyat değişim oranı momentumla aynıdır.
- ADI "dip/tepe dönüşü" belirsiz. Williams A/D "sıfır kesişimi" birikimli serinin başlangıç gününe bağlıdır, geçmiş uzayınca sinyal değişir.
- "Aynı sektörde aynı gösterge çalışır": sınanmadı; dayandığı küme etiketleri yukarıdaki nedenle güvenilir değil.

## Sınama (2026-11-04)
Dönemler `ajan/donemler.py`. SAT'ta artı, hissenin gruptan geride kalmasıdır.

- **Tezin birincileri çalışmıyor:** DEMA AL +%0,08, SAT +%0,01; %R AL +%0,05, SAT +%0,16 (hepsi şans). Tezin sonuncusu MFI de şans. Yani gruba göre aralarında ölçülebilir fark yok.
- **Bollinger alt bandına değince almak ters çalışıyor:** olağan −%0,87 (p 0,020), 2012–2020 −%0,41 (p 0,003), kriz +%0,18. Holm'u geçmedi, ama iki bağımsız dönemde tekrarladı. Bu tezden çıkan en kullanışlı bulgu: alt bant tek başına alım sebebi değil. Bu yüzden rapordaki "tepki yükselişi sık görülür" cümlesi kaldırıldı. Teknik puanın dönüş bileşeni (`puanlama.py`, Bollinger %b) alt banda hâlâ puan veriyor; puan formülü ayrıca sınanmadan değiştirilmedi.
- **+DI/−DI aşağı kesişimi:** olağan +%1,20 (p 0,003), 2012–2020 +%0,34 (p 0,055), kriz −%0,60. Zayıf; öteki ortalama SAT kurallarıyla aynı olguyu ölçüyor.
- RSI 30 altına girişte almak olağan dönemde −%1,09 (p 0,016), eski yıllarda +%0,08: tekrarlamadı.
- Gedik 20/50 aşağı kesişimi, 98 sınamada da Holm'u geçen tek sinyal olarak kaldı (düzeltilmiş p 0,016).
- 98 sınamada 11 ham p < 0,05; yalnızca şansla yaklaşık 5 beklenir.
