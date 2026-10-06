"""
Bir siyasetçinin tahmini portföyü: alıp henüz satmadığı hisseler.

Yöntem:
- Her hissede işlemler tarih sırasıyla izlenir. Bir satış bildirildiğinde
  pozisyon kapanmış sayılır (bildirimlerde satışın kısmi olup olmadığı her
  zaman ayırt edilemiyor); son satıştan sonraki alımlar açık pozisyondur.
- Maliyet, bildirilen tutar aralıklarının ortasıdır.
- Güncel değer, her alımın maliyeti × alım gününden bugüne fiyat değişimidir.
  Fiyatı bulunamayan hissede maliyet kullanılır.

Yalnızca veritabanındaki dönemde (2025 başından beri) bildirilen işlemler
görülür; daha önce alınıp elde tutulan hisseler portföyde görünmez.
"""

from collections import defaultdict
from contextlib import closing
from datetime import date

from piyasa.analiz.getiri import FiyatDeposu
from piyasa.kurallar import GECERLI_KOD
from piyasa.veritabani import get_connection


def hesapla(slug):
    """Açık pozisyonlar (güncel değere göre büyükten küçüğe) ve özet; işlem yoksa None."""
    with closing(get_connection()) as conn:
        islemler = conn.execute(
            f"""SELECT ticker, MAX(asset_name) AS sirket, action, transaction_date AS tarih,
                      SUM(amount_min) AS alt, SUM(amount_max) AS ust
               FROM transactions
               WHERE person_slug = ? AND chamber IS NOT NULL AND {GECERLI_KOD}
               GROUP BY ticker, action, transaction_date
               ORDER BY transaction_date, action = 'sell'""",
            (slug,),
        ).fetchall()
        if not islemler:
            return None

        acik = defaultdict(list)          # hisse → son satıştan sonraki alımlar
        adlar = {}
        for s in islemler:
            adlar[s["ticker"]] = s["sirket"] or adlar.get(s["ticker"])
            if s["action"] == "sell":
                acik.pop(s["ticker"], None)
            else:
                acik[s["ticker"]].append(dict(s))

        depo = FiyatDeposu(conn, hisseler=list(acik))

    pozisyonlar = []
    for ticker, alimlar in acik.items():
        alt = sum(a["alt"] or 0 for a in alimlar)
        ust = sum(a["ust"] or 0 for a in alimlar)
        maliyet = deger = 0.0
        fiyatli = False
        for a in alimlar:
            orta = ((a["alt"] or 0) + (a["ust"] or 0)) / 2
            maliyet += orta
            giris = depo.kapanis(ticker, date.fromisoformat(a["tarih"][:10]))
            _, son = depo.son(ticker)
            if giris and son:
                deger += orta * son / giris
                fiyatli = True
            else:
                deger += orta
        pozisyonlar.append({
            "ticker": ticker,
            "sirket": adlar.get(ticker) or "",
            "alim": len(alimlar),
            "ilk": alimlar[0]["tarih"][:10],
            "son": alimlar[-1]["tarih"][:10],
            "alt": alt, "ust": ust,
            "maliyet": maliyet,
            "deger": deger,
            "getiri": (deger / maliyet - 1) if fiyatli and maliyet else None,
        })

    pozisyonlar.sort(key=lambda p: p["deger"], reverse=True)
    toplam_maliyet = sum(p["maliyet"] for p in pozisyonlar)
    toplam_deger = sum(p["deger"] for p in pozisyonlar)
    for p in pozisyonlar:
        p["pay"] = p["deger"] / toplam_deger if toplam_deger else 0

    return {
        "pozisyonlar": pozisyonlar,
        "sayi": len(pozisyonlar),
        "maliyet": toplam_maliyet,
        "deger": toplam_deger,
        "getiri": (toplam_deger / toplam_maliyet - 1) if toplam_maliyet else None,
        "kapanan": len({s["ticker"] for s in islemler}) - len(pozisyonlar),
    }
