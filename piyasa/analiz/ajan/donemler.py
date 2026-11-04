"""
Sınama dönemleri. Dönem sınırları kural sonuçlarına bakılmadan, olayların tarihinden belirlenmiştir; sonuca bakarak
tarih seçmek kanıtı geçersiz kılar. Göstergeler bütün veriyle hesaplanır, dönem yalnızca sinyalin sayılıp sayılmayacağını
belirler. Sinyalden sonraki izleme süresi dönemin dışına taşıyorsa sinyal sayılmaz.
"""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Donem:
    kod: str
    ad: str
    bas: str
    bit: str | None
    neden: str

    def icerir(self, giris, cikis):
        """giris: sinyal günü, cikis: izlemenin bittiği gün."""
        if giris < pd.Timestamp(self.bas):
            return False
        return self.bit is None or cikis <= pd.Timestamp(self.bit)


OLAGAN = Donem("olagan", "Olağan dönem", "2020-11-01", "2026-02-27",
               "Karar bu dönemin sonucuna göre verilir: İran savaşı (Mart 2026) ve fon soruşturması (Eylül 2026) dışarıda.")
ESKI = Donem("eski", "Önceki yıllar", "2012-01-01", "2020-10-31",
             "Bağımsız ikinci sınama: kurallar yazılırken bakılmayan yıllar. 2018 kur krizi ve 2020 salgını içindedir.")
SOK = Donem("sok", "Savaş ve fon krizi", "2026-03-02", None,
            "Olağan dışı dönem: kurallar burada farklı mı davranıyor?")
TUM = Donem("tum", "Son 6 yılın tamamı", "2020-11-01", None, "Olağan dönem ile savaş ve fon krizi birlikte.")

DONEMLER = (OLAGAN, ESKI, SOK, TUM)
