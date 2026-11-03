"""
Analiz taraması: BIST 100 hisselerinin teknik ve temel puanları, piyasa genişliği ve rejimi.

    python -m piyasa analiz-tarama           teknik taramayı ve temel verinin bir kısmını şimdi tazeler
    python -m piyasa analiz-tarama --temel   bütün hisselerin temel verisini indirir (birkaç dakika)

Sonuç veritabanının klasöründeki analiz_tarama.json dosyasında durur; site oradan okur, ziyaretçi beklemez.
  teknik   her işlem günü kapanıştan sonra ve borsa açıkken saatte bir (iki yıllık günlük veri,
           tek toplu istekte)
  temel    her hisse haftada bir; her turda en çok TEMEL_PARCA hisse (Yahoo'yu yormamak için)
  medyan   temel verisi gelen şirketlerin F/K, PD/DD, FD/FAVÖK medyanları: hisse sayfasındaki
           değerleme bu medyanlara göre okunur (piyasa geneli ve aynı sektör)

Siteyi çalıştıran iki süreçten yalnızca kilidi alan indirir.
"""

import fcntl
import json
import os
import statistics
import sys
import threading
import time
import warnings
from contextlib import closing
from datetime import datetime

import numpy as np
import pandas as pd

from piyasa.analiz import teknik
from piyasa.ayarlar import VERITABANI
from piyasa.bist import piyasa as bist_piyasa

# Sık yazılan dosya: iCloud'a eşitlenen Masaüstü'nde değil, veritabanının yanında durur
DOSYA = VERITABANI.parent / "analiz_tarama.json"
KILIT = VERITABANI.parent / "analiz_tarama.kilit"
ENDEKS = "XU100.IS"
DOLAR = "TRY=X"
ACIK_TAZELIK = 60 * 60            # borsa açıkken teknik tarama en çok bu kadar eski olabilir
TEMEL_TAZELIK = 7 * 24 * 3600
TEMEL_PARCA = 12
DONGU = 10 * 60

_durum = {"veri": {}, "dosya": 0.0, "calisiyor": False}
_kilit = threading.Lock()


# ---------------------------------------------------------------------------
# Evren
# ---------------------------------------------------------------------------

def evren():
    """[(kod, ünvan, sektör)] — BIST 100 hisseleri."""
    from piyasa.veritabani import get_connection
    with closing(get_connection()) as conn:
        try:
            satirlar = conn.execute("SELECT kod, unvan, ana_sektor FROM bist_sirket WHERE xu100 = 1 ORDER BY kod").fetchall()
        except Exception:
            satirlar = conn.execute("SELECT kod, unvan, NULL FROM bist_sirket WHERE xu100 = 1 ORDER BY kod").fetchall()
    return [(r[0], r[1], r[2]) for r in satirlar]


# ---------------------------------------------------------------------------
# Teknik tarama
# ---------------------------------------------------------------------------

def _ohlcv(tablo, kod):
    try:
        df = tablo[kod] if isinstance(tablo.columns, pd.MultiIndex) else tablo
    except KeyError:
        return None
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df if len(df) >= 120 else None


def _gun_getirisi(c, n):
    return float(c.iloc[-1] / c.iloc[-n - 1] - 1) if len(c) > n and c.iloc[-n - 1] else None


def hisse_ozeti(df, endeks):
    """Tek hissenin tarama satırı: üç vade puanı, bileşenler ve birkaç gösterge."""
    g, b = teknik.puan_serileri(df, endeks)
    son, c = g.iloc[-1], g["close"]

    def f(x, n=4):
        return None if x is None or pd.isna(x) else round(float(x), n)

    return {
        "fiyat": f(son["close"]),
        "tarih": df.index[-1].strftime("%Y-%m-%d"),
        "puan": {v: f(b[f"puan_{v}"].iloc[-1], 1) for v in teknik.VADELER},
        "bilesen": {k: f(b[k].iloc[-1], 3) for k in teknik.BILESEN_ADLARI},
        "g1": _gun_getirisi(c, 1), "a1": _gun_getirisi(c, 21), "a3": _gun_getirisi(c, 63), "a6": _gun_getirisi(c, 126),
        "y1": _gun_getirisi(c, 252),
        "rsi": f(son["rsi"], 1),
        "ust50": bool(son["close"] > son["sma50"]) if pd.notna(son["sma50"]) else None,
        "ust200": bool(son["close"] > son["sma200"]) if pd.notna(son["sma200"]) else None,
        "atr_yuzde": f(son["atr"] / son["close"], 4) if son["close"] else None,
        "zirveden": f(son["close"] / son["zirve252"] - 1, 4) if pd.notna(son["zirve252"]) else None,
        "yeni_zirve": bool(df["High"].iloc[-1] >= df["High"].iloc[-252:].max()) if len(df) >= 252 else None,
        "yeni_dip": bool(df["Low"].iloc[-1] <= df["Low"].iloc[-252:].min()) if len(df) >= 252 else None,
        "st_yon": int(son["st_yon"]) if pd.notna(son["st_yon"]) else None,
        "hacim_tl": f(float((df["Close"] * df["Volume"]).iloc[-20:].mean()), 0),
    }


