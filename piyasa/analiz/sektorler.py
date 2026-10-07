"""
SEC sanayi sınıflandırma kodlarını (SIC) sektörlere, Temsilciler Meclisi
komitelerini de denetledikleri sektörlere eşler. Çıkar çatışması analizi
bu iki eşlemeyi kullanır.
"""

# (sektör, [(ilk SIC, son SIC), ...]). Sıra önemli: ilk eşleşen kazanır.
SIC_SEKTORLERI = [
    ("Savunma ve havacılık", [(3720, 3729), (3760, 3769), (3812, 3812), (3480, 3489), (3795, 3795)]),
    ("Sağlık", [(2830, 2836), (3841, 3851), (5047, 5047), (5122, 5122), (6324, 6324), (8000, 8099)]),
    ("Enerji", [(1300, 1399), (2900, 2999), (4610, 4619), (5171, 5172)]),
    ("Kamu hizmetleri", [(4900, 4999)]),
    ("Tarım ve gıda", [(100, 999), (2000, 2099), (2870, 2879), (5140, 5159)]),
    ("Otomotiv", [(3711, 3716)]),
    ("Ulaştırma", [(3740, 3749), (4000, 4799)]),
    ("İletişim ve medya", [(2710, 2799), (4800, 4899), (7810, 7819)]),
    ("Teknoloji", [(3570, 3579), (3600, 3699), (3820, 3829), (7370, 7379)]),
    ("Gayrimenkul", [(6500, 6599), (6798, 6798)]),
    ("Finans", [(6000, 6499), (6700, 6799)]),
    ("Madencilik ve malzeme", [(1000, 1299), (1400, 1499), (2600, 2699), (2800, 2899), (3300, 3399)]),
    ("İnşaat", [(1500, 1799), (3240, 3299)]),
    ("Perakende", [(5200, 5999)]),
    ("Eğitim", [(8200, 8299)]),
    ("Sanayi", [(2100, 3999), (5000, 5199)]),
]


def sic_sektoru(sic):
    if sic is None:
        return None
    for ad, araliklar in SIC_SEKTORLERI:
        if any(bas <= sic <= son for bas, son in araliklar):
            return ad
    return "Diğer"


# Kongre komitesi (Temsilciler Meclisi: H..., Senato: S...) → yasama ve
# denetim alanına giren sektörler.
# Bütçe, Kurallar, Etik gibi her sektöre dokunan komiteler bilerek dışarıda.
KOMITE_SEKTORLERI = {
    "HSAS": ["Savunma ve havacılık"],                                   # Silahlı Kuvvetler
    "HSAG": ["Tarım ve gıda"],                                          # Tarım
    "HSBA": ["Finans", "Gayrimenkul"],                                  # Finansal Hizmetler
    "HSIF": ["Enerji", "Kamu hizmetleri", "Sağlık", "İletişim ve medya"],  # Enerji ve Ticaret
    "HSII": ["Enerji", "Madencilik ve malzeme"],                        # Doğal Kaynaklar
    "HSPW": ["Ulaştırma", "İnşaat"],                                    # Ulaştırma ve Altyapı
    "HSSY": ["Teknoloji", "Savunma ve havacılık"],                      # Bilim, Uzay ve Teknoloji
    "HSVR": ["Sağlık"],                                                 # Gaziler
    "HSHM": ["Savunma ve havacılık", "Teknoloji"],                      # İç Güvenlik
    "HLIG": ["Savunma ve havacılık", "Teknoloji"],                      # İstihbarat
    "HSWM": ["Sağlık"],                                                 # Vergi ve Bütçe (sağlık alt komitesi)
    "HSED": ["Eğitim"],                                                 # Eğitim
    "HSZS": ["Teknoloji"],                                              # Çin ile Stratejik Rekabet
    # Senato
    "SSAS": ["Savunma ve havacılık"],                                   # Silahlı Kuvvetler
    "SSAF": ["Tarım ve gıda"],                                          # Tarım, Beslenme ve Ormancılık
    "SSBK": ["Finans", "Gayrimenkul"],                                  # Bankacılık, Konut ve Kentsel İşler
    "SSCM": ["Ulaştırma", "Teknoloji", "İletişim ve medya"],            # Ticaret, Bilim ve Ulaştırma
    "SSEG": ["Enerji", "Madencilik ve malzeme", "Kamu hizmetleri"],     # Enerji ve Doğal Kaynaklar
    "SSEV": ["İnşaat", "Ulaştırma"],                                    # Çevre ve Bayındırlık
    "SSFI": ["Sağlık"],                                                 # Maliye (Medicare, ilaç fiyatları)
    "SSHR": ["Sağlık", "Eğitim"],                                       # Sağlık, Eğitim, Çalışma ve Emeklilik
    "SSGA": ["Savunma ve havacılık", "Teknoloji"],                      # İç Güvenlik ve Hükümet İşleri
    "SLIN": ["Savunma ve havacılık", "Teknoloji"],                      # İstihbarat
    "SSVA": ["Sağlık"],                                                 # Gaziler
}

