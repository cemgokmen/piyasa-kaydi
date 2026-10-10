"""
Haber kartları için fotoğraf: Pexels (ücretsiz; fotoğraflar ticari kullanım dahil izinsiz kullanılabilir).

Haberin başlığındaki konuya göre İngilizce bir arama yapılır (altın → külçe altın, akaryakıt →
benzin pompası, Fed → merkez bankası binası...). Her habere farklı fotoğraf düşsün diye son 14 günde
kullanılan fotoğraflar seçilmez. Fotoğraf indirilip saklanır ve karta gömülür (görsel PNG olarak
indirilirken dışarıdan resim yüklenemez).

Anahtar data/pexels.env dosyasındadır:   PEXELS_API_KEY=...
Anahtar yoksa kartlar sitenin kendi konu çizimleriyle hazırlanır.
"""

import base64
import hashlib
import re
from datetime import UTC, datetime, timedelta

import requests

from piyasa.ayarlar import VERI_DIZINI

ANAHTAR_DOSYASI = VERI_DIZINI / "pexels.env"
KLASOR = VERI_DIZINI / "haber_gorselleri"
ARAMA = "https://api.pexels.com/v1/search"
TEKRAR_GUN = 14

# (Türkçe kök, İngilizce arama) — başlıkta ilk eşleşen kullanılır; sıra önemlidir (özelden genele)
ESLESMELER = [
    ("gümüş", "silver bullion bars"), ("altın", "gold bars bullion"), ("ons", "gold bullion"),
    ("tanker", "oil tanker ship sea"), ("akaryakıt", "gas station fuel pump"), ("benzin", "fuel pump gas station"),
    ("motorin", "diesel fuel pump"), ("doğal gaz", "natural gas pipeline"), ("doğalgaz", "natural gas pipeline"),
    ("elektrik", "electricity power lines"), ("petrol", "oil pump jack"), ("brent", "oil refinery"),
    ("opec", "oil barrels"), ("bitcoin", "bitcoin coin"), ("kripto", "cryptocurrency"),
    ("fed", "federal reserve building washington"), ("ecb", "european central bank frankfurt"),
    ("merkez bankası", "central bank building"), ("tcmb", "istanbul financial district"),
    ("enflasyon", "supermarket shopping prices"), ("faiz", "interest rates finance"),
    ("tahvil", "government bonds finance"), ("borsa istanbul", "istanbul stock exchange"),
    ("bist", "stock market chart screen"), ("wall street", "wall street new york"), ("nasdaq", "nasdaq stock market"),
    ("hisse", "stock market trading screen"), ("borsa", "stock market trading"), ("halka arz", "stock exchange ipo"),
    ("ihracat", "container ship port"), ("ithalat", "cargo containers port"), ("gümrük", "shipping containers"),
    ("otomotiv", "car factory production"), ("otomobil", "cars dealership"), ("konut", "apartment buildings"),
    ("kira", "apartment rent keys"), ("turizm", "istanbul tourism"), ("çay", "tea plantation"),
    ("buğday", "wheat field harvest"), ("tarım", "agriculture field"), ("fındık", "hazelnuts"),
    ("banka", "bank building"), ("kredi", "credit card payment"), ("sigorta", "insurance documents"),
    ("emekli", "retired senior couple"), ("maaş", "salary money"), ("asgari ücret", "workers salary"),
    ("vergi", "tax documents calculator"), ("bütçe", "government budget"), ("imf", "imf headquarters"),
    # Kur: yalnızca kur haberi ifadeleri ("milyon dolar" kur haberi değildir)
    ("dolar/tl", "us dollar banknotes"), ("doların", "us dollar banknotes"), ("dolar kuru", "us dollar banknotes"),
    ("dolar endeks", "us dollar banknotes"), ("euro/tl", "euro banknotes"), ("avro/tl", "euro banknotes"),
    ("döviz", "currency exchange office"), ("kur", "currency exchange"),
    ("çin", "shanghai skyline"), ("abd", "washington capitol"), ("avrupa", "european union flags"),
    ("rusya", "moscow skyline"), ("japonya", "tokyo skyline"), ("almanya", "frankfurt skyline"),
    ("teknoloji", "technology chip"), ("yapay zeka", "artificial intelligence"), ("çip", "semiconductor chip"),
]
KONU_ARAMASI = {"faiz": "central bank finance", "doviz": "currency exchange", "borsa": "stock market",
                "enerji": "energy industry", "kripto": "cryptocurrency", "dunya": "global economy",
                "ekonomi": "economy business"}


