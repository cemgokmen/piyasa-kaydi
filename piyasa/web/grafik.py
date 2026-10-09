"""
Liste ve kartlardaki küçük fiyat çizgileri (SVG polyline noktaları).
Borsa İstanbul, emtia ve kripto sayfaları ortak kullanır.
"""


def kucuk_grafik(degerler, genislik=120, yukseklik=34, nokta=None, basamak=0):
    """
    {'noktalar': '0,12 4,10 …', 'artis': bool}; en az iki değer yoksa None.
    nokta: yüzlerce satırlık tablolarda sayfa şişmesin diye seri bu kadar noktaya seyreltilir.
    """
    degerler = [v for v in degerler or [] if v is not None]
    if len(degerler) < 2:
        return None
    if nokta and len(degerler) > nokta:
        adim_ = len(degerler) / nokta
        degerler = [degerler[int(i * adim_)] for i in range(nokta - 1)] + [degerler[-1]]
    az, cok = min(degerler), max(degerler)
    aralik = (cok - az) or 1
    adim = genislik / (len(degerler) - 1)
    noktalar = " ".join(f"{i * adim:.{basamak}f},{(1 - (v - az) / aralik) * (yukseklik - 4) + 2:.{basamak}f}"
                        for i, v in enumerate(degerler))
    return {"noktalar": noktalar, "artis": degerler[-1] >= degerler[0]}