def genislik(satirlar):
    """Piyasa genişliği: hisselerin kaçı ortalamaların üstünde, kaçı yeni zirvede."""
    def oran(alan):
        degerler = [s[alan] for s in satirlar if s.get(alan) is not None]
        return sum(degerler) / len(degerler) if degerler else None
    orta = [s["puan"]["orta"] for s in satirlar if s["puan"].get("orta") is not None]
    return {
        "n": len(satirlar),
        "ust50": oran("ust50"), "ust200": oran("ust200"),
        "yeni_zirve": sum(1 for s in satirlar if s.get("yeni_zirve")),
        "yeni_dip": sum(1 for s in satirlar if s.get("yeni_dip")),
        "olumlu": sum(1 for p in orta if p >= 60), "olumsuz": sum(1 for p in orta if p <= 40),
        "medyan_puan": float(np.median(orta)) if orta else None,
    }


def rejim(endeks_df, dolar=None, gen=None):
    """Piyasa rejimi: endeksin trendi, dolar bazında trend ve genişlik birlikte."""
    t = teknik.analiz(endeks_df)
    gs = t["gosterge"]
    ust200 = gs["sma200"] is not None and gs["close"] > gs["sma200"]
    egim = None
    g = t["_g"]
    if g["sma200"].notna().sum() > 25:
        egim = float(g["sma200"].iloc[-1] / g["sma200"].iloc[-21] - 1)
    dolar_bazli = None
    if dolar is not None and len(dolar) > 220:
        usd = (endeks_df["Close"] / dolar.reindex(endeks_df.index).ffill()).dropna()
        ort = usd.rolling(200).mean()
        dolar_bazli = {"ust200": bool(usd.iloc[-1] > ort.iloc[-1]), "y1": float(usd.iloc[-1] / usd.iloc[-min(252, len(usd) - 1)] - 1),
                       "uzaklik": float(usd.iloc[-1] / ort.iloc[-1] - 1)}
    puan = 0
    puan += 1 if ust200 else -1
    puan += 1 if egim and egim > 0 else -1 if egim and egim < 0 else 0
    if gen and gen.get("ust200") is not None:
        puan += 1 if gen["ust200"] >= 0.55 else -1 if gen["ust200"] <= 0.40 else 0
    if dolar_bazli:
        puan += 1 if dolar_bazli["ust200"] else -1
    if puan >= 3:
        kod, ad, metin = "boga", "Yükseliş rejimi", ("Endeks yükselen 200 günlük ortalamanın üstünde ve hisselerin çoğu trendde. "
                                                     "Trend takibi ve kırılım alımları bu rejimde en iyi çalışır; tam pozisyon boyutu kullanılabilir.")
    elif puan <= -2:
        kod, ad, metin = "ayi", "Düşüş rejimi", ("Endeks 200 günlük ortalamanın altında ve hisselerin çoğu düşüşte. "
                                                 "Bu rejimde yeni alımlar daha sık stop olur: pozisyonları küçült, nakit oranını artır, yalnızca en güçlü hisselere bak.")
    else:
        kod, ad, metin = "karisik", "Kararsız rejim", ("Endeks ve genişlik aynı yönü göstermiyor. Seçici ol: pozisyon boyutunu yarıya indir, "
                                                       "trendi teyitli ve endeksten güçlü hisseleri tercih et.")
    return {"kod": kod, "ad": ad, "metin": metin, "puan": puan, "ust200": ust200, "egim200": egim, "dolar": dolar_bazli,
            "endeks_puan": t["puanlar"], "evre": t["evre"], "fiyat": gs["close"], "sma200": gs["sma200"],
            "y1": gs["getiriler"]["1y"], "a1": gs["getiriler"]["1a"], "rsi": gs["rsi"]}


