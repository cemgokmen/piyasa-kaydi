"""
Rehber sayfaları: finans bilmeyen biri için bildirimlerin ve temel kavramların sade anlatımı.
Arama motorlarında "Form 4 nedir", "KAP pay alım satım bildirimi" gibi aramalarda çıkmak için de.

Her rehber: slug, baslik, ozet (sayfa açıklaması), bolumler [(alt başlık, [paragraf ...])],
ilgili [(bağlantı metni, adres)].
"""

REHBERLER = [
    {
        "slug": "form-4-nedir",
        "baslik": "Form 4 nedir? ABD'de şirket yöneticilerinin hisse işlemleri",
        "ozet": "ABD'de şirket yöneticilerinin ve büyük ortakların kendi şirketlerinin hisselerini alıp sattığında "
                "SEC'e verdiği Form 4 bildirimi nedir, nasıl okunur, neden satışlar alımlardan çok daha fazladır?",
        "bolumler": [
            ("Form 4 kısaca", [
                "ABD'de bir şirketin üst düzey yöneticileri (CEO, finans direktörü gibi), yönetim kurulu üyeleri ve "
                "şirketin %10'undan fazlasına sahip ortaklar, kendi şirketlerinin hisselerinde yaptıkları her işlemi "
                "ABD Sermaye Piyasası Kurulu'na (SEC) bildirmek zorundadır. Bu bildirimin adı Form 4'tür.",
                "Bildirim, işlemden sonraki 2 iş günü içinde yapılmalıdır ve herkese açıktır. Bu yüzden içeriden "
                "biri hisse aldığında ya da sattığında bunu birkaç gün içinde öğrenmek mümkündür.",
            ]),
            ("Neden satışlar alımlardan çok fazla?", [
                "Yöneticiler maaşlarının önemli bir kısmını şirket hissesi olarak alır. Bu hisseleri vergi ödemek, ev "
                "almak ya da birikimlerini çeşitlendirmek için düzenli olarak satarlar; çoğu satış önceden planlanmış "
                "(\"10b5-1 planı\") otomatik satıştır.",
                "Bu yüzden tek bir satış genellikle bir şey söylemez. Buna karşılık bir yöneticinin kendi parasıyla "
                "piyasadan hisse alması daha anlamlı kabul edilir: hissenin değerinin artacağına inanmadan cebinden "
                "para koymaz. Birden çok yöneticinin aynı dönemde alması (\"küme alımı\") daha da dikkat çeker.",
            ]),
            ("Sitede hangi işlemler var?", [
                "Yalnızca açık piyasada yapılan alım (P) ve satımlar (S) gösterilir. Maaş olarak verilen hisseler, opsiyon "
                "kullanımları ve vergi için alıkonan hisseler yatırım kararı olmadığı için dışarıda bırakılır.",
                "Her işlemde bildirimin ne kadar geç yapıldığı da görünür; yasal süreyi aşanlar kırmızıyla işaretlenir.",
            ]),
        ],
        "ilgili": [("Yöneticilerin son işlemleri", "/islemler?kaynak=yonetici"),
                   ("Birden çok yöneticinin aldığı hisseler", "/sinyaller")],
    },
    {
        "slug": "13f-nasil-okunur",
        "baslik": "13F nedir, nasıl okunur? Büyük fonların portföyleri",
        "ozet": "BlackRock, Vanguard, Berkshire Hathaway gibi büyük yatırım kurumlarının her çeyrek SEC'e verdiği 13F "
                "bildirimi nedir, ne gösterir, neyi göstermez?",
        "bolumler": [
            ("13F kısaca", [
                "ABD'de 100 milyon doların üzerinde hisse yöneten kurumlar (fonlar, bankalar, sigorta şirketleri), her "
                "çeyreğin sonunda ellerinde hangi ABD hisselerinden ne kadar olduğunu 13F formuyla SEC'e bildirir.",
                "Bildirim çeyrek bittikten sonra en geç 45 gün içinde verilir. Yani bir fonun Mart sonundaki portföyü "
                "en geç Mayıs ortasında öğrenilir.",
            ]),
            ("Ne gösterir, neyi göstermez?", [
                "Gösterir: hangi hisseden kaç adet tutulduğu ve değeri. İki çeyreği karşılaştırınca hangi hisseye yeni "
                "girildiği, hangisinden tamamen çıkıldığı, hangisinin artırıldığı anlaşılır.",
                "Göstermez: açığa satışlar, ABD dışı hisseler, tahviller ve nakit. Ayrıca bilgi en az 45 gün eskidir; "
                "fon bu arada pozisyonunu değiştirmiş olabilir.",
                "Büyük endeks fonlarının (Vanguard, BlackRock) alımları çoğu zaman bir karar değil, endekse giren çıkan "
                "hisselerin ya da fona giren paranın sonucudur.",
            ]),
        ],
        "ilgili": [("Fonlar ve bankalar", "/fonlar")],
    },
    {
        "slug": "abd-kongre-hisse-islemleri",
        "baslik": "ABD'li siyasetçilerin hisse işlemleri nasıl bildiriliyor? (STOCK Act)",
        "ozet": "ABD Kongre üyelerinin hisse ve kripto işlemlerini açıklamasını zorunlu kılan STOCK Act nedir? "
                "Bildirimler neden tutar aralığı verir, ne kadar geç gelir?",
        "bolumler": [
            ("STOCK Act kısaca", [
                "2012'de çıkan STOCK Act yasası, ABD Kongre üyelerinin (Temsilciler Meclisi ve Senato), eşlerinin ve "
                "bakmakla yükümlü oldukları çocuklarının 1.000 doları aşan hisse, tahvil ve kripto para işlemlerini "
                "en geç 45 gün içinde açıklamasını zorunlu kılar.",
                "Amaç, yasa yapanların görevleri sırasında öğrendikleri bilgilerle kişisel kazanç sağlamasının önüne "
                "geçmektir.",
            ]),
            ("Neden tam tutar yok?", [
                "Bildirim formunda tutar tam olarak değil, aralık olarak yazılır: 1.001–15.000 dolar, 15.001–50.000 dolar, "
                "50.001–100.000 dolar gibi. Bu yüzden sitede tutarlar \"en az – en çok\" olarak gösterilir.",
            ]),
            ("Geç bildirim ve çıkar çatışması", [
                "45 günü aşan bildirimler sitede kırmızıyla işaretlenir. Yasanın öngördüğü ceza düşük olduğu için geç "
                "bildirim sık görülür.",
                "Bir üyenin, üyesi olduğu komitenin denetlediği sektörden hisse alması (örneğin savunma komitesindeki "
                "birinin savunma şirketi alması) olası çıkar çatışması olarak işaretlenir. Bu bir suçlama değildir; "
                "yalnızca dikkat çeken bir durumdur.",
            ]),
        ],
        "ilgili": [("Siyasetçilerin işlemleri", "/siyasetciler"), ("Çıkar çatışmaları", "/siyasetciler/cikar-catismasi"),
                   ("Kim piyasayı yendi?", "/siyasetciler/performans")],
    },
    {
        "slug": "kap-pay-alim-satim-bildirimi",
        "baslik": "KAP pay alım satım bildirimi nedir? Borsa İstanbul'da içeriden işlemler",
        "ozet": "Borsa İstanbul şirketlerinin yöneticileri ve büyük ortakları hisse alıp sattığında KAP'ta yaptığı "
                "pay alım satım bildirimi nedir, nasıl okunur? Fonların eşik bildirimleri ne anlama gelir?",
        "bolumler": [
            ("Kim bildirmek zorunda?", [
                "Türkiye'de Sermaye Piyasası Kurulu'nun (SPK) Özel Durumlar Tebliği'ne göre, borsada işlem gören bir "
                "şirkette yönetim sorumluluğu olan kişiler (yönetim kurulu üyeleri, genel müdür gibi) ve onlarla yakın "
                "ilişkideki kişiler şirket hisselerinde yaptıkları işlemleri Kamuyu Aydınlatma Platformu'nda (KAP) duyurur.",
                "Ayrıca bir kişinin ya da şirketin bir şirketteki payı %5, %10, %15, %20, %25, %33, %50, %67 ya da %95 "
                "eşiklerinden birini geçtiğinde ya da altına düştüğünde de bildirim yapılır.",
            ]),
            ("Bildirim nasıl okunur?", [
                "Bildirimlerin çoğu standart bir cümleyle yazılır: \"… tarihinde X payları ile ilgili olarak … TL fiyattan "
                "… nominal tutarlı alış işlemi Y tarafından gerçekleştirilmiştir.\"",
                "Nominal tutar, işleme konu pay adedidir (Borsa İstanbul'da bir payın nominal değeri genellikle 1 TL'dir). "
                "İşlem tutarı yaklaşık olarak nominal tutar ile fiyatın çarpımıdır.",
                "Bildirimin sonunda kişinin işlemden sonra şirketin yüzde kaçına sahip olduğu yazar.",
            ]),
            ("Fonların eşik bildirimleri", [
                "Portföy yönetim ve emeklilik şirketlerinin yönettiği fonlar da bir şirketteki payları belirli eşikleri "
                "geçince bildirim yapar. Eylül 2026'dan beri bu eşikler %3'ten başlıyor. Fon bildirimleri bir yöneticinin "
                "kişisel kararı değil, fonun yatırım kararıdır; sitede ayrı gösterilir.",
            ]),
        ],
        "ilgili": [("Borsa İstanbul'da kim aldı, kim sattı?", "/bist")],
    },
    {
        "slug": "pay-geri-alimi-nedir",
        "baslik": "Pay geri alımı nedir? Şirketler kendi hisselerini neden alır?",
        "ozet": "Şirketlerin kendi hisselerini borsadan geri alması ne demek, hisse fiyatına etkisi nedir, KAP'ta "
                "nasıl duyurulur?",
        "bolumler": [
            ("Geri alım kısaca", [
                "Bir şirket, elindeki nakitle kendi hisselerini borsadan satın alabilir. Buna pay geri alımı denir. "
                "Türkiye'de şirketler geri alım işlemlerini KAP'ta duyurur; bildirimde işlem günü, alınan pay adedi, "
                "fiyat ve sermayeye oranı yer alır.",
            ]),
            ("Şirketler neden geri alım yapar?", [
                "Yönetim hisseyi ucuz bulduğunda geri alım, \"hissemize güveniyoruz\" mesajıdır.",
                "Piyasadaki pay sayısı azaldığı için kalan hisselerin kardaki payı artar.",
                "Sert düşüş dönemlerinde fiyatı desteklemek için de kullanılır. Geri alımın kendisi hissenin "
                "yükseleceğini garanti etmez.",
            ]),
        ],
        "ilgili": [("Kendi payını geri alan şirketler", "/bist#geri-alim")],
    },
    {
        "slug": "f-k-pd-dd-nedir",
        "baslik": "F/K, PD/DD, temettü verimi nedir? Hisse rakamları sade dille",
        "ozet": "Hisse sayfalarındaki F/K oranı, PD/DD, net kar marjı, temettü verimi ve analist hedef fiyatı ne "
                "anlama gelir? Finans bilmeyenler için kısa anlatım.",
        "bolumler": [
            ("Piyasa değeri", [
                "Şirketin bütün hisselerinin bugünkü fiyatla toplam değeri. Şirketin borsadaki büyüklüğünü gösterir.",
            ]),
            ("F/K (fiyat / kazanç)", [
                "Hisse fiyatının, hisse başına yıllık karın kaç katı olduğunu gösterir. F/K 10 ise, şirket bugünkü kar "
                "seviyesini korursa hisse fiyatını kabaca 10 yılda kazanıyor demektir. Düşük F/K ucuzluk, yüksek F/K ise "
                "büyüme beklentisi anlamına gelebilir; şirket zarar ediyorsa F/K hesaplanmaz.",
            ]),
            ("PD/DD (piyasa değeri / defter değeri)", [
                "Piyasa değerinin, şirketin defterdeki özkaynağının kaç katı olduğu. 1'in altı, şirketin borsada "
                "defter değerinin altında işlem gördüğü anlamına gelir.",
            ]),
            ("Net kar marjı ve temettü verimi", [
                "Net kar marjı: her 100 liralık satıştan kaç liranın net kar olarak kaldığı.",
                "Temettü verimi: şirketin bir yılda dağıttığı kar payının hisse fiyatına oranı.",
            ]),
            ("Analist hedef fiyatı", [
                "Bankalarda ve aracı kurumlarda hisseyi takip eden uzmanların 12 ay sonrası için fiyat tahminlerinin "
                "ortalaması. Analistler sık yanılır; hedef fiyat bir kesinlik değil, görüştür.",
            ]),
        ],
        "ilgili": [("Örnek: Apple hisse sayfası", "/hisse/AAPL"), ("Örnek: THY hisse sayfası", "/bist/THYAO")],
    },
]

REHBER = {r["slug"]: r for r in REHBERLER}
