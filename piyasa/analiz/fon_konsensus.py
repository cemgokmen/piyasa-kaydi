"""
Dev fonların çeyreklik 13F bildirimlerinden fon konsensüsü: hangi hisseyi kaç fon aldı, kaç fon sattı.
"""

import statistics
from contextlib import closing

from piyasa.bicim import donem_metni, kisa_tutar
from piyasa.onbellek import sureli
from piyasa.veritabani import get_connection


def baglanti():
    return closing(get_connection())


DEGISIM_ESIGI = 0.05      # adet en az %5 değişmediyse "değişmedi" sayılır
SIRKET_OLAYI_PAYI = 0.8   # önceki sahiplerin bu kadarı çıktıysa satın alma / iflas / borsadan çıkma


def _ilk_kelime(ad):
    kelimeler = (ad or "").upper().split()
    return kelimeler[0] if kelimeler else ""


def _ceyrek_getirileri(hisseler):
    """Son iki çeyrek sonu arasındaki gerçek (bölünmeye göre düzeltilmiş) fiyat değişimi."""
    with baglanti() as conn:
        donemler = [s[0] for s in conn.execute("SELECT DISTINCT donem FROM holdings ORDER BY donem DESC LIMIT 2")]
        if len(donemler) < 2:
            return {}
        getiriler = {}
        for s in conn.execute(
            """SELECT ticker,
                      (SELECT kapanis FROM fiyat_gecmisi f WHERE f.ticker = t.ticker AND f.tarih <= ?
                       ORDER BY tarih DESC LIMIT 1) AS son,
                      (SELECT kapanis FROM fiyat_gecmisi f WHERE f.ticker = t.ticker AND f.tarih <= ?
                       ORDER BY tarih DESC LIMIT 1) AS onceki
               FROM (SELECT DISTINCT ticker FROM fiyat_gecmisi) t""",
            (donemler[0], donemler[1]),
        ):
            if s["ticker"] in hisseler and s["son"] and s["onceki"]:
                getiriler[s["ticker"]] = s["son"] / s["onceki"]
    return getiriler