def anahtar():
    try:
        for s in ANAHTAR_DOSYASI.read_text().splitlines():
            if s.strip().startswith("PEXELS_API_KEY=") and s.split("=", 1)[1].strip():
                return s.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def arama_sozcugu(baslik, konu="ekonomi"):
    """Başlığa uygun İngilizce fotoğraf araması."""
    b = baslik.replace("I", "ı").replace("İ", "i").lower()
    for kok, sorgu in ESLESMELER:
        if re.search(r"(?<![a-zçğıöşü])" + re.escape(kok) + (r"(?![a-zçğıöşü])" if len(kok) <= 3 else ""), b):
            if kok == "altın" and re.search(r"altın(d[ae]|dan|a\b)", b):
                continue
            return sorgu
    return KONU_ARAMASI.get(konu, "economy business")


def _tablo(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS haber_gorsel (
        adres TEXT PRIMARY KEY, foto_id INTEGER, dosya TEXT, fotografci TEXT, sayfa TEXT, zaman TEXT)""")


def foto(conn, haber):
    """{'veri': 'data:image/jpeg;base64,...', 'fotografci': ...}; anahtar yoksa ya da bulunamazsa None."""
    _tablo(conn)
    kayit = conn.execute("SELECT dosya, fotografci FROM haber_gorsel WHERE adres = ?", (haber["adres"],)).fetchone()
    if kayit and (KLASOR / kayit[0]).exists():
        return _veri(kayit[0], kayit[1])
    a = anahtar()
    if not a:
        return None
    try:
        cevap = requests.get(ARAMA, params={"query": arama_sozcugu(haber["baslik"], haber.get("konu")),
                                            "orientation": "landscape", "per_page": 30},
                             headers={"Authorization": a}, timeout=15)
        cevap.raise_for_status()
        fotolar = cevap.json().get("photos", [])
    except Exception:
        return None
    sinir = (datetime.now(UTC) - timedelta(days=TEKRAR_GUN)).isoformat()
    kullanilan = {r[0] for r in conn.execute("SELECT foto_id FROM haber_gorsel WHERE zaman >= ?", (sinir,))}
    adaylar = [f for f in fotolar if f["id"] not in kullanilan] or fotolar
    if not adaylar:
        return None
    # Aynı haber hep aynı fotoğrafı alsın, farklı haberler farklısını
    secilen = adaylar[int(hashlib.sha1(haber["adres"].encode()).hexdigest(), 16) % min(len(adaylar), 8)]
    try:
        resim = requests.get(secilen["src"]["landscape"], timeout=20)
        resim.raise_for_status()
    except Exception:
        return None
    KLASOR.mkdir(parents=True, exist_ok=True)
    dosya = f"{secilen['id']}.jpg"
    (KLASOR / dosya).write_bytes(resim.content)
    conn.execute("INSERT OR REPLACE INTO haber_gorsel VALUES (?, ?, ?, ?, ?, ?)",
                 (haber["adres"], secilen["id"], dosya, secilen.get("photographer"), secilen.get("url"),
                  datetime.now(UTC).isoformat()))
    conn.commit()
    return _veri(dosya, secilen.get("photographer"))


def _veri(dosya, fotografci):
    icerik = (KLASOR / dosya).read_bytes()
    return {"veri": "data:image/jpeg;base64," + base64.b64encode(icerik).decode(), "fotografci": fotografci}
