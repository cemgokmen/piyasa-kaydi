"""Teknik analiz sonucunun Türkçe okuması ve senaryolar."""

from piyasa.analiz.teknik.yapi import dow_metni
from piyasa.bicim import ek, ondalik, uzun_tarih
from piyasa.bicim import fiyat as _p


def _o(x, n=1):
    return ondalik(x, n)


def _yuzde(x):
    return f"%{_o(abs(x) * 100)}".replace(".", ",")


def okuma(t, bolgeler=None):
    """
    Teknik analiz sonucunu, deneyimli bir grafik okuyucunun yazacağı gibi başlıklar altında
    Türkçe cümlelere çevirir. Her madde: {'baslik', 'yon' (+1/0/−1), 'metin'}.
    """
    gs = t["gosterge"]
    c = gs["close"]
    m = []

    def ekle(baslik, yon, metin):
        m.append({"baslik": baslik, "yon": yon, "metin": metin})

    # Ana trend
    if gs["sma200"]:
        ust200 = c > gs["sma200"]
        ust50 = gs["sma50"] and c > gs["sma50"]
        dizilim = gs["sma50"] and gs["sma20"] and gs["sma20"] > gs["sma50"] > gs["sma200"]
        ters = gs["sma50"] and gs["sma20"] and gs["sma20"] < gs["sma50"] < gs["sma200"]
        uzaklik = c / gs["sma200"] - 1
        if dizilim and ust200:
            metin = (f"Fiyat 20, 50 ve 200 günlük ortalamaların üstünde ve ortalamalar yükseliş sırasında dizili (20 > 50 > 200). "
                     f"200 günlüğe uzaklık {_yuzde(uzaklik)}.")
            ekle("Ana trend: yükseliş", 1, metin)
        elif ters and not ust200:
            ekle("Ana trend: düşüş", -1, f"Fiyat bütün ana ortalamaların altında ve ortalamalar düşüş sırasında (20 < 50 < 200). "
                 f"200 günlüğün {_yuzde(uzaklik)} altında.")
        elif ust200:
            ekle("Ana trend: yükseliş, kısa vadede dinlenme" if not ust50 else "Ana trend: yükseliş", 1 if ust50 else 0,
                 f"Fiyat 200 günlük ortalamanın {_yuzde(uzaklik)} üstünde" + ("" if ust50 else ", ama 50 günlüğün altına sarktı: ana trend bozulmadan düzeltme.") + ".")
        else:
            ekle("Ana trend: zayıf", -1 if not ust50 else 0, f"Fiyat 200 günlük ortalamanın {_yuzde(uzaklik)} altında"
                 + (", kısa vadede 50 günlüğün üstüne çıkarak toparlanma deniyor." if ust50 else "."))
    if t["evre"]:
        ekle("Haftalık grafik (Weinstein evresi)", 1 if t["evre"]["yon"] > 0 else (-1 if t["evre"]["yon"] < 0 else 0), t["evre"]["metin"])
    ekle("Tepe-dip yapısı", t["yapi"]["yon"], t["yapi"]["metin"])
    if t.get("dow"):
        ekle("Dow teorisi", t["dow"]["yon"], dow_metni(t["dow"]))

    # Trend gücü
    if gs["adx"] is not None:
        yon_di = "alıcılar (+DI)" if (gs["arti_di"] or 0) > (gs["eksi_di"] or 0) else "satıcılar (−DI)"
        if gs["adx"] >= 25:
            ekle("Trend gücü", 1 if yon_di.startswith("alıcı") else -1,
                 f"ADX {gs['adx']:.0f}: güçlü bir trend var ve yönünü {yon_di} belirliyor. Güçlü trendde osilatörlerin aşırı alım/satım "
                 "uyarıları sık yanıltır; trend yönünde işlem daha güvenlidir.")
        elif gs["adx"] < 18:
            ekle("Trend gücü", 0, f"ADX {gs['adx']:.0f}: belirgin bir trend yok, fiyat yatay. Bu ortamda destekten alıp dirençte satmak, "
                 "kırılım kovalamaktan daha iyi çalışır.")
        else:
            ekle("Trend gücü", 0, f"ADX {gs['adx']:.0f}: trend orta güçte, {yon_di} hafif üstün.")

    # Momentum
    r = gs["rsi"]
    if r is not None:
        if r >= 70:
            metin, yon = f"RSI {r:.0f}: aşırı alım bölgesi. Güçlü trendlerde uzun süre burada kalabilir; tek başına satış sebebi değil ama yeni alım için risk/getiri zayıflar.", 0
        elif r <= 30:
            metin, yon = f"RSI {r:.0f}: aşırı satım bölgesi. Tepki yükselişi ihtimali arttı; düşüş trendinde ise teyit (yükselen dip, hacim) beklenmeli.", 0
        elif r >= 50:
            metin, yon = f"RSI {r:.0f}: momentum alıcılar lehine (50'nin üstü).", 1
        else:
            metin, yon = f"RSI {r:.0f}: momentum satıcılar lehine (50'nin altı).", -1
        if gs["macd_hist"] is not None:
            if gs["macd"] > gs["macd_sinyal"]:
                metin += " MACD sinyal çizgisinin üstünde" + (" ve sıfırın üstünde: yükseliş momentumu teyitli." if gs["macd"] > 0 else ", ancak sıfırın altında: düşüş içinde toparlanma.")
            else:
                metin += " MACD sinyal çizgisinin altında" + (" ve sıfırın altında: düşüş momentumu sürüyor." if gs["macd"] < 0 else ", sıfırın üstünde: yükseliş ivme kaybediyor.")
        ekle("Momentum", yon, metin)

    # Diğer osilatörler ve trend filtresi: yalnızca bugünkü konum, sinyaller ajan bölümündedir
    if gs.get("vhf") is not None:
        parca = [f"VHF {ondalik(gs['vhf'], 2)}: " + ("fiyat belirgin bir yöne gidiyor." if gs["vhf"] >= 0.40
                                                     else "fiyat yatay sayılır." if gs["vhf"] < 0.25 else "trend orta güçte.")]
        if gs.get("williams") is not None:
            parca.append(f"Williams %R {gs['williams']:.0f}".replace("-", "−")
                         + (" (aşırı alım)" if gs["williams"] > -20 else " (aşırı satım)" if gs["williams"] < -80 else "") + ".")
        if gs.get("cci20") is not None:
            parca.append(f"CCI {gs['cci20']:.0f}".replace("-", "−")
                         + (" (spekülatif yükseliş)" if gs["cci20"] > 100 else " (aşırı düşüş)" if gs["cci20"] < -100 else "") + ".")
        if gs.get("momentum10") is not None:
            parca.append(f"10 günlük momentum {gs['momentum10']:.0f} (100 denge).")
        ekle("Osilatörler", 0, " ".join(parca))

    # Trend çizgileri
    for tc in t.get("trend_cizgileri") or []:
        ad = "Yükselen destek çizgisi" if tc["tur"] == "destek" else "Alçalan direnç çizgisi"
        if tc["durum"] == "gecerli":
            uzak = (tc["f3"] / c - 1)
            ekle(ad, 1 if tc["tur"] == "destek" else -1,
                 f"{_p(tc['f1'])} ve {_p(tc['f2'])} noktalarından geçiyor; bugün {_p(tc['f3'])}, fiyata uzaklığı {_yuzde(uzak)}. "
                 "Kırılma ancak %3 delme ya da 3 kapanışla sayılır."
                 + (f" Paraleli (kanalın karşı sınırı) bugün {_p(tc['kanal_f3'])}." if tc.get("kanal_f3") else ""))
        else:
            ekle(ad + " kırıldı", tc["yon"], f"{uzun_tarih(tc['kirilis_tarih'].isoformat())} günü kırıldı"
                 + ("; kırılış hacimle teyitli." if tc["hacimli"] else "; kırılışta hacim artışı yok, güven düşük."))

    # Göreli güç
    if gs.get("endeks_getiri"):
        g3, e3 = gs["getiriler"]["3a"], gs["endeks_getiri"]["3a"]
        g6, e6 = gs["getiriler"]["6a"], gs["endeks_getiri"]["6a"]
        if g3 is not None and e3 is not None:
            fark = g3 - e3
            metin = f"Son 3 ayda hisse {'+' if g3 >= 0 else '−'}{_yuzde(g3)}, endeks {'+' if e3 >= 0 else '−'}{_yuzde(e3)}"
            if g6 is not None and e6 is not None:
                metin += f"; 6 ayda hisse {'+' if g6 >= 0 else '−'}{_yuzde(g6)}, endeks {'+' if e6 >= 0 else '−'}{_yuzde(e6)}"
            metin += ". " + ("Hisse endeksten güçlü: piyasa liderleri arasında." if fark > 0.03 else
                             "Hisse endeksin gerisinde: para başka hisselere akıyor." if fark < -0.03 else "Endeksle benzer seyir.")
            ekle("Endekse göre güç", 1 if fark > 0.03 else (-1 if fark < -0.03 else 0), metin)

    # Hacim
    if gs["cmf"] is not None and gs["hacim20"]:
        oran = gs["hacim"] / gs["hacim20"] if gs["hacim20"] else None
        metin = f"Chaikin para akışı {'+' if gs['cmf'] >= 0 else '−'}{ondalik(abs(gs['cmf']), 2)}: " + ("alıcılar kapanışları günün üst bölümüne taşıyor, para girişi var." if gs["cmf"] > 0.05
                                                       else "kapanışlar günün alt bölümünde, para çıkışı var." if gs["cmf"] < -0.05 else "belirgin bir para akışı yok.")
        if oran:
            metin += f" Son günün hacmi 20 günlük ortalamanın {_o(oran)} katı."
        ekle("Hacim ve para akışı", 1 if gs["cmf"] > 0.05 else (-1 if gs["cmf"] < -0.05 else 0), metin)

    # Oynaklık
    if gs["bb_b"] is not None:
        b_ = gs["bb_b"]
        if b_ > 1:
            metin = "Fiyat üst Bollinger bandının dışında kapattı: güçlü itiş ama kısa vadede gerilmiş."
        elif b_ < 0:
            metin = "Fiyat alt Bollinger bandının dışında kapattı: sert satış. BIST 100 geçmişinde alt banda değmek tek başına alım sebebi olmadı."
        else:
            metin = f"Fiyat Bollinger bantlarının içinde (%b = {ondalik(b_, 2)})."
        metin += f" Günlük ortalama hareket (ATR) {_p(gs['atr'])}, yani fiyatın {ek('%' + _o(gs['atr'] / c * 100), 'si')}"
        if gs["oynaklik"]:
            metin += f"; yıllık oynaklık %{gs['oynaklik'] * 100:.0f}"
            if gs.get("endeks_oynaklik"):
                metin += f" (endeks %{gs['endeks_oynaklik'] * 100:.0f})"
        ekle("Oynaklık", 0, metin + ".")

    # Ichimoku
    if gs["span_a"] and gs["span_b"]:
        bulut_ust, bulut_alt = max(gs["span_a"], gs["span_b"]), min(gs["span_a"], gs["span_b"])
        if c > bulut_ust:
            metin, yon = "Fiyat Ichimoku bulutunun üstünde", 1
        elif c < bulut_alt:
            metin, yon = "Fiyat Ichimoku bulutunun altında", -1
        else:
            metin, yon = "Fiyat Ichimoku bulutunun içinde (kararsız bölge)", 0
        if gs["tenkan"] and gs["kijun"]:
            metin += "; dönüş çizgisi (tenkan) temel çizginin (kijun) " + ("üstünde." if gs["tenkan"] > gs["kijun"] else "altında.")
        ekle("Ichimoku", yon, metin)

    # Fibonacci
    fib = t["fibonacci"]
    if fib:
        d = fib["duzeltme"]
        if fib["yon"] == "yukari":
            metin = (f"Son 6 ayın yükseliş salınımı {_p(fib['alt'])} → {_p(fib['ust'])}. Fiyat bu yükselişin %{round(d * 100)} kadarını geri verdi. ")
            if d < 0.236:
                metin += "Zirveye yakın, düzeltme sığ: güçlü trend işareti."
            elif d <= 0.618:
                metin += "Klasik düzeltme bölgesi (%38,2–61,8) içinde. Buradan dönüş kuralının kanıtı kaynak kuralları bölümünde."
            else:
                metin += "%61,8'in ötesine geçen derin düzeltme: yükseliş trendinin geçerliliği sorgulanıyor."
        else:
            metin = (f"Son 6 ayın düşüş salınımı {_p(fib['ust'])} → {_p(fib['alt'])}. Fiyat düşüşün %{round(d * 100)} kadarını geri aldı. ")
            metin += ("Tepki zayıf." if d < 0.382 else "Tepki, klasik %38,2–61,8 bölgesinde." if d <= 0.618
                      else "Düşüşün çoğu geri alındı: dönüş ihtimali güçleniyor.")
        metin += " BIST 100 geçmişinde düzeltmeler bu seviyelerde yığılmıyor; seviyeyi tek başına kanıt sayma."
        ekle("Fibonacci", 0, metin)

    # Destek / direnç
    if bolgeler:
        destek = [b for b in bolgeler if b["tur"] == "destek"]
        direnc = [b for b in bolgeler if b["tur"] == "direnç"]
        parca = []
        if destek:
            d = max(destek, key=lambda b: b["merkez"])
            parca.append(f"En yakın destek {_p(d['alt'])}–{_p(d['ust'])} (%{_o(abs(d['uzaklik_yuzde']))} aşağıda, güç {d['puan']:.0f}/100, "
                         f"{d['test']} testte {d['tutunan']} kez tutundu)")
        if direnc:
            r_ = min(direnc, key=lambda b: b["merkez"])
            parca.append(f"en yakın direnç {_p(r_['alt'])}–{_p(r_['ust'])} (%{_o(abs(r_['uzaklik_yuzde']))} yukarıda, güç {r_['puan']:.0f}/100)")
        if parca:
            metin = "; ".join(parca)
            ekle("Destek ve direnç", 0, metin[0].upper() + metin[1:] + ".")

    return m


def senaryolar(t, bolgeler):
    """Boğa ve ayı senaryosu: hangi seviyede ne olur."""
    gs = t["gosterge"]
    c, a = gs["close"], gs["atr"]
    destek = sorted([b for b in bolgeler or [] if b["tur"] == "destek"], key=lambda b: -b["merkez"])
    direnc = sorted([b for b in bolgeler or [] if b["tur"] == "direnç"], key=lambda b: b["merkez"])
    yukari_esik = direnc[0]["ust"] if direnc else c + 2 * a
    asagi_esik = destek[0]["alt"] if destek else c - 2 * a
    hedef_yukari = direnc[1]["merkez"] if len(direnc) > 1 else yukari_esik + 2 * a
    hedef_asagi = destek[1]["merkez"] if len(destek) > 1 else asagi_esik - 2 * a
    return {
        "boga": f"{_p(yukari_esik)} üstünde hacimli günlük kapanış, yükselişin devamını teyit eder; ilk hedef {_p(hedef_yukari)}.",
        "ayi": f"{_p(asagi_esik)} altında kapanış yapıyı bozar; bir sonraki durak {_p(hedef_asagi)}.",
        "yukari_esik": yukari_esik, "asagi_esik": asagi_esik,
    }
