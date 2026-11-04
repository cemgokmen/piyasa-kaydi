"""
Kanıt dosyası: kuralların dönem dönem sınama sonucu ve tezin deneyi. Haftada bir yenilenir, site dosyadan okur.
Elle: python -m piyasa ajan-sina

'kurallar', 'formasyonlar' ve 'cizgiler' olağan dönemin sonucudur; karar buna göre verilir (donemler.py).
Öteki dönemler 'donemler' altındadır.
"""

import json
import os
import time
import warnings

import pandas as pd

from piyasa.analiz.ajan import KURALLAR, sinama
from piyasa.analiz.ajan import deney as deney_modulu
from piyasa.analiz.ajan.donemler import DONEMLER, ESKI, OLAGAN
from piyasa.analiz.teknik.veri import bolunme_duzelt
from piyasa.ayarlar import VERITABANI
from piyasa.bist import piyasa as bist_piyasa

DOSYA = VERITABANI.parent / "ajan_kanit.json"
TAZELIK = 7 * 24 * 3600
ENDEKS = "XU100.IS"
BASLANGIC = "2011-01-01"     # 2012'den önce göstergelerin oturması için bir yıl

_bellek = {"veri": {}, "dosya": 0.0}


def _indir(kodlar):
    import yfinance as yf
    yahoo = [bist_piyasa.yahoo_kodu(k) for k in kodlar] + [ENDEKS]
    tablo = yf.download(yahoo, start=BASLANGIC, interval="1d", auto_adjust=True, group_by="ticker",
                        threads=True, progress=False, timeout=60)
    fiyatlar = {}
    for kod in kodlar:
        try:
            d = tablo[bist_piyasa.yahoo_kodu(kod)][["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
        except KeyError:
            continue
        if d.index.tz is not None:
            d.index = d.index.tz_localize(None)
        if len(d) >= 300:
            fiyatlar[kod] = bolunme_duzelt(d)
    e = tablo[ENDEKS]["Close"].dropna()
    if e.index.tz is not None:
        e.index = e.index.tz_localize(None)
    return fiyatlar, e


def _tekrar_isle(olagan, eski):
    """Olağan dönemdeki sonuç, kuralların yazılmasında bakılmayan önceki yıllarda da görülüyor mu?"""
    for kimlik, v in olagan.items():
        for taraf in ("al", "sat"):
            s, e = v[taraf], (eski.get(kimlik) or {}).get(taraf) or {}
            if s.get("ortalama") is None or e.get("n", 0) < 20:
                s["tekrar"] = None
            elif s["ortalama"] * e["ortalama"] <= 0:
                s["tekrar"] = "tekrarlamadi"
            else:
                s["tekrar"] = "tekrarladi" if e["p"] < 0.05 else "ayni_yon"


def hesapla(fiyatlar, endeks):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Bugün henüz kapanmamış olabilir: sınama tamamlanmış günlerle yapılır
        bugun = pd.Timestamp.today().normalize()
        fiyatlar = {k: d[d.index < bugun] for k, d in fiyatlar.items()}
        endeks = endeks[endeks.index < bugun]
        sinyaller = sinama.olaylar(fiyatlar)
        form = sinama.formasyon_kayitlari(fiyatlar)
        ciz = sinama.cizgi_kayitlari(fiyatlar)
        donemler = {d.kod: {"ad": d.ad, "bas": d.bas, "bit": d.bit, "neden": d.neden,
                            "kurallar": sinama.sina(fiyatlar, donem=d, sinyaller=sinyaller),
                            "formasyonlar": sinama.formasyon_ozeti(form, d), "cizgiler": sinama.cizgi_ozeti(ciz, d)}
                    for d in DONEMLER}
        olagan = donemler[OLAGAN.kod]
        _tekrar_isle(olagan["kurallar"], donemler[ESKI.kod]["kurallar"])
        return {"zaman": time.time(), "hisse": len(fiyatlar),
                "bas": endeks.index[0].strftime("%Y-%m-%d"), "bit": endeks.index[-1].strftime("%Y-%m-%d"),
                "kurallar": olagan["kurallar"], "formasyonlar": olagan["formasyonlar"], "cizgiler": olagan["cizgiler"],
                "donemler": donemler, "deney": deney_modulu.tekrarla(fiyatlar, endeks)}


def _yaz(veri):
    gecici = DOSYA.with_suffix(".tmp")
    gecici.write_text(json.dumps(veri, separators=(",", ":"), default=str))
    os.replace(gecici, DOSYA)


def oku():
    try:
        degisme = os.path.getmtime(DOSYA)
    except OSError:
        return _bellek["veri"]
    if degisme > _bellek["dosya"]:
        try:
            _bellek["veri"] = json.loads(DOSYA.read_text())
            _bellek["dosya"] = degisme
        except (OSError, ValueError):
            pass
    return _bellek["veri"]


def gerekli():
    v = oku()
    if not v or time.time() - v.get("zaman", 0) > TAZELIK:
        return True
    # Yeni kural ya da yeni bir sınama türü eklendiyse hemen sına
    return bool(set(KURALLAR) - set(v.get("kurallar") or {})) or "donemler" not in v


def tazele(kodlar):
    fiyatlar, endeks = _indir(kodlar)
    veri = hesapla(fiyatlar, endeks)
    _yaz(veri)
    return veri


def main():
    from piyasa.analiz import tarama
    print("Kurallar sınanıyor…", flush=True)
    v = tazele([k for k, _, _ in tarama.evren()])
    print(f"{v['hisse']} hisse, {v['bas']} – {v['bit']}")
    for d in v["donemler"].values():
        print(f"\n{d['ad']} ({d['bas']} – {d['bit'] or 'bugün'})")
        for kimlik, s in d["kurallar"].items():
            print(f"  {kimlik:28} AL {s['al'].get('kanit'):10} SAT {s['sat'].get('kanit')}")
        for f in d["formasyonlar"].values():
            print(f"  {f['ad']:24} {f['n']:5} kırılış, 60 günde hedefe ulaşan %{f['hedef'] * 100:.0f}")
