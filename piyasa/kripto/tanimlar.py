"""
Takip edilen kripto paralar ve profilleri.

Her coin için:
  coingecko   CoinGecko kimliği (gerçek 24 saatlik değişim, piyasa değeri, arz, zirve)
  yahoo       Yahoo Finance kodu (fiyat geçmişi ve grafik)
  sembol      Borsalardaki kısaltması
  tur         Ne tür bir kripto olduğu (sade dille)
  ozet        Ne işe yaradığı, 2-3 cümle
  kurulus     Ağın çalışmaya başladığı yıl
  kurucu      Kurucuları
  mekanizma   İşlemlerin nasıl onaylandığı
  arz         Toplam arzın nasıl belirlendiği
  ozellikler  Öne çıkan özellikler (madde madde)
  etkenler    Fiyatını neler etkiler
  riskler     Bilinmesi gereken riskler
  cot         CFTC raporundaki vadeli işlem kodu (büyük fonların konumu); yoksa None
  vadeli      Yahoo'daki CME vadeli kök kodu (piyasa beklentisi); yoksa None
  etfler      ABD'de işlem gören spot kripto fonları {borsa kodu: ad}
  adlar       Kongre bildirimlerinde bu coini tanıyan kelimeler (küçük harf)
  haber       Google Haberler'de aranacak Türkçe ifade
"""

import re

