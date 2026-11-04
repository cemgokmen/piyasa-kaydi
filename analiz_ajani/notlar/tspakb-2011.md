# TSPAKB 2011: Analiz Yöntemleri

Türkiye Sermaye Piyasası Aracı Kuruluşları Birliği, *Analiz Yöntemleri*, SPK lisanslama sınavları ileri düzey kılavuzu, Eylül 2011. 93 sayfa.
Sayfalar kılavuzun basılı numaralarıdır (PDF sayfası = basılı + 5). Kurallar: `piyasa/analiz/ajan/kaynaklar/tspakb2011.py`.

Okunan bölümler: firma analizi (s. 22–46) ve grafikler-teknik analiz (s. 47–87). Faiz ve ekonomi-sektör analizi (s. 1–21) gözden geçirilmedi, ajana girecek sınanabilir iddia aranmadı.

## Bu kaynak sayesinde bulunan hata

Sermaye artırımı düzeltmesi bölümü (s. 56–57) `bolunme_duzelt` fonksiyonunu yeniden incelemeye yol açtı. Eski kural "kapanıştan kapanışa %15'ten büyük her sıçrama sermaye artırımıdır" diyordu. Bu yanlıştı:

- Baz fiyat ağırlıklı ortalamayken (2021 başına kadar) kapanıştan kapanışa +%22'ye, −%18'e kadar gerçek hareket olabiliyordu. Veride +%10,5 üstü günler 2021 Ocak'ta biter.
- Yahoo seans atlayabiliyor. VESTL 2026-11-03'ü atlamış; iki tavan +%21 görünüyor. Eski kural geçmişi %21 şişirip günün yükselişini siliyordu; aynı gün 11 hisse sınırı aştı.
- 2023-02-15 deprem sonrası açılış 70 hisseyi etkiledi.

99 hissede 350 gün düzeltiliyordu, 20 gün gerçekten düzeltme gerektiriyor. Yeni kural seansa ve döneme bakar, yukarı sıçramayı yalnızca %25'in üstünde düzeltir (bedelsiz fiyatı düşürür; AYGAZ +%72 gibi yukarılar Yahoo hatasıdır). Aynı zamanda eski kuralın kaçırdığı küçük bedelsizleri yakalar (KCAER −%13,7, EUREN −%13,4).

**Bu düzeltmeden önceki bütün sınama sayıları, öteki not dosyalarındakiler dahil, biraz değişti.** Güncel sayı `/analiz` sayfasındadır.

Kaynakla karşılaştırma: hacmin (1 + BDL + BDZ) ile çarpılması bizde var (s. 57). Çıkarma yerine oranla düzeltmeyi kaynak da önerir (dipnot 2, s. 56), bizde de oranladır. Yahoo temettüyü düzeltir (TUPRS, FROTO, DOAS, TTRAK, ENJSA, AKSEN, EREGL denendi); bu yüzden düzeltilmiş kapanışta bir tavan günü %10'u aşabilir.

## Kaynaktaki yanlışlar

| Sayfa | Yazan | Doğrusu |
|---|---|---|
| 73 | 9 günlük üssel katsayı 2/10 = 0,5 | 0,2 |
| 73 | "X=2 iken katsayı 2/13" | X=12 |
| 69 | Üssel ortalamada dönem seçimi yoktur | Aynı sayfada ç = 2/(n+1); n bir dönem seçimidir |
| 72 | Bollinger, "sapma değeri ile çarpılan ortalamanın zarfı" | Ortalama ± k × standart sapma |
| 76 | %K formülünde ×100 yok | 0–100 ölçeği için gerekir |
| 40 | Sonuç 360'a bölünürse kaç günde yenilendiği bulunur | 360, devir hızına bölünür |
| 80 | Fibonacci, Giza piramidini incelerken bulan bir rahip | Rahip değildi, piramit anlatısının dayanağı yok; dizi *Liber Abaci*'deki problemden bilinir |
| 81 | Oran "son fiyata" uygulanır | Salınımın boyuna uygulanır; s. 83'te doğrusu var |
| 80 | 3. dalga en uzun | Elliott kuralı "en kısa olamaz"dır |

Kaynak s. 60'taki açığa satış düzenlemesi 2011 tarihlidir, bugünkü mevzuat yerine kullanılmaz.

MACD katsayıları: kaynak 0,15 ve 0,075 (Appel) der, biz 2/13 ve 2/27 kullanıyoruz. 60 hissede 14.575 kesişimin %96,3'ü aynı gün çıkar. Değiştirilmedi.