KOMITE_ADLARI = {
    "HSAS": "Silahlı Kuvvetler Komitesi",
    "HSAG": "Tarım Komitesi",
    "HSBA": "Finansal Hizmetler Komitesi",
    "HSIF": "Enerji ve Ticaret Komitesi",
    "HSII": "Doğal Kaynaklar Komitesi",
    "HSPW": "Ulaştırma ve Altyapı Komitesi",
    "HSSY": "Bilim, Uzay ve Teknoloji Komitesi",
    "HSVR": "Gaziler Komitesi",
    "HSHM": "İç Güvenlik Komitesi",
    "HLIG": "İstihbarat Komitesi",
    "HSWM": "Vergi ve Bütçe (Ways and Means) Komitesi",
    "HSED": "Eğitim ve İş Gücü Komitesi",
    "HSZS": "Çin ile Stratejik Rekabet Komitesi",
    "HSAP": "Ödenekler Komitesi",
    "HSBU": "Bütçe Komitesi",
    "HSFA": "Dış İlişkiler Komitesi",
    "HSGO": "Denetim ve Hükümet Reformu Komitesi",
    "HSHA": "Meclis İdaresi Komitesi",
    "HSJU": "Yargı Komitesi",
    "HSRU": "Kurallar Komitesi",
    "HSSM": "Küçük İşletmeler Komitesi",
    "HSSO": "Etik Komitesi",
    "SSAS": "Senato Silahlı Kuvvetler Komitesi",
    "SSAF": "Senato Tarım Komitesi",
    "SSBK": "Senato Bankacılık Komitesi",
    "SSCM": "Senato Ticaret, Bilim ve Ulaştırma Komitesi",
    "SSEG": "Senato Enerji ve Doğal Kaynaklar Komitesi",
    "SSEV": "Senato Çevre ve Bayındırlık Komitesi",
    "SSFI": "Senato Maliye Komitesi",
    "SSHR": "Senato Sağlık, Eğitim ve Çalışma Komitesi",
    "SSGA": "Senato İç Güvenlik Komitesi",
    "SLIN": "Senato İstihbarat Komitesi",
    "SSVA": "Senato Gaziler Komitesi",
    "SSAP": "Senato Ödenekler Komitesi",
    "SSBU": "Senato Bütçe Komitesi",
    "SSFR": "Senato Dış İlişkiler Komitesi",
    "SSJU": "Senato Yargı Komitesi",
    "SSRA": "Senato Kurallar Komitesi",
    "SSSB": "Senato Küçük İşletmeler Komitesi",
    "SLET": "Senato Etik Komitesi",
    "SLIA": "Senato Kızılderili İşleri Komitesi",
    "SPAG": "Senato Yaşlanma Komitesi",
}
