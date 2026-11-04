"""
Ajan: okunan kaynaklardaki al-sat iddialarını kural olarak tutar, geçmişte sınar ve yalnızca kanıtı
olanları dikkate alır.

Yeni kaynak eklemek:
  1. Dosya analiz_ajani/pdf/ klasörüne konur, notlar analiz_ajani/notlar/<ad>-<yıl>.md dosyasına yazılır.
  2. piyasa/analiz/ajan/kaynaklar/<ad><yıl>.py dosyasında kurallar @kural ile tanımlanır; başka kayıt gerekmez.
  3. python -m piyasa ajan-sina çalıştırılır: kural kanıtını kazanır, raporda kaynağıyla görünür.
"""

import importlib
import pkgutil

from piyasa.analiz.ajan import kaynaklar
from piyasa.analiz.ajan.kural import KURALLAR, Baglam, Kural, kural  # noqa: F401

for _m in pkgutil.iter_modules(kaynaklar.__path__):
    importlib.import_module(f"{kaynaklar.__name__}.{_m.name}")
