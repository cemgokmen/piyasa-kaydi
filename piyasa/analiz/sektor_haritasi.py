"""
Sektör ısı haritası: siyasetçiler ve şirket yöneticileri hangi sektörlerde net
alıcı, hangilerinde net satıcı?

Tutarlar: Kongre bildirimleri aralık verir, aralığın ortası alınır; yönetici
bildirimlerinde tutar kesindir. Sektörler SEC sanayi kodlarından (SIC) gelir
(bkz. piyasa/analiz/sektorler.py). Sektörü bilinmeyen hisseler sayılmaz.

Net oran = (alım − satım) / (alım + satım), −1 ile +1 arasında. Etiket ve renk
her zaman bu gerçek yönü gösterir (satış fazlaysa "net satıcı", kırmızı).

Yöneticiler hisse ödülü ve opsiyon gelirlerini nakde çevirdikleri için hemen
her sektörde net satıcıdır. Bu yüzden sektörler arasındaki farkı göstermek
için ayrıca alım payı (alımın toplam içindeki payı) ve bunun bütün sektörlerin
ortalamasıyla karşılaştırması verilir.

Beş renk: koyu kırmızı (güçlü satıcı), açık kırmızı (satıcı), mavi (dengeli),
açık yeşil (alıcı), koyu yeşil (güçlü alıcı). |net oran| < 0,1 dengeli;
0,1–0,6 alıcı/satıcı; 0,6 üstü güçlü.
"""

from contextlib import closing
from datetime import date, timedelta

from piyasa.bicim import kisa_tutar
from piyasa.kurallar import GECERLI_KOD, TEMIZ
from piyasa.onbellek import sureli
from piyasa.veritabani import get_connection

DONEMLER = {30: "Son 30 gün", 90: "Son 3 ay", 365: "Son 1 yıl"}
GRUPLAR = {"siyaset": "Siyasetçiler", "yonetici": "Şirket yöneticileri"}
ONE_CIKAN = 3          # her sektörde gösterilen hisse sayısı


def renk_tonu(net_oran):
    """(yön, kademe): yön 'alim'/'satim'/'notr'; kademe 0 dengeli, 1 normal, 2 güçlü."""
    buyukluk = abs(net_oran)
    if buyukluk < 0.1:
        return "notr", 0
    kademe = 1 if buyukluk < 0.6 else 2
    return ("alim" if net_oran > 0 else "satim"), kademe


@sureli(15 * 60)
def sektor_haritasi(gun=90, grup="siyaset"):
    baslangic = (date.today() - timedelta(days=gun)).isoformat()
    kosul = "t.chamber IS NOT NULL" if grup == "siyaset" else "t.chamber IS NULL"
    tutar = ("(COALESCE(t.amount_min, 0) + COALESCE(t.amount_max, 0)) / 2.0"
             if grup == "siyaset" else "COALESCE(t.amount_max, 0)")
    with closing(get_connection()) as conn:
        satirlar = conn.execute(
            f"""SELECT s.sektor, t.ticker, t.action, COUNT(*) AS adet, SUM({tutar}) AS tutar,
                       COUNT(DISTINCT t.person_slug) AS kisi
                FROM transactions t JOIN sirket s ON s.ticker = t.ticker
                WHERE {kosul} AND t.transaction_date >= ? AND s.sektor IS NOT NULL AND s.sektor != 'Diğer'
                  AND {TEMIZ.replace('suspect', 't.suspect')} AND {GECERLI_KOD.replace('ticker', 't.ticker')}
                GROUP BY s.sektor, t.ticker, t.action""",
            (baslangic,),
        ).fetchall()

    sektorler = {}
    for r in satirlar:
        s = sektorler.setdefault(r["sektor"], {"ad": r["sektor"], "alim_adet": 0, "satim_adet": 0,
                                               "alim": 0.0, "satim": 0.0, "hisseler": {}})
        alim = r["action"] == "buy"
        s["alim_adet" if alim else "satim_adet"] += r["adet"]
        s["alim" if alim else "satim"] += r["tutar"] or 0
        h = s["hisseler"].setdefault(r["ticker"], {"ticker": r["ticker"], "alim": 0.0, "satim": 0.0})
        h["alim" if alim else "satim"] += r["tutar"] or 0

    liste = []
    for s in sektorler.values():
        toplam = s["alim"] + s["satim"]
        if not toplam:
            continue
        s["net_oran"] = (s["alim"] - s["satim"]) / toplam
        s["toplam"] = toplam
        s["alim_kisa"], s["satim_kisa"] = kisa_tutar(s["alim"]), kisa_tutar(s["satim"])
        liste.append(s)
    liste.sort(key=lambda s: s["toplam"], reverse=True)

    alim = sum(s["alim"] for s in liste)
    satim = sum(s["satim"] for s in liste)
    ortalama_pay = alim / (alim + satim) if alim + satim else 0
    for s in liste:
        s["yon"], s["ton"] = renk_tonu(s["net_oran"])
        s["alim_payi"] = s["alim"] / s["toplam"]
        fark = s["alim_payi"] - ortalama_pay
        s["goreli"] = "ust" if fark > 0.03 else "alt" if fark < -0.03 else "ayni"
        # Kutudaki hisseler kutunun yönüne göre: alıcı sektörde en çok alınanlar
        anahtar = "alim" if s["yon"] == "alim" or (s["yon"] == "notr" and s["net_oran"] >= 0) else "satim"
        s["one_cikan_baslik"] = "En çok alınan" if anahtar == "alim" else "En çok satılan"
        s["one_cikan"] = sorted((h for h in s.pop("hisseler").values() if h[anahtar] > 0),
                                key=lambda h: h[anahtar], reverse=True)[:ONE_CIKAN]
    return {
        "goreli": grup == "yonetici",
        "ortalama_pay": ortalama_pay,
        "sektorler": liste,
        "alim_kisa": kisa_tutar(alim),
        "satim_kisa": kisa_tutar(satim),
        # Yöneticilerde hemen hepsi net satıcı: en alıcı / en satıcı alım payına göre sıralanır
        "en_alici": sorted(liste, key=lambda s: -s["alim_payi"])[:3],
        "en_satici": sorted(liste, key=lambda s: s["alim_payi"])[:3],
    }
