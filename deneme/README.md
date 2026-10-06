# Deneme ve tek seferlik scriptler

Projenin ilk aşamalarında SEC verisinin yapısını anlamak için yazılan
denemeler ve bir kez çalıştırılıp işi biten düzeltme scriptleri.
Sitenin çalışması için gerekli değiller; başvuru için saklanıyorlar.

| Dosya | Ne yapıyor |
|---|---|
| `sec_dene.py` | Günlük EDGAR indeksini indirip ekrana basar |
| `sec_dene2.py` | Tek bir Form 4 belgesini ayrıştırmayı dener |
| `f13_dene.py` | 13F verisinin biçimine bakar |
| `hata_ara.py` | Anormal tutarlı kayıtların ham adet/fiyatını gösterir |
| `url_duzelt.py` | Eski ham dosya adreslerini bildirim sayfası adresine çevirir (bir kez çalıştı) |
| `veri_aktar.py` | `data/islemler.json` örnek kayıtlarını veritabanına aktarır |

Proje kökünden çalıştırılır: `python deneme/hata_ara.py`
