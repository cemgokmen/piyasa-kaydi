"""
Borsa İstanbul fiyatları (Yahoo Finance, ücretsiz; borsa saatinde yaklaşık 15 dakika gecikmeli).

  fiyatlar(kodlar)  Borsa İstanbul hisselerinin son fiyatı, günlük / haftalık / yıllık değişimi ve
                    küçük grafik için son 3 ayın kapanışları
  yahoo_kodu(kod)   'THYAO' -> 'THYAO.IS'

Yüzlerce hissenin indirilmesi dakikaları bulabildiği için sayfa beklemez: fiyatlar arka planda
100'erli parçalar halinde tazelenir, sayfa elde olan en son veriyi gösterir.

İnternet kotasını korumak için:
  - Fiyatlar yalnızca borsa açıkken (hafta içi 10:00–18:35, gecikme payıyla) 20 dakikada bir
    tazelenir; kapanıştan sonra bir kez daha alınır, gece ve hafta sonu hiç indirilmez.
  - Bir yıllık geçmiş günde bir kez indirilir; gün içinde yalnızca son 5 gün indirilip saklanan
    geçmişe eklenir.
  - Sitenin işçileri aynı veriyi ayrı ayrı indirmez: indirmeyi kilidi alan tek süreç yapar ve
    sonucu data/bist_fiyatlari.json dosyasına yazar, diğerleri oradan okur.
"""

import fcntl
import json
import os
import threading
import time
from datetime import date, datetime, timedelta
from datetime import time as saat

import pandas as pd
import yfinance as yf

from piyasa.ayarlar import VERI_DIZINI

ENDEKSLER = ("XU100.IS", "XU030.IS")
TAZELIK = 20 * 60          # saniye: borsa açıkken
TAM_TAZELIK = 20 * 3600    # bir yıllık geçmiş en çok bu kadar eskiyse yeniden indirilir
PARCA = 100
ACILIS, KAPANIS = saat(10, 0), saat(18, 35)   # kapanış: 18:10 + Yahoo'nun ~15 dk gecikmesi + pay
DOSYA = VERI_DIZINI / "bist_fiyatlari.json"
KILIT = VERI_DIZINI / "bist_fiyatlari.kilit"

# seri: {'THYAO': {'t': ['2026-10-08', ...], 'c': [300.5, ...]}} — bir yıllık günlük kapanışlar
_durum = {"zaman": 0.0, "tam": 0.0, "seri": {}, "veri": {}, "dosya": 0.0, "calisiyor": False}
_kilit = threading.Lock()


def yahoo_kodu(kod):
    return f"{kod.upper()}.IS"


# ---------------------------------------------------------------------------
# Borsa saatleri
# ---------------------------------------------------------------------------

def borsa_acik(simdi=None):
    simdi = simdi or datetime.now()
    return simdi.weekday() < 5 and ACILIS <= simdi.time() <= KAPANIS


def son_kapanis(simdi=None):
    """En son biten seansın (gecikme payıyla) bitiş anı."""
    simdi = simdi or datetime.now()
    gun = simdi.date()
    if simdi.time() < KAPANIS:
        gun -= timedelta(days=1)
    while gun.weekday() >= 5:
        gun -= timedelta(days=1)
    return datetime.combine(gun, KAPANIS)


def gerekli_mi(simdi=None, zaman=None):
    """Fiyatlar indirilmeli mi? zaman: son başarılı indirmenin Unix zamanı."""
    simdi = simdi or datetime.now()
    zaman = _durum["zaman"] if zaman is None else zaman
    if not zaman:
        return True
    son = datetime.fromtimestamp(zaman)
    if borsa_acik(simdi):
        return (simdi - son).total_seconds() > TAZELIK
    return son < son_kapanis(simdi)           # kapanıştan sonra bir kez


# ---------------------------------------------------------------------------
# İndirme ve hesap
# ---------------------------------------------------------------------------

def _indir(kodlar, donem="1y"):
    """{'THYAO.IS': {'t': [...], 'c': [...]}} — Yahoo'dan günlük kapanışlar, tek toplu istekte."""
    tablo = yf.download(list(kodlar), period=donem, interval="1d", auto_adjust=True, group_by="ticker",
                        threads=True, progress=False, timeout=20)
    sonuc = {}
    for kod in kodlar:
        try:
            seri = tablo[kod]["Close"].dropna() if isinstance(tablo.columns, pd.MultiIndex) else tablo["Close"].dropna()
        except KeyError:
            continue
        if len(seri):
            sonuc[kod] = {"t": [i.strftime("%Y-%m-%d") for i in seri.index], "c": [float(v) for v in seri]}
    return sonuc