KRIPTOLAR = [
    {
        "slug": "bitcoin", "coingecko": "bitcoin", "ad": "Bitcoin", "sembol": "BTC", "yahoo": "BTC-USD",
        "tur": "Dijital para",
        "ozet": "İlk ve en büyük kripto para. Hiçbir devlete ya da şirkete bağlı olmadan, internet üzerinden "
                "doğrudan kişiden kişiye para gönderilebilmesi için tasarlandı. Toplam miktarı 21 milyonla "
                "sınırlı olduğu için çoğu zaman \"dijital altın\" diye anılır.",
        "kurulus": 2009, "kurucu": "Satoshi Nakamoto (gerçek kimliği bilinmiyor)",
        "mekanizma": "İş ispatı (madencilik): bilgisayarlar işlemleri onaylamak için yarışır, kazanan yeni bitcoin alır.",
        "arz": "En fazla 21 milyon. Yeni bitcoin üretimi yaklaşık 4 yılda bir yarıya iner (\"halving\").",
        "ozellikler": [
            "Yaklaşık 10 dakikada bir yeni blok (işlem paketi) eklenir.",
            "Son yarılanma Nisan 2024'te oldu; bir sonrakinin 2028'de olması bekleniyor.",
            "ABD'de Ocak 2024'ten beri borsada işlem gören spot Bitcoin fonları (ETF) var.",
        ],
        "etkenler": [
            "Fonlara para girişi: BlackRock ve Fidelity gibi kurumların Bitcoin fonlarına giren ve çıkan para.",
            "Faizler ve dolar: Faiz düştükçe riskli varlıklara talep artar; Fed kararları güçlü etkendir.",
            "Yarılanma döngüsü: Yeni arzın azalması tarihsel olarak fiyatı desteklemiştir.",
            "Düzenlemeler: ABD ve diğer ülkelerin kripto kuralları.",
        ],
        "riskler": [
            "Fiyatı çok oynaktır; bir yılda %50'nin üzerinde düştüğü dönemler olmuştur.",
            "Şifre (özel anahtar) kaybedilirse varlık geri getirilemez.",
        ],
        "cot": "133741", "vadeli": "BTC",
        "etfler": {
            "IBIT": "iShares Bitcoin Trust (BlackRock)", "FBTC": "Fidelity Wise Origin Bitcoin Fund",
            "GBTC": "Grayscale Bitcoin Trust", "BTC": "Grayscale Bitcoin Mini Trust",
            "ARKB": "ARK 21Shares Bitcoin ETF", "BITB": "Bitwise Bitcoin ETF", "HODL": "VanEck Bitcoin ETF",
            "BTCO": "Invesco Galaxy Bitcoin ETF", "BRRR": "CoinShares Bitcoin ETF",
            "EZBC": "Franklin Bitcoin ETF", "BITO": "ProShares Bitcoin Strategy ETF (vadeli)",
        },
        "adlar": ["bitcoin", "btc"],
        "haber": '"bitcoin" OR "BTC fiyatı"',
    },
    {
        "slug": "ethereum", "coingecko": "ethereum", "ad": "Ethereum", "sembol": "ETH", "yahoo": "ETH-USD",
        "tur": "Akıllı sözleşme platformu",
        "ozet": "Üzerinde uygulama çalıştırılabilen bir blokzincir. Bankasız kredi ve takas uygulamaları (DeFi), "
                "dolara bağlı sabit paralar ve NFT'lerin büyük kısmı Ethereum üzerinde çalışır. Ağın para birimi "
                "Ether (ETH), işlem ücretlerini ödemekte kullanılır.",
        "kurulus": 2015, "kurucu": "Vitalik Buterin ve ekibi",
        "mekanizma": "Hisse ispatı: ETH'sini kilitleyen (\"stake\" eden) kullanıcılar işlemleri onaylar ve ödül alır. "
                     "Eylül 2022'de madencilikten bu sisteme geçti.",
        "arz": "Üst sınırı yok. Ücretlerin bir kısmı yakıldığı için arz yoğun dönemlerde azalabilir.",
        "ozellikler": [
            "Yaklaşık 12 saniyede bir yeni blok eklenir.",
            "Dolar bazlı sabit paraların (USDT, USDC) önemli kısmı Ethereum üzerindedir.",
            "ABD'de Temmuz 2024'ten beri spot Ethereum fonları (ETF) işlem görüyor.",
        ],
        "etkenler": [
            "Ağ kullanımı: DeFi ve sabit para işlemleri arttıkça ETH talebi artar.",
            "Rakip ağlar: Solana gibi daha ucuz ağlarla rekabet.",
            "Fonlara para girişi ve faizler.",
            "Bitcoin: Kripto piyasası genelde Bitcoin'le birlikte hareket eder.",
        ],
        "riskler": [
            "Bitcoin'den daha oynaktır.",
            "Akıllı sözleşmelerdeki yazılım hataları büyük kayıplara yol açabilir.",
        ],
        "cot": "146021", "vadeli": "ETH",
        "etfler": {
            "ETHA": "iShares Ethereum Trust (BlackRock)", "FETH": "Fidelity Ethereum Fund",
            "ETHE": "Grayscale Ethereum Trust", "ETH": "Grayscale Ethereum Mini Trust",
            "ETHW": "Bitwise Ethereum ETF", "QETH": "Invesco Galaxy Ethereum ETF",
            "EZET": "Franklin Ethereum ETF", "CETH": "21Shares Core Ethereum ETF", "ETHV": "VanEck Ethereum ETF",
        },
        "adlar": ["ethereum", "ether", "eth"],
        "haber": '"ethereum" OR "ETH fiyatı"',
    },
    {
        "slug": "xrp", "coingecko": "ripple", "ad": "XRP", "sembol": "XRP", "yahoo": "XRP-USD",
        "tur": "Ödeme ağı",
        "ozet": "Bankalar ve ödeme şirketleri arasında ülkeler arası para transferini hızlı ve ucuz yapmak için "
                "geliştirildi. XRP Ledger adlı ağın para birimidir; ağı geliştiren şirketlerin başında Ripple gelir.",
        "kurulus": 2012, "kurucu": "Chris Larsen, Jed McCaleb, David Schwartz (Ripple)",
        "mekanizma": "Uzlaşma protokolü: madencilik yoktur, güvenilen sunucular işlemlerin sırası üzerinde anlaşır.",
        "arz": "100 milyar XRP'nin tamamı başlangıçta üretildi; önemli bir kısmı Ripple'ın kontrolündeki emanette tutulur.",
        "ozellikler": [
            "İşlemler 3-5 saniyede onaylanır, ücreti kuruşun çok altındadır.",
            "ABD SEC'in Ripple'a açtığı dava 2025'te sona erdi.",
        ],
        "etkenler": [
            "Bankaların ve ödeme şirketlerinin benimsemesi.",
            "ABD'deki düzenleyici kararlar.",
            "Ripple'ın elindeki XRP'yi piyasaya sürme hızı.",
        ],
        "riskler": [
            "Arzın büyük kısmının tek bir şirketin kontrolünde olması.",
            "Fiyatı haber ve dava gelişmelerine çok duyarlıdır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["xrp", "ripple"],
        "haber": '"XRP" OR "Ripple"',
    },
    {
        "slug": "bnb", "coingecko": "binancecoin", "ad": "BNB", "sembol": "BNB", "yahoo": "BNB-USD",
        "tur": "Borsa ve platform parası",
        "ozet": "Dünyanın en büyük kripto borsası Binance'in çıkardığı kripto para. Binance'te işlem ücreti "
                "indirimi sağlar ve BNB Chain ağında işlem ücretlerini ödemekte kullanılır.",
        "kurulus": 2017, "kurucu": "Changpeng Zhao (Binance)",
        "mekanizma": "Yetkili hisse ispatı: sınırlı sayıda doğrulayıcı işlemleri onaylar.",
        "arz": "Başlangıçta 200 milyon; düzenli yakımlarla 100 milyona indirilmesi hedefleniyor.",
        "ozellikler": [
            "Binance her çeyrek BNB yakarak (yok ederek) arzı azaltır.",
            "BNB Chain, ucuz işlem ücretleriyle en çok kullanılan ağlardan biridir.",
        ],
        "etkenler": [
            "Binance'in işlem hacmi ve itibarı.",
            "Binance'e yönelik düzenleyici davalar ve cezalar.",
        ],
        "riskler": [
            "Değeri büyük ölçüde tek bir şirkete (Binance) bağlıdır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["bnb", "binance coin"],
        "haber": '"BNB" Binance',
    },
    {
        "slug": "solana", "coingecko": "solana", "ad": "Solana", "sembol": "SOL", "yahoo": "SOL-USD",
        "tur": "Akıllı sözleşme platformu",
        "ozet": "Ethereum gibi üzerinde uygulama çalıştırılabilen, ama çok daha hızlı ve ucuz olacak şekilde "
                "tasarlanmış bir blokzincir. Takas uygulamaları, ödeme ve meme coin işlemlerinde çok kullanılır.",
        "kurulus": 2020, "kurucu": "Anatoly Yakovenko",
        "mekanizma": "Hisse ispatı ve \"tarih ispatı\": işlemlere zaman damgası vurularak saniyede binlerce işlem yapılır.",
        "arz": "Üst sınırı yok; her yıl azalan oranda yeni SOL üretilir.",
        "ozellikler": [
            "İşlem ücreti genellikle bir kuruşun altındadır.",
            "Ağ geçmişte birkaç kez saatlerce durdu.",
        ],
        "etkenler": [
            "Ağdaki uygulama ve işlem sayısı.",
            "Kripto piyasasının genel havası; riskli dönemlerde Bitcoin'den daha sert düşer.",
        ],
        "riskler": [
            "Ağ kesintileri geçmişte güveni sarsmıştır.",
            "Çok oynaktır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["solana", "sol"],
        "haber": '"Solana" kripto',
    },
    {
        "slug": "dogecoin", "coingecko": "dogecoin", "ad": "Dogecoin", "sembol": "DOGE", "yahoo": "DOGE-USD",
        "tur": "Meme coin",
        "ozet": "Bir internet şakası olarak, ünlü Shiba Inu köpeği fotoğrafından esinlenerek çıkarıldı. "
                "Elon Musk'ın paylaşımlarıyla popülerleşti; değeri büyük ölçüde topluluk ilgisine dayanır.",
        "kurulus": 2013, "kurucu": "Billy Markus ve Jackson Palmer",
        "mekanizma": "İş ispatı (madencilik), Litecoin ile birlikte kazılır.",
        "arz": "Üst sınırı yok; her yıl yaklaşık 5 milyar yeni DOGE üretilir.",
        "ozellikler": [
            "Bir dakikada bir yeni blok eklenir.",
            "Bahşiş ve küçük ödemelerde kullanılır.",
        ],
        "etkenler": [
            "Sosyal medya ve ünlülerin paylaşımları.",
            "Kripto piyasasının genel havası.",
        ],
        "riskler": [
            "Değeri kullanım yerine ilgiye dayandığı için çok sert dalgalanır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["dogecoin", "doge"],
        "haber": '"Dogecoin"',
    },
    {
        "slug": "tron", "coingecko": "tron", "ad": "TRON", "sembol": "TRX", "yahoo": "TRX-USD",
        "tur": "Akıllı sözleşme platformu",
        "ozet": "Düşük ücretli işlemler için tasarlanmış bir blokzincir. Bugün en çok, dolara bağlı sabit para "
                "USDT'nin (Tether) transferinde kullanılır; Tether transferlerinin büyük kısmı TRON üzerinden yapılır.",
        "kurulus": 2018, "kurucu": "Justin Sun",
        "mekanizma": "Temsili hisse ispatı: TRX sahiplerinin seçtiği 27 temsilci işlemleri onaylar.",
        "arz": "Üst sınırı yok; ücretlerin bir kısmı yakıldığı için arz zaman zaman azalır.",
        "ozellikler": [
            "Bir blok 3 saniyede eklenir.",
            "Gelişmekte olan ülkelerde dolar transferi için yaygın kullanılır.",
        ],
        "etkenler": [
            "Ağdaki USDT hacmi.",
            "Kurucusu Justin Sun'la ilgili gelişmeler.",
        ],
        "riskler": [
            "Ağ yönetimi az sayıda temsilcide toplanmıştır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["tron", "trx"],
        "haber": '"TRON" TRX',
    },
    {
        "slug": "cardano", "coingecko": "cardano", "ad": "Cardano", "sembol": "ADA", "yahoo": "ADA-USD",
        "tur": "Akıllı sözleşme platformu",
        "ozet": "Ethereum'un kurucularından Charles Hoskinson'ın başlattığı, akademik araştırmaya dayalı "
                "geliştirilen bir blokzincir. Yenilikler hakemli bilimsel makalelerle tasarlanır.",
        "kurulus": 2017, "kurucu": "Charles Hoskinson",
        "mekanizma": "Hisse ispatı (Ouroboros): ADA sahipleri doğrulayıcılara oy verir.",
        "arz": "En fazla 45 milyar ADA.",
        "ozellikler": [
            "Geliştirme yavaş ama dikkatli ilerler.",
            "Yönetim kararları ADA sahiplerinin oyuyla alınır.",
        ],
        "etkenler": [
            "Ağda uygulama sayısının artıp artmaması.",
            "Kripto piyasasının genel havası.",
        ],
        "riskler": [
            "Kullanımı rakip ağlara göre düşük kalmıştır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["cardano", "ada"],
        "haber": '"Cardano" ADA',
    },
    {
        "slug": "chainlink", "coingecko": "chainlink", "ad": "Chainlink", "sembol": "LINK", "yahoo": "LINK-USD",
        "tur": "Veri ağı (oracle)",
        "ozet": "Blokzincirler dış dünyayı göremez: hisse fiyatı, hava durumu ya da maç sonucu bilmez. Chainlink "
                "bu verileri güvenilir şekilde blokzincirlere taşır; bankasız kredi uygulamalarının çoğu fiyat "
                "bilgisini Chainlink'ten alır.",
        "kurulus": 2017, "kurucu": "Sergey Nazarov ve Steve Ellis",
        "mekanizma": "Ethereum üzerinde çalışan bir token; veri sağlayıcılar LINK kilitleyerek güvence verir.",
        "arz": "En fazla 1 milyar LINK.",
        "ozellikler": [
            "Bankalar ve SWIFT ile varlıkların blokzincire taşınması üzerine ortak çalışmalar yaptı.",
        ],
        "etkenler": [
            "DeFi uygulamalarının büyümesi.",
            "Geleneksel finans kurumlarıyla ortaklıklar.",
        ],
        "riskler": [
            "Değeri, üzerine kurulduğu ağların başarısına bağlıdır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["chainlink", "link"],
        "haber": '"Chainlink"',
    },
    {
        "slug": "avalanche", "coingecko": "avalanche-2", "ad": "Avalanche", "sembol": "AVAX", "yahoo": "AVAX-USD",
        "tur": "Akıllı sözleşme platformu",
        "ozet": "Hızlı işlem onayı ve şirketlerin kendi özel ağlarını (\"subnet\") kurabilmesiyle öne çıkan bir "
                "blokzincir. Kurucusu Türk asıllı bilgisayar bilimci Emin Gün Sirer'dir.",
        "kurulus": 2020, "kurucu": "Emin Gün Sirer (Ava Labs)",
        "mekanizma": "Hisse ispatı; işlemler genellikle 1-2 saniyede kesinleşir.",
        "arz": "En fazla 720 milyon AVAX; işlem ücretleri yakılır.",
        "ozellikler": [
            "Kurumlar varlıkların blokzincire taşınması (tokenizasyon) için kullanır.",
        ],
        "etkenler": [
            "Kurumsal kullanım ve yeni özel ağlar.",
            "Kripto piyasasının genel havası.",
        ],
        "riskler": [
            "Rakip ağlarla yoğun rekabet.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["avalanche", "avax"],
        "haber": '"Avalanche" AVAX',
    },
    {
        "slug": "stellar", "coingecko": "stellar", "ad": "Stellar", "sembol": "XLM", "yahoo": "XLM-USD",
        "tur": "Ödeme ağı",
        "ozet": "Ülkeler arası para transferini ucuzlatmak ve bankası olmayan insanlara finansal hizmet ulaştırmak "
                "için kurulan bir ödeme ağı. Kâr amacı gütmeyen Stellar Vakfı tarafından desteklenir.",
        "kurulus": 2014, "kurucu": "Jed McCaleb ve Joyce Kim",
        "mekanizma": "Stellar uzlaşma protokolü: madencilik yoktur, güvenilen sunucular anlaşır.",
        "arz": "Toplam 50 milyar XLM; yeni üretim 2019'da durduruldu.",
        "ozellikler": [
            "İşlemler 5 saniyede onaylanır.",
            "Dolar bazlı sabit para USDC Stellar üzerinde de çalışır.",
        ],
        "etkenler": [
            "Ödeme şirketlerinin benimsemesi.",
            "XRP ile benzer hareket etme eğilimi.",
        ],
        "riskler": [
            "Arzın bir kısmı vakfın elindedir.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["stellar", "xlm"],
        "haber": '"Stellar" XLM',
    },
    {
        "slug": "litecoin", "coingecko": "litecoin", "ad": "Litecoin", "sembol": "LTC", "yahoo": "LTC-USD",
        "tur": "Dijital para",
        "ozet": "Bitcoin'in kodundan türetilmiş, daha hızlı ve ucuz ödemeler için tasarlanmış en eski kripto "
                "paralardan biri. \"Bitcoin altınsa Litecoin gümüştür\" sözüyle tanınır.",
        "kurulus": 2011, "kurucu": "Charlie Lee",
        "mekanizma": "İş ispatı (madencilik).",
        "arz": "En fazla 84 milyon LTC; Bitcoin gibi 4 yılda bir yarılanma olur.",
        "ozellikler": [
            "2,5 dakikada bir yeni blok eklenir (Bitcoin'den 4 kat hızlı).",
        ],
        "etkenler": [
            "Bitcoin'in hareketi.",
            "Ödemelerde kullanım.",
        ],
        "riskler": [
            "Yeni ağlar karşısında ilgisi azalmıştır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["litecoin", "ltc"],
        "haber": '"Litecoin"',
    },
    {
        "slug": "bitcoin-cash", "coingecko": "bitcoin-cash", "ad": "Bitcoin Cash", "sembol": "BCH", "yahoo": "BCH-USD",
        "tur": "Dijital para",
        "ozet": "2017'de Bitcoin'den ayrılan bir kol. Bitcoin topluluğunda blok boyutu tartışması yaşanınca, daha "
                "büyük bloklarla daha çok ve daha ucuz işlem yapılmasını isteyen grup Bitcoin Cash'i başlattı.",
        "kurulus": 2017, "kurucu": "Bitcoin topluluğunun bir kısmı (Roger Ver gibi destekçiler)",
        "mekanizma": "İş ispatı (madencilik), Bitcoin'le aynı yöntem.",
        "arz": "En fazla 21 milyon BCH.",
        "ozellikler": [
            "Ayrılık anında Bitcoin sahibi olan herkes aynı miktarda Bitcoin Cash aldı.",
        ],
        "etkenler": [
            "Bitcoin'in hareketi ve yarılanma döngüsü.",
        ],
        "riskler": [
            "Bitcoin'e göre çok daha az kullanılır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["bitcoin cash", "bch"],
        "haber": '"Bitcoin Cash"',
    },
    {
        "slug": "polkadot", "coingecko": "polkadot", "ad": "Polkadot", "sembol": "DOT", "yahoo": "DOT-USD",
        "tur": "Blokzincirleri bağlayan ağ",
        "ozet": "Farklı blokzincirlerin birbiriyle güvenli şekilde konuşabilmesi için tasarlandı. Ethereum'un "
                "kurucularından Gavin Wood tarafından başlatıldı.",
        "kurulus": 2020, "kurucu": "Gavin Wood (Web3 Vakfı)",
        "mekanizma": "Aday gösterilmiş hisse ispatı: DOT sahipleri doğrulayıcıları seçer.",
        "arz": "Üst sınırı yok; her yıl yeni DOT üretilir.",
        "ozellikler": [
            "Bağlı ağlar (\"parachain\") ana ağın güvenliğini ortak kullanır.",
        ],
        "etkenler": [
            "Ağa bağlanan projelerin sayısı.",
            "Kripto piyasasının genel havası.",
        ],
        "riskler": [
            "Kullanımı beklentilerin gerisinde kalmıştır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["polkadot", "dot"],
        "haber": '"Polkadot" DOT',
    },
    {
        "slug": "tether", "coingecko": "tether", "ad": "Tether", "sembol": "USDT", "yahoo": "USDT-USD",
        "tur": "Sabit para",
        "ozet": "Değeri 1 dolara sabitlenmiş bir kripto para. Kripto borsalarında dolar yerine kullanılır; Türkiye gibi "
                "enflasyonun yüksek olduğu ülkelerde birikimi dolarda tutmanın kolay yolu olarak çok yaygındır. "
                "Dünyanın en çok işlem gören kripto parasıdır.",
        "kurulus": 2014, "kurucu": "Tether Limited (kurucuları Brock Pierce, Reeve Collins, Craig Sellars)",
        "mekanizma": "Şirket her USDT'ye karşılık elinde dolar, ABD hazine bonosu ve benzeri varlıklar tuttuğunu beyan eder; "
                     "kendi blokzinciri yoktur, Ethereum ve TRON gibi ağlarda çalışır.",
        "arz": "Üst sınırı yok: talep oldukça yeni USDT basılır, geri ödendikçe yok edilir.",
        "ozellikler": [
            "Fiyatı 1 dolar civarında kalacak şekilde tasarlanmıştır; yatırım değil, ödeme ve saklama aracıdır.",
            "Şirket, yasa dışı işlemlerle ilgili adreslerdeki USDT'yi dondurabilir.",
            "Rezervlerinin büyük kısmı ABD hazine bonosudur; bu yüzden Tether, dünyanın en büyük hazine bonosu alıcılarındandır.",
        ],
        "etkenler": [
            "Fiyat hep 1 dolar civarındadır; izlenmesi gereken, piyasa değerinin (dolaşımdaki USDT miktarının) artıp azalmasıdır.",
            "Piyasa değeri artıyorsa kripto piyasasına yeni para giriyor demektir.",
        ],
        "riskler": [
            "Rezervlerin tam bağımsız denetimi uzun süre tartışma konusu oldu.",
            "Kriz anlarında kısa süreliğine 1 doların altına düşebilir.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["tether", "usdt"],
        "haber": '"Tether" USDT',
    },
    {
        "slug": "usd-coin", "coingecko": "usd-coin", "ad": "USD Coin", "sembol": "USDC", "yahoo": "USDC-USD",
        "tur": "Sabit para",
        "ozet": "ABD'li Circle şirketinin çıkardığı, değeri 1 dolara sabitlenmiş kripto para. Tether'in en büyük rakibidir; "
                "rezervleri düzenli bağımsız raporlarla açıklandığı için kurumlar tarafından daha çok tercih edilir.",
        "kurulus": 2018, "kurucu": "Circle (Jeremy Allaire), başlangıçta Coinbase ile birlikte",
        "mekanizma": "Her USDC'ye karşılık nakit dolar ve kısa vadeli ABD hazine bonosu tutulur; Ethereum, Solana gibi ağlarda çalışır.",
        "arz": "Üst sınırı yok: talep oldukça basılır, geri ödendikçe yok edilir.",
        "ozellikler": [
            "Circle 2025'te ABD borsasında halka açıldı (borsa kodu CRCL).",
            "ABD'de 2025'te sabit paralar için ilk federal yasa çıktı; USDC bu kurallara göre işletilir.",
        ],
        "etkenler": [
            "Fiyat hep 1 dolar civarındadır; izlenmesi gereken dolaşımdaki USDC miktarıdır.",
            "Faizler: Circle, rezervlerdeki hazine bonolarının faizinden kazanır.",
        ],
        "riskler": [
            "Mart 2023'te rezervlerin bir kısmı batan bir bankada kalınca birkaç gün 0,88 dolara kadar düştü.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["usd coin", "usdc"],
        "haber": '"USDC" Circle',
    },
    {
        "slug": "hyperliquid", "coingecko": "hyperliquid", "ad": "Hyperliquid", "sembol": "HYPE", "yahoo": "HYPE32196-USD",
        "tur": "Merkeziyetsiz borsa",
        "ozet": "Kendi blokzinciri üzerinde çalışan, kimlik istemeyen bir kripto vadeli işlem borsası. Kısa sürede dünyanın en "
                "büyük merkeziyetsiz borsalarından biri oldu. Borsanın kazandığı ücretlerin büyük kısmıyla piyasadan HYPE geri alınır.",
        "kurulus": 2024, "kurucu": "Jeff Yan",
        "mekanizma": "Hisse ispatı (HyperBFT): işlemler bir saniyenin altında kesinleşir.",
        "arz": "En fazla 1 milyar HYPE.",
        "ozellikler": [
            "Girişim sermayesi almadı; tokenların büyük kısmı kullanıcılara dağıtıldı.",
            "Kaldıraçlı işlemlerin çok olduğu bir platformdur.",
        ],
        "etkenler": [
            "Borsadaki işlem hacmi ve ücret gelirleri.",
            "Kaldıraçlı işlem talebi: piyasa hareketli oldukça hacim artar.",
        ],
        "riskler": [
            "Genç bir projedir; yazılım hatası ya da piyasa manipülasyonu riskleri vardır.",
            "Kaldıraçlı işlemlerin düzenlenmesi değeri etkileyebilir.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["hyperliquid", "hype"],
        "haber": '"Hyperliquid"',
    },
    {
        "slug": "sui", "coingecko": "sui", "ad": "Sui", "sembol": "SUI", "yahoo": "SUI20947-USD",
        "tur": "Akıllı sözleşme platformu",
        "ozet": "Meta'nın (Facebook) iptal edilen kripto para projesi Diem'de çalışan mühendislerin kurduğu, hızlı ve ucuz "
                "işlemler için tasarlanmış bir blokzincir. Oyun, ödeme ve takas uygulamalarında kullanılır.",
        "kurulus": 2023, "kurucu": "Mysten Labs (Evan Cheng ve eski Meta mühendisleri)",
        "mekanizma": "Hisse ispatı; birbirinden bağımsız işlemler paralel işlenir.",
        "arz": "En fazla 10 milyar SUI; büyük kısmı zamanla serbest bırakılıyor.",
        "ozellikler": [
            "Meta'nın geliştirdiği Move programlama dilini kullanır.",
        ],
        "etkenler": [
            "Ağdaki uygulama ve kullanıcı sayısı.",
            "Kilitli tokenların piyasaya açılma takvimi.",
        ],
        "riskler": [
            "Arzın önemli bir kısmı hala kilitli; açıldıkça satış baskısı oluşabilir.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["sui"],
        "haber": '"Sui" kripto',
    },
    {
        "slug": "near", "coingecko": "near", "ad": "NEAR Protocol", "sembol": "NEAR", "yahoo": "NEAR-USD",
        "tur": "Akıllı sözleşme platformu",
        "ozet": "Kullanımı kolay olacak şekilde tasarlanmış ve son yıllarda yapay zeka uygulamalarına yönelmiş bir blokzincir. "
                "Kurucularından Illia Polosukhin, bugünkü yapay zeka modellerinin temelini atan \"Attention Is All You Need\" "
                "makalesinin yazarlarındandır.",
        "kurulus": 2020, "kurucu": "Illia Polosukhin ve Alexander Skidanov",
        "mekanizma": "Hisse ispatı; ağ parçalara (shard) bölünerek yük paylaştırılır.",
        "arz": "Üst sınırı yok; her yıl az miktarda yeni NEAR üretilir, ücretlerin bir kısmı yakılır.",
        "ozellikler": [
            "Hesap adları uzun adresler yerine okunabilir isimlerdir (örneğin ad.near).",
        ],
        "etkenler": [
            "Yapay zeka ve kripto kesişimindeki ilgi.",
            "Kripto piyasasının genel havası.",
        ],
        "riskler": [
            "Rakip ağlarla yoğun rekabet.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["near protocol", "near"],
        "haber": '"NEAR Protocol"',
    },
    {
        "slug": "uniswap", "coingecko": "uniswap", "ad": "Uniswap", "sembol": "UNI", "yahoo": "UNI7083-USD",
        "tur": "DeFi (merkeziyetsiz finans)",
        "ozet": "Ethereum üzerindeki en büyük merkeziyetsiz borsa. Bir şirkete hesap açmadan, cüzdandan cüzdana kripto takası "
                "yapılmasını sağlar. UNI, platformun yönetimine oy veren kişilerin tokenıdır.",
        "kurulus": 2018, "kurucu": "Hayden Adams",
        "mekanizma": "Ethereum üzerinde çalışan akıllı sözleşmeler; fiyatlar alıcı ve satıcı yerine havuzlardaki oranla belirlenir.",
        "arz": "Başlangıçta 1 milyar UNI.",
        "ozellikler": [
            "Takas havuzlarına para koyanlar işlem ücretlerinden pay alır.",
        ],
        "etkenler": [
            "Platformdaki işlem hacmi.",
            "Ücretlerin UNI sahiplerine dağıtılıp dağıtılmayacağına dair kararlar.",
        ],
        "riskler": [
            "ABD'deki düzenleyicilerin merkeziyetsiz borsalara yaklaşımı.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["uniswap", "uni"],
        "haber": '"Uniswap"',
    },
    {
        "slug": "aave", "coingecko": "aave", "ad": "Aave", "sembol": "AAVE", "yahoo": "AAVE-USD",
        "tur": "DeFi (merkeziyetsiz finans)",
        "ozet": "Bankasız kredi platformu: kullanıcılar kripto paralarını yatırıp faiz alır ya da kripto teminat göstererek "
                "borç alır. Merkeziyetsiz finansın en büyük kredi platformudur.",
        "kurulus": 2017, "kurucu": "Stani Kulechov",
        "mekanizma": "Ethereum ve başka ağlar üzerinde çalışan akıllı sözleşmeler; teminat değeri düşünce pozisyon otomatik kapatılır.",
        "arz": "En fazla 16 milyon AAVE.",
        "ozellikler": [
            "Platformda milyarlarca dolarlık kripto mevduat bulunur.",
            "AAVE sahipleri platformun kurallarına oy verir.",
        ],
        "etkenler": [
            "Platformdaki mevduat ve kredi hacmi.",
            "Kripto piyasasının genel havası.",
        ],
        "riskler": [
            "Akıllı sözleşme hatası ya da teminatın ani değer kaybı kayıplara yol açabilir.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["aave"],
        "haber": '"Aave" kripto',
    },
    {
        "slug": "hedera", "coingecko": "hedera-hashgraph", "ad": "Hedera", "sembol": "HBAR", "yahoo": "HBAR-USD",
        "tur": "Kurumsal ağ",
        "ozet": "Blokzincir yerine \"hashgraph\" adlı farklı bir teknoloji kullanan, hızlı ve ucuz bir ağ. Google, IBM ve "
                "Boeing gibi büyük şirketlerden oluşan bir konsey tarafından yönetilir; kurumsal kullanım hedefler.",
        "kurulus": 2019, "kurucu": "Leemon Baird ve Mance Harmon",
        "mekanizma": "Hashgraph uzlaşması ve hisse ispatı; işlemler saniyeler içinde kesinleşir.",
        "arz": "Toplam 50 milyar HBAR.",
        "ozellikler": [
            "İşlem ücretleri sabit ve dolar cinsinden çok düşüktür.",
        ],
        "etkenler": [
            "Büyük şirketlerin ağı kullanma kararları.",
            "Kripto piyasasının genel havası.",
        ],
        "riskler": [
            "Yönetim az sayıda şirkette toplanmıştır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["hedera", "hbar"],
        "haber": '"Hedera" HBAR',
    },
    {
        "slug": "monero", "coingecko": "monero", "ad": "Monero", "sembol": "XMR", "yahoo": "XMR-USD",
        "tur": "Gizlilik odaklı para",
        "ozet": "Gönderen, alan ve tutarın gizli kaldığı bir kripto para. Bitcoin'de bütün işlemler herkese açıkken "
                "Monero'da işlemler dışarıdan izlenemez.",
        "kurulus": 2014, "kurucu": "Kimliği bilinmeyen bir grup geliştirici",
        "mekanizma": "İş ispatı (madencilik); sıradan bilgisayarlarla kazılabilecek şekilde tasarlandı.",
        "arz": "Sınırı yok: ana arz 2022'de tamamlandı, şimdi her blokta sabit 0,6 XMR üretilir.",
        "ozellikler": [
            "Birçok büyük borsa düzenleyici baskısı nedeniyle Monero'yu listeden çıkardı.",
        ],
        "etkenler": [
            "Gizliliğe olan talep.",
            "Borsalarda listelenme ya da listeden çıkarılma kararları.",
        ],
        "riskler": [
            "Düzenleyici yasaklar ve borsalardan çıkarılma riski.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["monero", "xmr"],
        "haber": '"Monero"',
    },
    {
        "slug": "zcash", "coingecko": "zcash", "ad": "Zcash", "sembol": "ZEC", "yahoo": "ZEC-USD",
        "tur": "Gizlilik odaklı para",
        "ozet": "Bitcoin benzeri, ama isteyen kullanıcının işlemlerini \"sıfır bilgi ispatı\" denen şifreleme yöntemiyle tamamen "
                "gizleyebildiği bir kripto para. Açık ve gizli işlem aynı ağda yapılabilir.",
        "kurulus": 2016, "kurucu": "Zooko Wilcox-O'Hearn (Electric Coin Company)",
        "mekanizma": "İş ispatı (madencilik).",
        "arz": "En fazla 21 milyon ZEC; Bitcoin gibi yaklaşık 4 yılda bir yeni üretim yarıya iner.",
        "ozellikler": [
            "Kullandığı şifreleme yöntemi daha sonra Ethereum ölçeklendirme çözümlerinde de yaygınlaştı.",
        ],
        "etkenler": [
            "Gizliliğe olan talep.",
            "Kripto piyasasının genel havası.",
        ],
        "riskler": [
            "Gizlilik özellikleri nedeniyle düzenleyici baskı.",
            "Son dönemde çok sert yükselip düştü.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["zcash", "zec"],
        "haber": '"Zcash"',
    },
    {
        "slug": "bittensor", "coingecko": "bittensor", "ad": "Bittensor", "sembol": "TAO", "yahoo": "TAO22974-USD",
        "tur": "Yapay zeka ağı",
        "ozet": "Yapay zeka modellerini çalıştıranları TAO ile ödüllendiren merkeziyetsiz bir ağ. Her biri farklı bir yapay zeka "
                "işine (metin, görüntü, tahmin) odaklanan alt ağlardan oluşur.",
        "kurulus": 2021, "kurucu": "Jacob Steeves ve Ala Shaabana",
        "mekanizma": "Katkı ispatı: daha faydalı yapay zeka çıktısı üretenler daha çok TAO kazanır.",
        "arz": "En fazla 21 milyon TAO; Bitcoin gibi belirli aralıklarla yeni üretim yarıya iner.",
        "ozellikler": [
            "Arz yapısı Bitcoin'den esinlenmiştir.",
        ],
        "etkenler": [
            "Yapay zeka alanındaki ilgi.",
            "Alt ağlarda üretilen işin değeri.",
        ],
        "riskler": [
            "Teknolojisi karmaşıktır ve gerçek kullanımı ölçmek zordur.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["bittensor", "tao"],
        "haber": '"Bittensor"',
    },
    {
        "slug": "shiba-inu", "coingecko": "shiba-inu", "ad": "Shiba Inu", "sembol": "SHIB", "yahoo": "SHIB-USD",
        "tur": "Meme coin",
        "ozet": "Dogecoin'in popülerliğinden esinlenerek çıkarılan, Ethereum üzerinde çalışan bir meme coin. Fiyatı bir kuruşun "
                "çok altındadır; trilyonlarca adet arzı vardır.",
        "kurulus": 2020, "kurucu": "\"Ryoshi\" takma adlı anonim bir kişi",
        "mekanizma": "Ethereum üzerinde çalışan bir token.",
        "arz": "Yaklaşık 589 trilyon SHIB; topluluk düzenli olarak bir kısmını yakar.",
        "ozellikler": [
            "Arzın yarısı başlangıçta Ethereum'un kurucusu Vitalik Buterin'e gönderildi; o da büyük kısmını yaktı ve bağışladı.",
        ],
        "etkenler": [
            "Sosyal medya ilgisi ve topluluk.",
            "Kripto piyasasının genel havası.",
        ],
        "riskler": [
            "Değeri kullanım yerine ilgiye dayandığı için çok sert dalgalanır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["shiba inu", "shib"],
        "haber": '"Shiba Inu" SHIB',
    },
    {
        "slug": "pepe", "coingecko": "pepe", "ad": "Pepe", "sembol": "PEPE", "yahoo": "PEPE24478-USD",
        "tur": "Meme coin",
        "ozet": "İnternetteki ünlü \"Pepe the Frog\" kurbağa karikatüründen adını alan, 2023'te çıkan bir meme coin. "
                "Hiçbir kullanım amacı olmadığını açıkça belirtir; değeri tamamen ilgiye dayanır.",
        "kurulus": 2023, "kurucu": "Anonim",
        "mekanizma": "Ethereum üzerinde çalışan bir token.",
        "arz": "Yaklaşık 420 trilyon PEPE; yeni üretim yok.",
        "ozellikler": [
            "Çıktıktan birkaç hafta sonra milyarlarca dolarlık piyasa değerine ulaştı.",
        ],
        "etkenler": [
            "Sosyal medya ilgisi.",
            "Riskli varlıklara iştah.",
        ],
        "riskler": [
            "Kullanım amacı yoktur; çok sert dalgalanır.",
        ],
        "cot": None, "vadeli": None, "etfler": {},
        "adlar": ["pepe"],
        "haber": '"Pepe coin"',
    },
]

KRIPTO = {k["slug"]: k for k in KRIPTOLAR}

# Elle profili olmayan coinlerin sayfasında gösterilen genel etkenler ve riskler
GENEL_ETKENLER = [
    "Kripto piyasasının genel havası: Küçük coinler çoğunlukla Bitcoin'le aynı yönde, daha sert hareket eder.",
    "Projenin kullanımı: Ağdaki uygulama, kullanıcı ve işlem sayısındaki artış ya da azalış.",
    "Borsa kararları: Büyük borsalarda listelenme ya da listeden çıkarılma.",
    "Arz takvimi: Kilitli tokenların piyasaya açılması satış baskısı yaratabilir.",
]
GENEL_RISKLER = [
    "Piyasa değeri küçük ve genç projeler çok sert dalgalanır; değerinin büyük kısmını kısa sürede kaybedebilir.",
    "Tokenların büyük kısmı kurucu ekibin ya da erken yatırımcıların elinde olabilir.",
    "Projenin tanıtımı proje ekibinin kendi açıklamasına dayanır; doğrulanmış bir değerlendirme değildir.",
]

# Liste sayfasındaki süzgeç: tür -> grup
GRUPLAR = {
    "Dijital para": "Ödeme ve para", "Ödeme ağı": "Ödeme ve para", "Gizlilik odaklı para": "Ödeme ve para",
    "Sabit para": "Sabit paralar", "Meme coin": "Meme coinler",
    "DeFi (merkeziyetsiz finans)": "Platformlar ve DeFi", "Merkeziyetsiz borsa": "Platformlar ve DeFi",
    "Akıllı sözleşme platformu": "Platformlar ve DeFi", "Borsa ve platform parası": "Platformlar ve DeFi",
    "Blokzincirleri bağlayan ağ": "Platformlar ve DeFi", "Kurumsal ağ": "Platformlar ve DeFi",
    "Veri ağı (oracle)": "Platformlar ve DeFi", "Yapay zeka ağı": "Platformlar ve DeFi",
    # Elle profili olmayan coinlerin türleri (CoinGecko kategorilerinden)
    "Altına dayalı token": "Sabit paralar",
    "Borsa tokeni": "Platformlar ve DeFi", "DeFi (kredi)": "Platformlar ve DeFi",
    "Yapay zeka": "Platformlar ve DeFi", "Gerçek varlık tokenizasyonu": "Platformlar ve DeFi",
    "Oyun": "Platformlar ve DeFi", "Ölçekleme ağı (katman 2)": "Platformlar ve DeFi",
    "Blokzincir (katman 1)": "Platformlar ve DeFi",
    "Altyapı": "Platformlar ve DeFi", "Kripto para": "Diğer",
}

# Kripto ile iş yapan, ABD borsasında işlem gören şirketler. Yöneticilerinin ve
# siyasetçilerin bu hisselerdeki işlemleri kripto sayfalarında gösterilir.
#   coin: şirketin en çok bağlı olduğu kripto para (profil sayfasında da gösterilir)
KRIPTO_SIRKETLERI = [
    {"ticker": "COIN", "ad": "Coinbase", "ne": "ABD'nin en büyük kripto borsası", "coin": None},
    {"ticker": "MSTR", "ad": "Strategy (MicroStrategy)", "ne": "Kasasında en çok Bitcoin tutan şirket", "coin": "bitcoin"},
    {"ticker": "HOOD", "ad": "Robinhood", "ne": "Hisse ve kripto alım satım uygulaması", "coin": None},
    {"ticker": "CRCL", "ad": "Circle", "ne": "USDC sabit parasını çıkaran şirket", "coin": "usd-coin"},
    {"ticker": "GLXY", "ad": "Galaxy Digital", "ne": "Kripto yatırım ve aracılık şirketi", "coin": None},
    {"ticker": "BLSH", "ad": "Bullish", "ne": "Kurumsal kripto borsası", "coin": None},
    {"ticker": "GEMI", "ad": "Gemini", "ne": "Winklevoss kardeşlerin kripto borsası", "coin": None},
    {"ticker": "BKKT", "ad": "Bakkt", "ne": "Kripto saklama ve alım satım altyapısı", "coin": None},
    {"ticker": "FIGR", "ad": "Figure Technology", "ne": "Blokzincir tabanlı kredi platformu", "coin": None},
    {"ticker": "EXOD", "ad": "Exodus", "ne": "Kripto cüzdanı", "coin": None},
    {"ticker": "MARA", "ad": "MARA Holdings", "ne": "Bitcoin madencisi", "coin": "bitcoin"},
    {"ticker": "RIOT", "ad": "Riot Platforms", "ne": "Bitcoin madencisi", "coin": "bitcoin"},
    {"ticker": "CLSK", "ad": "CleanSpark", "ne": "Bitcoin madencisi", "coin": "bitcoin"},
    {"ticker": "CORZ", "ad": "Core Scientific", "ne": "Bitcoin madencisi ve veri merkezi", "coin": "bitcoin"},
    {"ticker": "HUT", "ad": "Hut 8", "ne": "Bitcoin madencisi", "coin": "bitcoin"},
    {"ticker": "CIFR", "ad": "Cipher Mining", "ne": "Bitcoin madencisi", "coin": "bitcoin"},
    {"ticker": "IREN", "ad": "IREN", "ne": "Bitcoin madencisi ve yapay zeka veri merkezi", "coin": "bitcoin"},
    {"ticker": "BMNR", "ad": "BitMine Immersion", "ne": "Kasasında en çok Ether tutan şirket", "coin": "ethereum"},
]
SIRKET = {s["ticker"]: s for s in KRIPTO_SIRKETLERI}

# Fon kodundan coine: 'IBIT' -> 'bitcoin'
ETF_COIN = {kod: k["slug"] for k in KRIPTOLAR for kod in k["etfler"]}

# Kongre bildirimlerindeki kripto varlık adı -> coin. Uzun ifadeler önce denenir
# ('bitcoin cash' 'bitcoin'den önce).
_ADLAR = sorted(((ad, k["slug"]) for k in KRIPTOLAR for ad in k["adlar"]), key=lambda x: -len(x[0]))


def coin_bul(varlik_adi, ticker=None):
    """'Bitcoin (BTC)' -> 'bitcoin'; ticker 'IBIT' -> 'bitcoin'; tanınmazsa None."""
    if ticker and ticker.upper() in ETF_COIN:
        return ETF_COIN[ticker.upper()]
    ad = (varlik_adi or "").lower()
    for kelime, slug in _ADLAR:
        if re.search(rf"(?<![a-z]){re.escape(kelime)}(?![a-z])", ad):
            return slug
    return None