def teknik_tara(kodlar):
    import yfinance as yf
    yahoo = [bist_piyasa.yahoo_kodu(k) for k in kodlar] + [ENDEKS, DOLAR]
    tablo = yf.download(yahoo, period="2y", interval="1d", auto_adjust=True, group_by="ticker",
                        threads=True, progress=False, timeout=30)
    endeks = _ohlcv(tablo, ENDEKS)
    if endeks is None:
        raise RuntimeError("BIST 100 endeksi indirilemedi")
    dolar = _ohlcv(tablo, DOLAR)
    dolar_kapanis = dolar["Close"] if dolar is not None else None
    satirlar = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for kod in kodlar:
            df = _ohlcv(tablo, bist_piyasa.yahoo_kodu(kod))
            if df is None:
                continue
            try:
                satirlar[kod] = hisse_ozeti(df, endeks["Close"])
            except Exception:
                continue
        gen = genislik(list(satirlar.values()))
        rj = rejim(endeks, dolar_kapanis, gen)
    return {"hisseler": satirlar, "genislik": gen, "rejim": rj, "zaman": time.time()}


# ---------------------------------------------------------------------------
# Temel tarama
# ---------------------------------------------------------------------------

TEMEL_ALANLARI = ("fk", "pddd", "fd_favok", "fcf_verimi", "roe", "roe_reel", "gelir_cagr_reel", "nb_favok", "temettu")


def temel_satiri(kod, sektor, enflasyon, medyan=None):
    from piyasa.analiz import temel_analiz
    veri = temel_analiz.veri_al(bist_piyasa.yahoo_kodu(kod))
    s = temel_analiz.degerlendir(enflasyon=enflasyon, medyan=medyan, sektor=sektor, **veri)
    if not s:
        return {"zaman": time.time(), "puan": None}
    return {
        "zaman": time.time(), "puan": s["puan"], "bilesen": s["bilesen"], "finans": s["finans"],
        "piotroski": s["piotroski"]["puan"] if s["piotroski"] else None,
        "piotroski_toplam": s["piotroski"]["toplam"] if s["piotroski"] else None,
        "altman": s["altman"]["bolge"] if s["altman"] else None,
        "bayrak": len(s["bayraklar"]),
        **{k: s["oranlar"].get(k) for k in TEMEL_ALANLARI},
    }


def medyanlar(temel, sektorler):
    """Piyasa geneli ve sektör medyanları (finans şirketleri FD/FAVÖK ve nakit veriminde dışarıda)."""
    def medyan(satirlar, alan, alt=None, ust=None):
        degerler = [s[alan] for s in satirlar if s.get(alan) is not None
                    and (alt is None or s[alan] > alt) and (ust is None or s[alan] < ust)]
        return statistics.median(degerler) if len(degerler) >= 5 else None

    def hesap(satirlar):
        finans_disi = [s for s in satirlar if not s.get("finans")]
        sonuc = {"fk": medyan(satirlar, "fk", 0, 200), "pddd": medyan(satirlar, "pddd", 0, 50),
                 "fd_favok": medyan(finans_disi, "fd_favok", 0, 200), "fcf_verimi": medyan(finans_disi, "fcf_verimi", -1, 1),
                 "n": len(satirlar)}
        return {k: v for k, v in sonuc.items() if v is not None}

    satirlar = [s for s in temel.values() if s.get("puan") is not None]
    genel = hesap(satirlar)
    sektor = {}
    for ad in {sektorler.get(k) for k in temel if sektorler.get(k)}:
        uyeler = [temel[k] for k in temel if sektorler.get(k) == ad and temel[k].get("puan") is not None]
        if len(uyeler) >= 5:
            sektor[ad] = hesap(uyeler)
    return {"genel": genel, "sektor": sektor}


def temel_tara(veri, liste, enflasyon, en_cok=TEMEL_PARCA, hepsi=False):
    temel = {} if hepsi else dict(veri.get("temel") or {})
    sektorler = {k: s for k, _, s in liste}
    simdi = time.time()
    eski = sorted((k for k, _, _ in liste), key=lambda k: (temel.get(k) or {}).get("zaman", 0))
    eski = [k for k in eski if simdi - (temel.get(k) or {}).get("zaman", 0) > TEMEL_TAZELIK][:en_cok]
    for kod in eski:
        try:
            temel[kod] = temel_satiri(kod, sektorler.get(kod), enflasyon, (veri.get("medyan") or {}).get("genel"))
        except Exception:
            temel.setdefault(kod, {})["zaman"] = simdi - TEMEL_TAZELIK + 6 * 3600    # 6 saat sonra yeniden dene
        time.sleep(0.8)
    return temel, medyanlar(temel, sektorler)


# ---------------------------------------------------------------------------
# Saklama ve tazeleme
# ---------------------------------------------------------------------------

