# Gedik Yatırım, Teknik Analiz Eğitim Sunumu, Şubat 2021 (40 slayt)

Dosya: `pdf/gedik-2021.pdf`. Sayfa numaraları PDF sayfasıdır. Yöntemi anlatan bir giriş sunumudur; kendi sınaması yoktur.

## Varsayımlar ve strateji (s. 3–8)
- Üç varsayım: fiyat her şeyi yansıtır, fiyat anlamlı süre trendde gider, tarih tekerrür eder.
- Vade, kazanç oranı ve sistem belli değilse "yalnızca fiyatların iniş çıkışını izlersiniz".
- Ana trend en az 1–2 yıl; ara trend ana trendi bozmaz; kısa vadeli trend küçük hareketlerdir.

## Trend, kanal, destek ve direnç (s. 13–21)
- Trend, en az iki noktadan geçen doğrudur: artan, azalan, yatay.
- Kanal: trend çizgisinin paraleli, karşı uçtan çizilir (s. 17–18).
- Sağlamlık (s. 20): geçtiği tepe/dip sayısı arttıkça, süresi uzadıkça sağlamlaşır. Eğimi yatay çizgi kırılınca daha çok düşer, dik çizgi kırılınca az düşer; bu yüzden "dik çizgi daha güvenilirdir".
- Tuzak (s. 21): artan trendi aşağı kırıp içine dönen ayı tuzağı, azalan trendi yukarı kırıp içine dönen boğa tuzağıdır. Tuzakta hacim artmaz, azalır.

## Hareketli ortalamalar (s. 22–23)
- Vade: uzun 100–200, orta 30–100, kısa 5–30, çok kısa 5–15 gün.
- Üç kullanım: fiyatın ortalamayı kesmesi; kısa ve uzun ortalamanın kesişmesi; aynı vadede iki yöntemin (basit, üssel) kesişmesi.

## Fibonacci (s. 25–28)
- %0, 23,6, 38,2, 50, 61,8, 100. Yükselişte tepeden çıkarılır, düşüşte dibe eklenir. Örnek: dip 4400, tepe 7500 → %61,8 seviyesi 6316.

## Formasyonlar (s. 7, 29–37)
- Üçgen: simetrikte yön söylenemez, kırılış beklenir. Artan genellikle yukarı, azalan aşağı kırılır.
- Üçgen hedefi "en az gidilecek nokta": ilk köşeden karşı kenarın paraleli (s. 33).
- Bayrak: X kadar yükselişten sonra bayrak kırılınca en az X kadar artış. Oluşurken hacim çok düşer, kırılışta artar. En çok bir iki hafta sürer (s. 35).
- Flama: kısa süreli üçgen, hızlı yükselişten sonra (s. 36). Kama: flamaya benzer, aşağı eğimli (s. 37).
- Yalnızca adı ya da resmi geçen, kuralı verilmeyenler: çanak, Elliott dalgaları, Gann, ikili tepe/dip (resimde; bizde zaten var).

## Koda geçişi ve BIST 100 sınaması (2026-11-04)

Veri: bugünkü BIST 100, 2020-11 – 2026-11 (sağkalım yanlılığı var). Kurallar `piyasa/analiz/ajan/kaynaklar/gedik2021.py`. Güncel kanıt `/analiz` sayfasında.

| Konu | Durum | Bulgu |
|---|---|---|
| Üçgen hedefi | **Kodumuz yanlıştı, düzeltildi** | Kırılış + yükseklik kullanılıyordu; iki kaynağa göre karşı kenarın paraleli |
| Bayrak | **Düzeltildi** | Süre 20 günden 10 güne indi; kırılış hacmi sapın yüksek hacmiyle kıyaslanıyordu; hacmi düşmeyen bayrak artık geçersiz |
| Kama, kanal | Eklendi | Kanal Altay'da da vardı, atlanmıştı. İkisi de şanstan farksız |
| Fibonacci | %0 ve %100 eklendi | Metindeki "klasik alım alanı" kaldırıldı; buradan dönüş şanstan farksız |
| Ortalama kesişimleri (5 kural) | Kural olarak | 20/50 aşağı kesişimi (+%1,40, p = 0,008) ve 50 günlüğün altına iniş (+%0,81, p = 0,023) zayıf kanıt; Holm düzeltmesini geçemedi. Öteki sinyaller şanstan farksız |
| Hacimli kırılış, boğa/ayı tuzağı | Kural olarak | Şanstan farksız |
| "Dik çizgi daha güvenilir" | **Dayanıklılık için yanlış** | 60 günde kırılma: yatık %70, orta %88, dik %95. Altay haklı. Kırılış sonrası daha sert hareket iddiası ise yönüyle uyuyor (yatıkta +%1,6, dikte −%1,9), ölçüm endekse göre değil |
| "Uzun çizgi daha sağlam" | Desteklenmedi | 60 günde kırılma üç grupta da %84–85. Çizgiler komşu tepe-diplerden kurulduğu için en uzun grup bile ~27 gün |
| "Çok temas daha sağlam" | Sınanmadı | Çizgilerimiz iki noktalıdır, sonraki nokta çizgiyi yeniler |
| "Hedef, en az gidilecek nokta" | **Desteklenmedi** | 60 günde hedefe ulaşma %18–70 (bayrak %27, simetrik üçgen %25, OBO %18) |
| Çanak, Elliott, Gann | Eklenmedi | Sunumda kural yok, yalnızca adı geçiyor |

Çoklu test uyarısı: 48 sinyal türünün 3'ü ham p < 0,05 verdi (biri Altay'dan). Şansla yaklaşık 2 tanesi beklenir; "zayıf kanıt" etiketini tek başına karar sebebi sayma.

Formasyon türlerine ayrılınca yalnızca omuz-baş-omuz öne çıktı: kırılıştan sonra 60 günde grubun %3,8 gerisinde (ham p = 0,016, düzeltmesiz). Hepsi sınandığı için bu da kanıt sayılmaz, izlenecek.

## Dönemlere ayrılmış yeniden sınama (2026-11-04)

Yukarıdaki tablo düzeltmelerden öncedir; 2026'daki savaş ve fon krizini içerir, bedelsiz hatası taşır ve p değerleri çakışmayı hesaba katmaz. Güncel sonuçlar `notlar/matriks-2020.md` dosyasındadır. Bu kaynak için:
- 20/50 aşağı kesişimi Holm'u geçti: olağan dönem +%2,07, 2012–2020 +%0,56, savaş ve fon krizi −%0,86.
- 60 günde kırılma (yatık/orta/dik): olağan %70/87/95, 2012–2020 %69/88/98, kriz %64/94/99. "Dik çizgi daha güvenilir" krizden bağımsız olarak desteklenmedi.
- Hedefe ulaşma, olağan / 2012–2020 / kriz: ters OBO %72/58/33, yükselen üçgen %60/57/63, dikdörtgen %52/49/35, alçalan üçgen %48/57/36, bayrak %29/28/6, OBO %18/30/31. Krizde örnek küçük (12–65 kırılış). "En az gidilecek nokta" iddiası sakin dönemde de desteklenmedi.
