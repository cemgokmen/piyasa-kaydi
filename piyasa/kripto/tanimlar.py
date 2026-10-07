"""
Takip edilen kripto paralar ve profilleri.

Her coin için:
  yahoo       Yahoo Finance kodu (fiyat, piyasa değeri, arz)
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
        "slug": "bitcoin", "ad": "Bitcoin", "sembol": "BTC", "yahoo": "BTC-USD",
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
        "slug": "ethereum", "ad": "Ethereum", "sembol": "ETH", "yahoo": "ETH-USD",
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
        "slug": "xrp", "ad": "XRP", "sembol": "XRP", "yahoo": "XRP-USD",
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
        "slug": "bnb", "ad": "BNB", "sembol": "BNB", "yahoo": "BNB-USD",
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
        "slug": "solana", "ad": "Solana", "sembol": "SOL", "yahoo": "SOL-USD",
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
        "slug": "dogecoin", "ad": "Dogecoin", "sembol": "DOGE", "yahoo": "DOGE-USD",
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
        "slug": "tron", "ad": "TRON", "sembol": "TRX", "yahoo": "TRX-USD",
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
        "slug": "cardano", "ad": "Cardano", "sembol": "ADA", "yahoo": "ADA-USD",
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
        "slug": "chainlink", "ad": "Chainlink", "sembol": "LINK", "yahoo": "LINK-USD",
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
        "slug": "avalanche", "ad": "Avalanche", "sembol": "AVAX", "yahoo": "AVAX-USD",
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
        "slug": "stellar", "ad": "Stellar", "sembol": "XLM", "yahoo": "XLM-USD",
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
        "slug": "litecoin", "ad": "Litecoin", "sembol": "LTC", "yahoo": "LTC-USD",
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
        "slug": "bitcoin-cash", "ad": "Bitcoin Cash", "sembol": "BCH", "yahoo": "BCH-USD",
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
        "slug": "polkadot", "ad": "Polkadot", "sembol": "DOT", "yahoo": "DOT-USD",
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
]

KRIPTO = {k["slug"]: k for k in KRIPTOLAR}

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