@sureli(6 * 3600)
def fon_konsensusu(adet=12):
    """
    Her fonun kendi son çeyreği bir önceki çeyreğiyle karşılaştırılır (fonlar
    bildirimlerini farklı zamanlarda yaptığı için tek bir ortak çeyrek alınmaz).
    Hisse başına kaç fonun yeni girdiği, artırdığı (adet %5+), azalttığı ve
    tamamen çıktığı sayılır.

    Şirket olayları alım-satım sayılmaz:
      - Geçen çeyrek hiçbir fonun tutmadığı hisse halka arz ya da bölünmedir;
        "yeni listelenen" olarak ayrı verilir.
      - Önceki sahiplerinin çoğu birden çıktıysa ya da kodu iflas eki 'Q' ile
        bitiyorsa şirket satın alınmış, iflas etmiş ya da borsadan çıkmıştır.
      - Hisse bölündüyse ya da birleştirildiyse (fonların bildirdiği birim değer,
        bölünmeye göre düzeltilmiş gerçek fiyat değişiminden çok farklıysa) adet
        oranları bölünme oranıyla düzeltilir; adet değişimi alım-satım sanılmaz.
    """
    with baglanti() as conn:
        satirlar = conn.execute(
            """WITH d AS (
                   SELECT fon_slug, donem,
                          DENSE_RANK() OVER (PARTITION BY fon_slug ORDER BY donem DESC) AS sira
                   FROM (SELECT DISTINCT fon_slug, donem FROM holdings))
               SELECT h.fon_slug, d.sira, h.ticker, MAX(h.sirket_adi) AS sirket,
                      SUM(h.adet) AS adet, SUM(h.deger) AS deger
               FROM holdings h JOIN d ON d.fon_slug = h.fon_slug AND d.donem = h.donem
               WHERE d.sira <= 2 AND h.ticker IS NOT NULL AND h.ticker != ''
               GROUP BY h.fon_slug, d.sira, h.ticker"""
        ).fetchall()
        son_donem = conn.execute("SELECT MAX(donem) FROM holdings").fetchone()[0]

    karsilastirilan = {s["fon_slug"] for s in satirlar if s["sira"] == 2}
    simdi, once = {}, {}
    for s in satirlar:
        if s["fon_slug"] in karsilastirilan:
            (simdi if s["sira"] == 1 else once)[(s["fon_slug"], s["ticker"])] = s

    # Hisse başına: her iki çeyrekte de tutan fonların adet oranları ve
    # bildirilen birim değerin değişimi (bölünme varsa gerçek fiyat değişiminden sapar)
    oranlar, birim_oranlari = {}, {}
    for (fon, ticker), s in simdi.items():
        o = once.get((fon, ticker))
        if o and o["adet"] and s["adet"] and o["deger"] and s["deger"]:
            oranlar.setdefault(ticker, []).append(s["adet"] / o["adet"])
            birim_oranlari.setdefault(ticker, []).append((s["deger"] / s["adet"]) / (o["deger"] / o["adet"]))
    getiriler = _ceyrek_getirileri(set(oranlar))

    hisseler = {}
    for (fon, ticker), s in simdi.items():
        k = hisseler.setdefault(ticker, {"ticker": ticker, "sirket": s["sirket"], "yeni": 0, "artiran": 0,
                                         "azaltan": 0, "cikan": 0, "tutan": 0, "onceki": 0, "deger": 0})
        k["tutan"] += 1
        k["deger"] += s["deger"] or 0
        o = once.get((fon, ticker))
        if o is None or not o["adet"]:
            k["yeni"] += 1
    for (fon, ticker), o in once.items():
        k = hisseler.setdefault(ticker, {"ticker": ticker, "sirket": o["sirket"], "yeni": 0, "artiran": 0,
                                         "azaltan": 0, "cikan": 0, "tutan": 0, "onceki": 0, "deger": 0})
        k["onceki"] += 1
        if (fon, ticker) not in simdi:
            k["cikan"] += 1
    for ticker, liste in oranlar.items():
        bolunme = 1.0
        if ticker in getiriler:
            bolunme = statistics.median(birim_oranlari[ticker]) / getiriler[ticker]
            if abs(bolunme - 1) < 0.15:          # fark küçükse bölünme yok, fiyat oynaması
                bolunme = 1.0
        for oran in liste:
            duzeltilmis = oran * bolunme - 1
            if duzeltilmis >= DEGISIM_ESIGI:
                hisseler[ticker]["artiran"] += 1
            elif duzeltilmis <= -DEGISIM_ESIGI:
                hisseler[ticker]["azaltan"] += 1

    def sirket_olayi(k):
        return (k["onceki"] == 0                                   # halka arz / bölünme
                or k["tutan"] == 0                                 # artık kimse tutmuyor
                or k["ticker"].endswith("Q") and len(k["ticker"]) == 5
                or k["onceki"] >= 5 and k["cikan"] / k["onceki"] >= SIRKET_OLAYI_PAYI)

    for k in hisseler.values():
        k["alan"] = k["yeni"] + k["artiran"]
        k["satan"] = k["azaltan"] + k["cikan"]
        k["deger_kisa"] = kisa_tutar(k["deger"])
    yeni_listelenen = sorted([k for k in hisseler.values() if k["onceki"] == 0 and k["tutan"] >= 3],
                             key=lambda k: (k["tutan"], k["deger"]), reverse=True)
    # Bu çeyrek yan şirket ayıran ana şirket (Honeywell -> Honeywell Aerospace): pozisyonlar
    # ayrılan şirkete geçtiği için düşmüş görünür, satış sayılmaz
    ayrilan_kokler = {_ilk_kelime(k["sirket"]) for k in yeni_listelenen}
    liste = [k for k in hisseler.values()
             if not sirket_olayi(k) and _ilk_kelime(k["sirket"]) not in ayrilan_kokler]

    def sirala(secilen, anahtar):
        return sorted(secilen, key=anahtar, reverse=True)[:adet]

    return {
        "donem_adi": donem_metni(son_donem) if son_donem else "",
        "fon_sayisi": len(karsilastirilan),
        "yeni_listelenen": yeni_listelenen[:8],
        "yeni_girilen": sirala([k for k in liste if k["yeni"] > 0], lambda k: (k["yeni"], k["deger"])),
        "en_cok_alinan": sirala([k for k in liste if k["alan"] > k["satan"]],
                                lambda k: (k["alan"] - k["satan"], k["deger"])),
        "en_cok_satilan": sirala([k for k in liste if k["satan"] > k["alan"]],
                                 lambda k: (k["satan"] - k["alan"], k["deger"])),
    }
