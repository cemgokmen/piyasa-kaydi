"""
Kural: bir kaynaktan (tez, kitap, ders notu) alınmış tek bir al-sat iddiası.

Kaynağın söylediği sınanacak bir iddiadır, doğru kabul edilmez. Bu yüzden her kural aynı biçimdedir:
geçmişin her günü için +1 (AL), −1 (SAT) ya da 0 (sinyal yok) döndüren bir fonksiyon. Aynı fonksiyon
hem bugünü okur hem geçmişi sınar (sinama.py); kural geleceği göremez (test_ajan bunu her kural için denetler).
"""

from dataclasses import dataclass
from functools import cached_property

import numpy as np
import pandas as pd

from piyasa.analiz.teknik.cizgiler import klasik_formasyonlar, trend_cizgileri
from piyasa.analiz.teknik.yapi import zigzag_teyitli


@dataclass(frozen=True)
class Kaynak:
    kod: str
    atif: str               # "Altay 1997"
    tam: str                # künye
    notlar: str             # depodaki not dosyası


@dataclass(frozen=True)
class Kural:
    kimlik: str
    ad: str
    kaynak: Kaynak
    sayfa: str
    aile: str               # osilator | trend | formasyon | hacim
    ufuk: int               # sınanan gün sayısı: kısa göstergeler kısa, trend araçları uzun vade
    al: str                 # AL sinyalinin sade anlatımı
    sat: str
    fonksiyon: object
    gecerlilik: int = 5     # sinyal bugünden kaç gün geriye kadar "güncel" sayılır


class Baglam:
    """Kuralların ortak girdisi: fiyat, gösterge tablosu ve bir kez hesaplanan tepe-dip türevleri."""

    def __init__(self, df, g):
        self.df, self.g = df, g

    @cached_property
    def noktalar(self):
        return zigzag_teyitli(self.df, self.g["atr"])[0]

    @cached_property
    def cizgiler(self):
        return trend_cizgileri(self.df, self.noktalar)

    @cached_property
    def formasyonlar(self):
        return klasik_formasyonlar(self.df, self.noktalar, self.g["atr"])

    def bos(self):
        return pd.Series(0.0, index=self.df.index)


KURALLAR = {}


def kural(kimlik, ad, kaynak, sayfa, aile, ufuk, al, sat, gecerlilik=5):
    def sar(f):
        KURALLAR[kimlik] = Kural(kimlik, ad, kaynak, sayfa, aile, ufuk, al, sat, f, gecerlilik)
        return f
    return sar


# ---------------------------------------------------------------------------
# Kural yazarken kullanılan kısayollar
# ---------------------------------------------------------------------------

def yukari_kesti(s, seviye):
    seviye = seviye if hasattr(seviye, "shift") else pd.Series(seviye, index=s.index)
    return (s > seviye) & (s.shift(1) <= seviye.shift(1))


def asagi_kesti(s, seviye):
    seviye = seviye if hasattr(seviye, "shift") else pd.Series(seviye, index=s.index)
    return (s < seviye) & (s.shift(1) >= seviye.shift(1))


def sinyal(al, sat):
    """İki koşuldan +1/−1/0 serisi; ikisi birden doğruysa sinyal yok."""
    return pd.Series(np.where(al & ~sat, 1.0, np.where(sat & ~al, -1.0, 0.0)), index=al.index)
