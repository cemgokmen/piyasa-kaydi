"""
KAP sektör adlarının okunur yazımı. KAP adları büyük harfle ve virgülsüz verir
('METAL EŞYA MAKİNE ELEKTRİKLİ CİHAZLAR VE ULAŞIM ARAÇLARI'); listede olmayan yeni bir
ad gelirse yalnızca küçük harfe çevrilir.
"""

from piyasa.bicim import tr_cumle

SEKTOR_ADLARI = {
    "ANA METAL SANAYİ": "Ana metal sanayi",
    "ARACI KURUMLAR": "Aracı kurumlar",
    "BALIKÇILIK VE SU ÜRÜNLERİ": "Balıkçılık ve su ürünleri",
    "BANKALAR": "Bankalar",
    "BÜRO YÖNETİMİ, BÜRO DESTEĞİ VE DİĞER ŞİRKET DESTEK FAALİYETLERİ":
        "Büro yönetimi, büro desteği ve diğer şirket destek faaliyetleri",
    "BİLGİ HİZMET FAALİYETLERİ": "Bilgi hizmetleri",
    "BİLGİ VE İLETİŞİM": "Bilgi ve iletişim",
    "BİLİŞİM": "Bilişim",
    "DİĞER MADENCİLİK VE TAŞ OCAKÇILIĞI": "Diğer madencilik ve taş ocakçılığı",
    "DİĞER İMALAT SANAYİİ": "Diğer imalat sanayii",
    "ELEKTRİK GAZ VE BUHAR": "Elektrik, gaz ve buhar",
    "ELEKTRİK GAZ VE SU": "Elektrik, gaz ve su",
    "EĞİTİM SAĞLIK SPOR VE EĞLENCE HİZMETLERİ": "Eğitim, sağlık, spor ve eğlence hizmetleri",
    "FİNANSAL KİRALAMA VE FAKTORİNG ŞİRKETLERİ": "Finansal kiralama ve faktoring şirketleri",
    "FİNANSMAN ŞİRKETLERİ": "Finansman şirketleri",
    "GAYRİMENKUL FAALİYETLERİ": "Gayrimenkul faaliyetleri",
    "GAYRİMENKUL YATIRIM ORTAKLIKLARI": "Gayrimenkul yatırım ortaklıkları",
    "GIDA, İÇECEK VE TÜTÜN": "Gıda, içecek ve tütün",
    "GİRİŞİM SERMAYESİ YATIRIM ORTAKLIKLARI": "Girişim sermayesi yatırım ortaklıkları",
    "HAM PETROL VE DOĞAL GAZ ÇIKARTILMASI": "Ham petrol ve doğal gaz çıkarımı",
    "HOLDİNGLER VE YATIRIM ŞİRKETLERİ": "Holdingler ve yatırım şirketleri",
    "HUKUK VE MUHASEBE FAALİYETLERİ": "Hukuk ve muhasebe faaliyetleri",
    "KAĞIT VE KAĞIT ÜRÜNLERİ BASIM": "Kağıt, kağıt ürünleri ve basım",
    "KONAKLAMA": "Konaklama",
    "KÖMÜR VE LİNYİT MADENCİLİĞİ": "Kömür ve linyit madenciliği",
    "KİMYA İLAÇ PETROL LASTİK VE PLASTİK ÜRÜNLER": "Kimya, ilaç, petrol, lastik ve plastik ürünler",
    "KİRALAMA VE LEASING FAALİYETLERİ": "Kiralama ve leasing",
    "MADENCİLİK VE TAŞ OCAKÇILIĞI": "Madencilik ve taş ocakçılığı",
    "MALİ KURULUŞLAR": "Mali kuruluşlar",
    "MENKUL KIYMET YATIRIM ORTAKLIKLARI": "Menkul kıymet yatırım ortaklıkları",
    "MESLEKİ, BİLİMSEL VE TEKNİK FAALİYETLER": "Mesleki, bilimsel ve teknik faaliyetler",
    "METAL CEVHERİ MADENCİLİĞİ": "Metal cevheri madenciliği",
    "METAL EŞYA MAKİNE ELEKTRİKLİ CİHAZLAR VE ULAŞIM ARAÇLARI":
        "Metal eşya, makine, elektrikli cihazlar ve ulaşım araçları",
    "MİMARLIK VE MÜHENDİSLİK FAALİYETLERİ; TEKNİK MUAYENE VE ANALİZ":
        "Mimarlık, mühendislik, teknik muayene ve analiz",
    "ORMAN ÜRÜNLERİ VE MOBİLYA": "Orman ürünleri ve mobilya",
    "OTELLER VE LOKANTALAR": "Oteller ve lokantalar",
    "PERAKENDE TİCARET": "Perakende ticaret",
    "REKLAMCILIK VE PAZAR ARAŞTIRMASI": "Reklamcılık ve pazar araştırması",
    "SAVUNMA": "Savunma",
    "SEYAHAT ACENTESİ, TUR OPERATÖRÜ VE DİĞER REZERVASYON HİZMETLERİ İLE İLGİLİ FAALİYETLER":
        "Seyahat acenteleri, tur operatörleri ve rezervasyon hizmetleri",
    "SPOR EĞLENCE BOŞ ZAMANLARI DEĞERLENDİRME HİZMETLERİ": "Spor, eğlence ve boş zaman hizmetleri",
    "SPOR FAALİYETLERİ EĞLENCE VE OYUN FAALİYETLERİ": "Spor, eğlence ve oyun faaliyetleri",
    "SİGORTA ŞİRKETLERİ": "Sigorta şirketleri",
    "TARIM VE HAYVANCILIK AVCILIK VE İLGİLİ HİZMET FAALİYETLERİ": "Tarım, hayvancılık, avcılık ve ilgili hizmetler",
    "TARIM, ORMANCILIK VE BALIKÇILIK": "Tarım, ormancılık ve balıkçılık",
    "TAŞ VE TOPRAĞA DAYALI": "Taş ve toprağa dayalı sanayi",
    "TEKNOLOJİ": "Teknoloji",
    "TEKSTİL, GİYİM EŞYASI VE DERİ": "Tekstil, giyim eşyası ve deri",
    "TELEKOMÜNİKASYON": "Telekomünikasyon",
    "TOPTAN TİCARET": "Toptan ticaret",
    "TOPTAN VE PERAKENDE TİCARET": "Toptan ve perakende ticaret",
    "ULAŞTIRMA VE DEPOLAMA": "Ulaştırma ve depolama",
    "VARLIK YÖNETİM ŞİRKETLERİ": "Varlık yönetim şirketleri",
    "YARATICI SANATLAR GÖSTERİ SANATLARI VE EĞLENCE FAALİYETLERİ":
        "Yaratıcı sanatlar, gösteri sanatları ve eğlence",
    "YAYIMCILIK": "Yayımcılık",
    "YİYECEK VE İÇECEK HİZMETLERİ": "Yiyecek ve içecek hizmetleri",
    "İDARİ VE DESTEK HİZMET FAALİYETLERİ": "İdari ve destek hizmetleri",
    "İMALAT": "İmalat",
    "İNSAN SAĞLIĞI VE SOSYAL HİZMETLER": "İnsan sağlığı ve sosyal hizmetler",
    "İNŞAAT VE BAYINDIRLIK": "İnşaat ve bayındırlık",
    "İNŞAAT VE BAYINDIRLIK İŞLERİ": "İnşaat ve bayındırlık işleri",
}


def sektor_adi(ad):
    """'METAL EŞYA MAKİNE ...' -> 'Metal eşya, makine, elektrikli cihazlar ve ulaşım araçları'"""
    if not ad:
        return None
    return SEKTOR_ADLARI.get(ad.strip()) or tr_cumle(ad)