def _birlestir(eski, yeni):
    """Saklanan bir yıllık seriye son günleri ekler (aynı gün varsa yenisi geçerli), bir yıldan eskiyi atar."""
    gunler = dict(zip(eski["t"], eski["c"], strict=True)) if eski else {}
    gunler.update(zip(yeni["t"], yeni["c"], strict=True))
    sinir = (date.today() - timedelta(days=366)).isoformat()
    t = sorted(g for g in gunler if g >= sinir)
    return {"t": t, "c": [gunler[g] for g in t]}


def _degisim(c, gun):
    """Son kapanışın 'gun' işlem günü önceki kapanışa göre değişimi."""
    if len(c) <= gun:
        return None
    onceki = c[-1 - gun]
    return c[-1] / onceki - 1 if onceki else None


def _ozet(s):
    c = s["c"]
    if len(c) < 2:
        return None
    return {
        "fiyat": c[-1], "tarih": s["t"][-1],
        "g1": _degisim(c, 1), "h1": _degisim(c, 5), "a1": _degisim(c, 21),
        "y1": c[-1] / c[0] - 1 if c[0] else None,
        "seri": c[-63:],
    }


def _hesapla(seriler):
    return {k: o for k, s in seriler.items() if (o := _ozet(s))}


# ---------------------------------------------------------------------------
# Süreçler arası paylaşım
# ---------------------------------------------------------------------------

def _dosyadan_oku():
    """Başka bir sürecin indirdiği daha yeni veri varsa belleğe alır."""
    try:
        degisme = os.path.getmtime(DOSYA)
    except OSError:
        return
    if degisme <= _durum["dosya"]:
        return
    try:
        veri = json.loads(DOSYA.read_text())
    except (OSError, ValueError):
        return
    _durum.update(zaman=veri.get("zaman", 0.0), tam=veri.get("tam", 0.0), seri=veri.get("seri", {}),
                  dosya=degisme)
    _durum["veri"] = _hesapla(_durum["seri"])


def _dosyaya_yaz():
    gecici = DOSYA.with_suffix(".tmp")
    gecici.write_text(json.dumps({"zaman": _durum["zaman"], "tam": _durum["tam"], "seri": _durum["seri"]},
                                 separators=(",", ":")))
    os.replace(gecici, DOSYA)
    _durum["dosya"] = os.path.getmtime(DOSYA)


def tazele(kodlar, zorla=False):
    """Fiyatları indirip saklar. Aynı anda (bütün süreçlerde) yalnızca bir indirme çalışır."""
    with _kilit:
        if _durum["calisiyor"]:
            return
        _durum["calisiyor"] = True
    try:
        KILIT.parent.mkdir(parents=True, exist_ok=True)
        with open(KILIT, "w") as kilit_dosyasi:
            try:
                fcntl.flock(kilit_dosyasi, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return                                    # başka süreç indiriyor; sonucu dosyadan okunur
            _dosyadan_oku()
            if not zorla and not gerekli_mi():
                return
            tam = time.time() - _durum["tam"] > TAM_TAZELIK
            # Endeksler ve (çağıranın öne koyduğu) büyük hisseler ilk parçada gelir
            yahoo = list(ENDEKSLER) + [yahoo_kodu(k) for k in kodlar if yahoo_kodu(k) not in ENDEKSLER]
            yahoo = list(dict.fromkeys(yahoo))
            seri = dict(_durum["seri"])
            for i in range(0, len(yahoo), PARCA):
                parca = yahoo[i:i + PARCA]
                # Geçmişi elde olmayan hisseler gün içinde de bir yıllık indirilir
                eksik = [k for k in parca if k.removesuffix(".IS") not in seri]
                istekler = [(parca, "1y")] if tam else [(eksik, "1y"), ([k for k in parca if k not in eksik], "5d")]
                for liste, donem in istekler:
                    if not liste:
                        continue
                    try:
                        veri = _indir(liste, donem)
                    except Exception:
                        continue
                    for k, s in veri.items():
                        kod = k.removesuffix(".IS")
                        seri[kod] = s if donem == "1y" else _birlestir(seri.get(kod), s)
                # Bu turda gelmeyen hisselerin eski fiyatı korunur; sayfalar parça parça dolsun
                _durum["seri"] = seri
                _durum["veri"] = _hesapla(seri)
            if seri:
                _durum["zaman"] = time.time()
                if tam:
                    _durum["tam"] = _durum["zaman"]
                _dosyaya_yaz()
    except Exception:
        pass
    finally:
        _durum["calisiyor"] = False


def fiyatlar(kodlar, bekle=False):
    """
    {'THYAO': {fiyat, tarih, g1, h1, a1, y1, seri}}. Veri eskiyse tazelenir; bekle=False iken
    sayfa beklemez, elde olan (boş olabilir) veriyi alır.
    """
    _dosyadan_oku()
    if gerekli_mi():
        if bekle:
            tazele(kodlar)
        elif not _durum["calisiyor"]:
            threading.Thread(target=tazele, args=(list(kodlar),), daemon=True).start()
    return dict(_durum["veri"])
