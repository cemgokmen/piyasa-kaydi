"""
Takip edilen emtialar ve onları etkileyen göstergeler.

Her emtia için:
  yahoo   Yahoo Finance vadeli işlem kodu (fiyat ve hacim)
  birim   Fiyatın birimi
  cot     CFTC raporundaki sözleşme kodu (büyük fonların konumu); yoksa None
  eia     ABD Enerji Bilgi İdaresi haftalık stok serisi; yoksa None
  haber   Google Haberler'de aranacak Türkçe ifade
"""

ONS_GRAM = 31.1034768   # 1 troy ons kaç gram

EMTIALAR = [
    {
        "slug": "altin", "ad": "Altın", "grup": "Değerli metaller",
        "yahoo": "GC=F", "birim": "$/ons", "cot": "088691", "eia": None,
        "haber": '"ons altın" OR "altın talebi" OR "merkez bankaları altın" OR "altın rezervi"',
        "etkenler": [
            "Faizler: Faiz düştükçe getirisi olmayan altının cazibesi artar; Fed kararları en güçlü etkendir.",
            "Dolar: Altın dolarla fiyatlanır; dolar zayıfladığında altın genellikle yükselir.",
            "Merkez bankası alımları: Özellikle Çin, Türkiye, Polonya gibi ülkelerin rezerv alımları talebi destekler.",
            "Belirsizlik: Savaş, kriz ve enflasyon dönemlerinde güvenli liman talebi artar.",
        ],
    },
    {
        "slug": "gumus", "ad": "Gümüş", "grup": "Değerli metaller",
        "yahoo": "SI=F", "birim": "$/ons", "cot": "084691", "eia": None,
        "haber": '"gümüş fiyatları" OR "ons gümüş"',
        "etkenler": [
            "Hem değerli hem sanayi metali: Talebin yarıdan fazlası güneş paneli ve elektronik sanayisinden gelir.",
            "Altınla birlikte hareket eder ama daha oynaktır; altın/gümüş oranı izlenir.",
            "Faiz ve dolar altındaki gibi etkiler.",
        ],
    },
    {
        "slug": "platin", "ad": "Platin", "grup": "Değerli metaller",
        "yahoo": "PL=F", "birim": "$/ons", "cot": "076651", "eia": None,
        "haber": '"platin fiyatı" OR platin',
        "etkenler": [
            "Arzın büyük kısmı Güney Afrika ve Rusya'dan gelir; madencilik grevleri ve yaptırımlar fiyatı etkiler.",
            "Talep ağırlıkla otomotiv (katalitik konvertör) ve hidrojen teknolojilerinden gelir.",
        ],
    },
    {
        "slug": "bakir", "ad": "Bakır", "grup": "Sanayi metalleri",
        "yahoo": "HG=F", "birim": "$/libre", "cot": "085692", "eia": None,
        "haber": '"bakır fiyatları" OR "bakır talebi"',
        "etkenler": [
            "Küresel büyümenin göstergesi kabul edilir; inşaat, elektrik şebekesi ve elektrikli araçlarda kullanılır.",
            "Çin dünya talebinin yaklaşık yarısını oluşturur; Çin ekonomisine dair haberler fiyatı hızla etkiler.",
            "Şili ve Peru'daki maden üretimi arz tarafını belirler.",
        ],
    },
    {
        "slug": "brent", "ad": "Brent petrol", "grup": "Enerji",
        "yahoo": "BZ=F", "birim": "$/varil", "cot": "067651", "eia": "ham_petrol",
        # Brent'in fon verisini Londra borsası (ICE) yayımlar; CFTC'de yok.
        # Fiyatı Brent'le birlikte hareket eden ABD ham petrolünün (WTI) fon verisi gösterilir.
        "cot_notu": "Brent'in fon verisi Londra borsasında yayımlandığı için, Brent'le birlikte hareket eden ABD ham petrolünün (WTI) fon verisi gösteriliyor.",
        "haber": '"brent petrol" OR "petrol fiyatları" OR OPEC',
        "etkenler": [
            "Türkiye için önemi: Akaryakıt pompa fiyatları ve enerji ithalat faturası Brent'e bağlıdır.",
            "OPEC+ kararları: Üretim kotaları arzı doğrudan belirler.",
            "Stoklar: ABD ham petrol stokları (haftalık EIA verisi) beklenenden fazla artarsa fiyat baskılanır.",
            "Jeopolitik: Orta Doğu'daki gerilimler, Hürmüz Boğazı ve tanker taşımacılığı, Rusya ve İran'a yaptırımlar arzı daraltabilir.",
            "Talep: Küresel büyüme ve özellikle Çin'in petrol ithalatı.",
        ],
    },
]

EMTIA = {e["slug"]: e for e in EMTIALAR}
GRUPLAR = ["Değerli metaller", "Enerji", "Sanayi metalleri"]

# Emtiaları etkileyen genel göstergeler (Yahoo kodları)
GOSTERGELER = {
    "dolar_endeksi": {"yahoo": "DX-Y.NYB", "ad": "Dolar endeksi (DXY)"},
    "usdtry": {"yahoo": "TRY=X", "ad": "Dolar/TL"},
}

# FRED (ABD Merkez Bankası St. Louis) serileri
FRED_SERILERI = {
    "fed_faiz": "DFEDTARU",       # Fed politika faizi üst sınırı
    "abd_10y": "DGS10",           # ABD 10 yıllık tahvil faizi
    "reel_faiz": "DFII10",        # 10 yıllık enflasyona endeksli (reel) faiz
}

# EIA haftalık stok serileri
EIA_SERILERI = {
    "ham_petrol": {
        "url": "https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls",
        "ad": "ABD ticari ham petrol stokları",
        "birim": "milyon varil",
        "bolen": 1000,   # kaynak bin varil
    },
}

# Haber başlıklarını konuya göre etiketleme (küçük harfle aranır)
HABER_ETIKETLERI = [
    ("Merkez bankası", ["fed", "faiz", "merkez bankası", "tcmb", "powell", "ecb", "fomc"]),
    ("OPEC", ["opec"]),
    ("Yaptırım / gümrük", ["yaptırım", "ambargo", "gümrük", "tarife", "ihracat yasağı", "kota"]),
    ("Arz", ["üretim", "arz", "stok", "maden", "rafineri", "hasat", "rezerv"]),
    ("Talep", ["talep", "ithalat", "tüketim", "alım"]),
    ("Jeopolitik", ["savaş", "saldırı", "gerilim", "ateşkes", "iran", "rusya", "ukrayna", "israil", "kızıldeniz", "hürmüz"]),
]