def _oku():
    try:
        degisme = os.path.getmtime(DOSYA)
    except OSError:
        return _durum["veri"]
    if degisme > _durum["dosya"]:
        try:
            _durum["veri"] = json.loads(DOSYA.read_text())
            _durum["dosya"] = degisme
        except (OSError, ValueError):
            pass
    return _durum["veri"]


def _yaz(veri):
    gecici = DOSYA.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, separators=(",", ":"), default=str))
    os.replace(gecici, DOSYA)
    _durum["veri"], _durum["dosya"] = veri, os.path.getmtime(DOSYA)


def teknik_gerekli(veri, simdi=None):
    simdi = simdi or datetime.now()
    zaman = (veri.get("teknik") or {}).get("zaman")
    if not zaman:
        return True
    son = datetime.fromtimestamp(zaman)
    if bist_piyasa.borsa_acik(simdi):
        return (simdi - son).total_seconds() > ACIK_TAZELIK
    return son < bist_piyasa.son_kapanis(simdi)


def tazele(zorla=False, temel_en_cok=TEMEL_PARCA, temel_hepsi=False):
    """Gerekiyorsa teknik taramayı ve temel verinin bir parçasını tazeler (süreçler arası tek indirme)."""
    with _kilit:
        if _durum["calisiyor"]:
            return False
        _durum["calisiyor"] = True
    try:
        KILIT.parent.mkdir(parents=True, exist_ok=True)
        with open(KILIT, "w") as kilit_dosyasi:
            try:
                fcntl.flock(kilit_dosyasi, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
            veri = dict(_oku())
            liste = evren()
            if not liste:
                return False
            degisti = False
            if zorla or teknik_gerekli(veri):
                veri["teknik"] = teknik_tara([k for k, _, _ in liste])
                veri["adlar"] = {k: a for k, a, _ in liste}
                veri["sektorler"] = {k: s for k, _, s in liste}
                degisti = True
                _yaz(veri)
            if temel_en_cok:
                from piyasa.analiz import temel_analiz
                from piyasa.analiz.karsilastirma import enflasyon
                once = json.dumps(veri.get("temel"), sort_keys=True, default=str)
                veri["temel"], veri["medyan"] = temel_tara(veri, liste, temel_analiz.yillik_enflasyon(enflasyon("TR")),
                                                            temel_en_cok, hepsi=temel_hepsi)
                if degisti or json.dumps(veri["temel"], sort_keys=True, default=str) != once:
                    _yaz(veri)
            return True
    finally:
        _durum["calisiyor"] = False


def veri():
    """Elde olan son tarama (boş olabilir); gerekiyorsa arka planda tazeleme başlatır."""
    v = _oku()
    if teknik_gerekli(v) and not _durum["calisiyor"]:
        threading.Thread(target=lambda: _sessiz(tazele), daemon=True).start()
    return v


def _sessiz(fonksiyon, *args, **kwargs):
    try:
        return fonksiyon(*args, **kwargs)
    except Exception:
        return None


def arkaplanda_tazele(aralik=DONGU):
    def dongu():
        time.sleep(20)
        while True:
            _sessiz(tazele)
            time.sleep(aralik)
    threading.Thread(target=dongu, name="analiz-tarama", daemon=True).start()


def medyan_al(kod=None):
    """Hisse sayfası için değerleme medyanları: aynı sektörde yeterli şirket varsa sektörün, yoksa piyasanın."""
    v = _oku()
    m = v.get("medyan") or {}
    genel = m.get("genel") or {}
    sektor = (v.get("sektorler") or {}).get(kod) if kod else None
    sm = (m.get("sektor") or {}).get(sektor) if sektor else None
    if sm:
        return {**genel, **sm}, f"{sektor.capitalize() if sektor else ''} sektörü ({sm.get('n')} şirket)"
    if genel:
        return genel, f"BIST 100 ({genel.get('n')} şirket)"
    return None, None


def main():
    hepsi = "--temel" in sys.argv
    print("Analiz taraması başlıyor…", flush=True)
    bas = time.time()
    tazele(zorla=True, temel_en_cok=200 if hepsi else TEMEL_PARCA, temel_hepsi=hepsi)
    v = _oku()
    t = v.get("teknik") or {}
    print(f"Teknik: {len(t.get('hisseler', {}))} hisse · rejim: {(t.get('rejim') or {}).get('ad')}")
    temel = v.get("temel") or {}
    print(f"Temel: {sum(1 for s in temel.values() if s.get('puan') is not None)} hisse · medyan: {(v.get('medyan') or {}).get('genel')}")
    print(f"Süre: {time.time() - bas:.0f} sn")