Fibonacci oranı: kaynak %76,4 der, biz %78,6 çiziyoruz. Yığılma olmadığı için (aşağıda) seçimin önemi yok, değiştirilmedi.

## Sınama sonuçları

Fark: aynı günkü hisse grubuna göre, SAT'ta artı hissenin geride kaldığını gösterir. Maliyet öncesi. Sıra: olağan (2020-11 – 2026-02) / 2012–2020.

| Kural | Sayfa | AL | SAT | Karar |
|---|---|---|---|---|
| Fiyat, HO20 | 69–70 | −0,09 / −0,16 | +0,29 / +0,18 | şans |
| 5/20 kesişim | 69–70 | −0,45 / −0,22 | +0,49 / +0,41 | şans |
| HO20, %3 filtre | 70 | −0,15 / +0,01 | +0,54 / +0,34 | SAT zayıf |
| HO20, 2 gün filtre | 70 | −0,15 / −0,09 | +0,56 / +0,25 | SAT zayıf, tekrarladı |
| HO20, %5 zarf | 70 | −0,22 / −0,14 | +0,96 / +0,27 | SAT zayıf |
| En yüksek-en düşük bandı | 70–71 | −0,04 / −0,03 | +0,39 / +0,26 | şans |
| Bollinger dışı, bant açılıyor | 72 | −0,48 / +0,07 | +1,07 / +0,55 | SAT zayıf, tekrarladı |
| Bollinger sıkışma kırılışı | 72 | −0,37 / +0,09 | +0,09 / +0,58 | şans |
| MACD, ADX ≥ 20 | 73, 78 | +0,12 / +0,10 | +0,26 / +0,04 | şans |
| MACD, ADX < 20 | 78 | −0,74 / −0,96 | +0,57 / +0,80 | olağanda şans; 2012–2020'de p < 0,01 |
| MACD histogram dönüşü | 73 | +0,23 / −0,15 | +0,29 / +0,02 | şans |
| Stokastik(5) kesişim | 76 | −0,08 / −0,05 | +0,02 / −0,00 | şans |
| Stokastik(5) bölge çıkışı | 76 | +0,14 / −0,13 | +0,18 / +0,02 | şans |
| RSI(9) 30/70 | 77 | −0,37 / −0,35 | +0,30 / −0,39 | şans |
| RSI(25) 30/70 | 77 | +0,49 / −0,25 | +0,02 / −1,03 | şans |
| RSI uyumsuzluğu | 77 | +0,46 / −0,33 | +0,18 / +0,06 | şans |
| Anahtar gün | 67 | +2,94 / −0,13 | +0,25 / +0,46 | şans (AL'da az örnek) |
| Kırılma boşluğu | 68 | −0,98 / +0,50 | +2,20 / +0,47 | SAT zayıf |
| Boşluk dolumu | 68 | −1,37 / +0,08 | −0,51 / +0,21 | şans |
| İkili tepe-dip | 67 | −0,38 / −0,27 | +1,38 / +0,73 | SAT zayıf, tekrarladı |
| Trend çizgisinden geri çekilme | 62 | −0,35 / −0,01 | −0,10 / +0,41 | şans |

21 yeni kuralın hiçbiri Holm düzeltmesini geçmedi. Toplam 140 testte 16 ham p < 0,05 var (şansla yaklaşık 7), 12'si SAT. Holm'u hâlâ yalnızca Gedik 20/50 SAT geçiyor (+2,09; 2012–2020'de +0,53, p = 0,08, tek başına anlamlı değil). Tekrarlanan AL kuralı yine yok.

İki dönemde de aynı yönde p < 0,05 çıkanların hepsi SAT: 2 gün filtreli HO20, Bollinger dışına çıkış, ikili tepe, +DI/−DI (Budak), beş gösterge (Matriks). Hiçbiri tek başına Holm'u geçmez. Bunlar "almama" uyarısı olarak okunabilir, açığa satış veya kesin satış gerekçesi değildir.

Kaynakların karşılaştığı yer:

- **Bollinger:** Budak "banda değen fiyat döner" der, TSPAKB "bant dışında devam" der. Veri TSPAKB'ye yakındır: alt bandın altına kapanış geride kalmaya devam eder. Budak'ın alt bant AL'ı olağanda artık şans (−0,73, p = 0,056), 2012–2020'de geride kalır (−0,42, p = 0,004).
- **Filtreler:** Kaynağa göre yanlış sinyali azaltır. SAT tarafında farkı büyütür (+0,29'dan +0,54–0,96'ya), AL tarafında etkisizdir.
- **ADX:** "ADX < 20 iken MACD geçersizdir" yarım doğru. ADX ≥ 20 filtresi kazanç sağlamaz. ADX < 20'de AL iki dönemde de eksi, SAT ise iki dönemde de artı; yani sinyal geçersiz değil, AL'ı kötü.

## Sinyal olmayan iddialar

Bunlar al-sat sinyali üretmediği için `/analiz` tablosunda görünmez; sonuçlar yalnızca bu dosyadadır.

| İddia | Sayfa | Olağan | 2012–2020 | Sonuç |
|---|---|---|---|---|
| Yükselen üçgen düz kenardan (yukarı) kırılır | 65 | %47 (n 629) | %37 (n 1101) | Çürüdü |
| Alçalan üçgen düz kenardan (aşağı) kırılır | 65 | %40 (n 534) | %35 (n 817) | Çürüdü |
| Simetrik üçgen önceki trend yönünde kırılır | 65 | %52 | %52 | Yazı tura |
| Alçalan kama yukarı kırılır | 66 | %85 | %78 | Tuttu |
| Yükselen kama aşağı kırılır | 66 | %63 | %69 | Tuttu |
| Üçgen, boyunun 2/3–3/4'ünde kırılır | 65 | Dilimde %11–17 | %9–16 | Kural değil, medyan 0,58–0,86 |
| Düzeltme %38–62 arasıdır | 80 | %16 | %17 | Çürüdü |
| Fibonacci seviyesinde yığılma | 81–83 | Yok (%61,8 bandı %3,1; %56 bandı %3,1) | Yok | Çürüdü |
| Fibonacci zaman günlerinde sert hareket (5–34) | 84 | +0,013, p = 0,22 | +0,001, p = 0,93 | Çürüdü |
| Bollinger sıkışması oynaklık artışını haber verir | 72 | 1,22 / 1,01 kat | 1,27 / 1,01 kat | Tuttu, ama düşük oynaklıktan dönüş kendiliğinden beklenir |
| Sıkışma trend değişimini haber verir | 72 | %46 / %47 yön değişimi | %45 / %46 | Çürüdü |
| Uzun vadede log eksen (trend çizgisi) | 53–55 | Karışık | Karışık | İki dönemde iyileşme yok, aritmetik kaldı |

Kama ve üçgen sonuçlarının bir kısmı geometridir: eğimli kenar fiyata doğru gelir, ona değme olasılığı yüksektir. Kırılışın yönünü söyler, kırılıştan sonra kazandıracağını söylemez. Formasyon kuralı sınamada şans düzeyindedir.

Elliott dalgaları (s. 79–80) sınanmadı: dalga sayımı yoruma bağlı, önceden yazılmış bir sinyal çıkmıyor. V formasyonu (s. 65) yalnız tanımlanmış, sinyal kuralı yok. Fibonacci yay ve yelpazesi (s. 81–83) yoruma bağlı ve eksen ölçeğine göre değişir.

## Yapılan değişiklikler

- `bolunme_duzelt` düzeltildi; kural sınaması, puan testi ve tarama yeniden çalıştırıldı.
- Üçgenlere kırılmadan yön verilmiyor; yeşil/kırmızı gösterilmez.
- Yukarı boşluk artık olumlu gösterilmiyor (Aşağı boşluk olumsuz kaldı).
- Fibonacci okumasına yığılma olmadığı yazıldı.
- Temel analize asit-test, nakit oranı, duran varlık/devamlı sermaye, borç/maddi özkaynak, stok ve alacak süresi eklendi (s. 36–41). Yahoo'da yalnızca son dört yıl olduğu için geçmişte sınanamaz; puana girmez.
- Bayrak: vergi öncesi özkaynak getirisi, faiz öncesi varlık getirisinden düşükse borç aleyhte çalışıyor demektir. Kaynak s. 43 vergi sonrası ROE ile karşılaştırır; vergi tek tarafa girmesin diye iki taraf da vergi öncesi alındı.
- Teknik puan değişmedi: kaynaktaki hiçbir şey puana önceden belirlenen ölçütü geçerek girmedi.

## Bizde olup kaynakta da doğrulananlar

Destek-direnç gücünde hacim ve süre (s. 62), kırılan seviyenin rol değiştirmesi (s. 61), Dow ilkeleri (s. 61), cari oran ölçüsü 2 (s. 37; puanda +1 buradadır), oranların sektör ve geçmişle kıyaslanması (s. 36), enflasyondan arındırma (s. 35).

Kaynağın en yararlı cümlesi s. 86: yöntemler kârlılık ve tutarlılık açısından sürekli sınanmalı, komisyon gözetilmeli.
