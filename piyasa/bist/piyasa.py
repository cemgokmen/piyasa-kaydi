"""
Borsa İstanbul fiyatları (Yahoo Finance, ücretsiz; borsa saatinde yaklaşık 15 dakika gecikmeli).

  fiyatlar(kodlar)  BIST 100 şirketlerinin son fiyatı, günlük / haftalık / yıllık değişimi ve
                    küçük grafik için son 3 ayın kapanışları
  yahoo_kodu(kod)   'THYAO' -> 'THYAO.IS'

100 hissenin toplu indirilmesi yarım dakikayı bulabildiği için sayfa beklemez: fiyatlar
arka planda tazelenir, sayfa elde olan en son veriyi gösterir.
"""

import threading
import time

import pandas as pd
import yfinance as yf

ENDEKS = "XU100.IS"
TAZELIK = 15 * 60          # saniye

_durum = {"zaman": 0.0, "veri": {}, "calisiyor": False}
_kilit = threading.Lock()


def yahoo_kodu(kod):
    return f"{kod.upper()}.IS"


def _degisim(seri, gun):
    """Son kapanışın 'gun' işlem günü önceki kapanışa göre değişimi."""
    if len(seri) <= gun:
        return None
    onceki = seri.iloc[-1 - gun]
    return float(seri.iloc[-1] / onceki - 1) if onceki else None


def _indir(kodlar):
    """{'THYAO.IS': {...}} — Yahoo'dan bir yıllık günlük kapanışlar, tek toplu istekte."""
    tablo = yf.download(list(kodlar), period="1y", interval="1d", auto_adjust=True, group_by="ticker",
                        threads=True, progress=False, timeout=20)
    sonuc = {}
    for kod in kodlar:
        try:
            seri = tablo[kod]["Close"].dropna() if isinstance(tablo.columns, pd.MultiIndex) else tablo["Close"].dropna()
        except KeyError:
            continue
        if len(seri) < 2:
            continue
        sonuc[kod] = {
            "fiyat": float(seri.iloc[-1]),
            "tarih": seri.index[-1].strftime("%Y-%m-%d"),
            "g1": _degisim(seri, 1), "h1": _degisim(seri, 5), "a1": _degisim(seri, 21),
            "y1": float(seri.iloc[-1] / seri.iloc[0] - 1) if seri.iloc[0] else None,
            "seri": [float(v) for v in seri.iloc[-63:]],
        }
    return sonuc


def tazele(kodlar):
    """Fiyatları indirip saklar; aynı anda yalnızca bir indirme çalışır."""
    with _kilit:
        if _durum["calisiyor"]:
            return
        _durum["calisiyor"] = True
    try:
        yahoo = sorted({yahoo_kodu(k) for k in kodlar} | {ENDEKS})
        veri = _indir(yahoo)
        if veri:
            # Bu turda gelmeyen hisselerin eski fiyatı korunur
            _durum["veri"] = {**_durum["veri"], **{k.removesuffix(".IS"): v for k, v in veri.items()}}
            _durum["zaman"] = time.monotonic()
    except Exception:
        pass
    finally:
        _durum["calisiyor"] = False


def fiyatlar(kodlar, bekle=False):
    """
    {'THYAO': {fiyat, tarih, g1, h1, a1, y1, seri}}. Veri eskiyse arka planda tazelenir;
    bekle=False iken sayfa beklemez, elde olan (boş olabilir) veriyi alır.
    """
    if time.monotonic() - _durum["zaman"] > TAZELIK:
        if bekle:
            tazele(kodlar)
        else:
            threading.Thread(target=tazele, args=(list(kodlar),), daemon=True).start()
    return dict(_durum["veri"])
