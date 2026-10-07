"""Mimari kuralları ve ortak altyapı."""

import ast
from pathlib import Path

import pytest

from piyasa import onbellek

KOK = Path(__file__).resolve().parent.parent / "piyasa"


def _ice_aktarilanlar(dosya):
    agac = ast.parse(dosya.read_text(encoding="utf-8"))
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.ImportFrom) and dugum.module:
            yield dugum.module
        elif isinstance(dugum, ast.Import):
            yield from (a.name for a in dugum.names)


@pytest.mark.parametrize("dosya", sorted(
    p for p in KOK.rglob("*.py") if "web" not in p.relative_to(KOK).parts
), ids=lambda p: str(p.relative_to(KOK)))
def test_web_disindaki_katmanlar_webe_bagimli_degil(dosya):
    """Veri toplama, analiz ve emtia katmanları web katmanını içe aktarmaz."""
    web = [m for m in _ice_aktarilanlar(dosya) if m == "piyasa.web" or m.startswith("piyasa.web.")]
    # Komut satırı 'site' komutu için web'i başlatabilir
    if dosya.name == "__main__.py":
        return
    assert not web, f"{dosya.name} web katmanını içe aktarıyor: {web}"


# Katmanlar: toplama -> veritabanı -> analiz / web. Okuma katmanları (analiz, web)
# veri toplama ve bakım kodunu içe aktarmaz; veri toplama da bakım kodunu.
# Ortak sabitler ve kurallar piyasa.kurallar'dadır.
YASAKLAR = {
    "analiz": ("piyasa.toplama", "piyasa.bakim"),
    "web": ("piyasa.toplama", "piyasa.bakim"),
    "emtia": ("piyasa.toplama", "piyasa.bakim"),
    "kripto": ("piyasa.toplama", "piyasa.bakim"),
    "toplama": ("piyasa.bakim",),
}


@pytest.mark.parametrize("dosya", sorted(
    p for p in KOK.rglob("*.py") if p.relative_to(KOK).parts[0] in YASAKLAR
), ids=lambda p: str(p.relative_to(KOK)))
def test_katman_yonu(dosya):
    katman = dosya.relative_to(KOK).parts[0]
    ihlal = [m for m in _ice_aktarilanlar(dosya) if m.startswith(YASAKLAR[katman])]
    assert not ihlal, f"{dosya.relative_to(KOK)} ({katman}) şunları içe aktarmamalı: {ihlal}"


def test_sureli_onbellek(monkeypatch):
    saat = [1000.0]
    monkeypatch.setattr(onbellek.time, "monotonic", lambda: saat[0])
    cagri = []

    @onbellek.sureli(60)
    def kare(x):
        cagri.append(x)
        return x * x

    assert kare(3) == 9 and kare(3) == 9
    assert cagri == [3]                     # ikinci çağrı önbellekten
    saat[0] += 61
    assert kare(3) == 9 and cagri == [3, 3]  # süre doldu, yeniden hesaplandı
    kare.temizle()
    kare(3)
    assert cagri == [3, 3, 3]


def test_hatada_eski_sonuc(monkeypatch):
    saat = [0.0]
    monkeypatch.setattr(onbellek.time, "monotonic", lambda: saat[0])
    durum = {"hata": False}

    @onbellek.sureli(10, hatada_eskisi=True)
    def veri():
        if durum["hata"]:
            raise ConnectionError
        return "taze"

    assert veri() == "taze"
    saat[0] += 11
    durum["hata"] = True
    assert veri() == "taze"                 # ağ hatası: son başarılı sonuç
    veri.temizle()
    with pytest.raises(ConnectionError):
        veri()                              # eski sonuç da yoksa hata
