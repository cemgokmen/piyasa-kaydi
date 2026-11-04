"""
Kanıt dosyası: kuralların sınama sonucu ve tezin deneyi. Hesap ~20 saniye + indirme; haftada bir yenilenir,
site dosyadan okur. Elle: python -m piyasa ajan-sina
"""

import json
import os
import time
import warnings

import pandas as pd

from piyasa.analiz.ajan import KURALLAR, sinama
from piyasa.analiz.ajan import deney as deney_modulu
from piyasa.ayarlar import VERITABANI
from piyasa.bist import piyasa as bist_piyasa

DOSYA = VERITABANI.parent / "ajan_kanit.json"
TAZELIK = 7 * 24 * 3600
ENDEKS = "XU100.IS"
GECMIS = "6y"

_bellek = {"veri": {}, "dosya": 0.0}


def _indir(kodlar):
    import yfinance as yf
    yahoo = [bist_piyasa.yahoo_kodu(k) for k in kodlar] + [ENDEKS]
    tablo = yf.download(yahoo, period=GECMIS, interval="1d", auto_adjust=True, group_by="ticker",
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
            fiyatlar[kod] = d
    e = tablo[ENDEKS]["Close"].dropna()
    if e.index.tz is not None:
        e.index = e.index.tz_localize(None)
    return fiyatlar, e


def hesapla(fiyatlar, endeks):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # Bugün henüz kapanmamış olabilir: sınama tamamlanmış günlerle yapılır
        bugun = pd.Timestamp.today().normalize()
        fiyatlar = {k: d[d.index < bugun] for k, d in fiyatlar.items()}
        endeks = endeks[endeks.index < bugun]
        return {"zaman": time.time(), "hisse": len(fiyatlar),
                "bas": endeks.index[0].strftime("%Y-%m-%d"), "bit": endeks.index[-1].strftime("%Y-%m-%d"),
                "kurallar": sinama.sina(fiyatlar), "deney": deney_modulu.tekrarla(fiyatlar, endeks),
                "formasyonlar": sinama.formasyon_sinama(fiyatlar), "cizgiler": sinama.cizgi_sinama(fiyatlar)}


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
    return bool(set(KURALLAR) - set(v.get("kurallar") or {})) or "formasyonlar" not in v


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
    for kimlik, s in v["kurallar"].items():
        print(f"  {kimlik:28} AL {s['al'].get('kanit'):10} SAT {s['sat'].get('kanit')}")
    for f in v["formasyonlar"].values():
        print(f"  {f['ad']:24} {f['n']:5} kırılış, 60 günde hedefe ulaşan %{f['hedef'] * 100:.0f}")
