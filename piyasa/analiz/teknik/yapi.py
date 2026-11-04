"""Fiyat yapısı: tepe-dip noktaları, Dow okuması, uyumsuzluk, Weinstein evresi, Fibonacci."""

from piyasa.bicim import fiyat as _p


def zigzag(df, atr_seri, katsayi=2.0):
    """
    Anlamlı tepe ve dipler: fiyat son uç noktadan en az katsayi × ATR geri dönünce uç kesinleşir.
    [(indeks, fiyat, 'tepe'|'dip'), ...] ve henüz kesinleşmemiş son uç.
    """
    noktalar, son = zigzag_teyitli(df, atr_seri, katsayi)
    return [n[:3] for n in noktalar], son


def zigzag_teyitli(df, atr_seri, katsayi=2.0):
    """
    zigzag ile aynı, ama her noktanın sonunda kesinleştiği gün de vardır: (indeks, fiyat, tür, teyit_günü).
    Geçmiş sınanırken nokta yalnızca teyit gününden sonra bilinir; yoksa sonuçlar geleceği görür.
    """
    yuksek, dusuk = df["High"].to_numpy(), df["Low"].to_numpy()
    a = atr_seri.bfill().to_numpy()
    noktalar = []
    yon = 1
    uc_i, uc_f = 0, yuksek[0]
    for i in range(1, len(df)):
        esik = katsayi * a[i]
        if yon > 0:
            if yuksek[i] >= uc_f:
                uc_i, uc_f = i, yuksek[i]
            elif uc_f - dusuk[i] > esik:
                noktalar.append((uc_i, float(uc_f), "tepe", i))
                yon, uc_i, uc_f = -1, i, dusuk[i]
        else:
            if dusuk[i] <= uc_f:
                uc_i, uc_f = i, dusuk[i]
            elif yuksek[i] - uc_f > esik:
                noktalar.append((uc_i, float(uc_f), "dip", i))
                yon, uc_i, uc_f = 1, i, yuksek[i]
    son = (uc_i, float(uc_f), "tepe" if yon > 0 else "dip")
    return noktalar, son


def yapi(noktalar, son_uc):
    """Son tepe ve diplerin sırası: yükselen tepe-dip = yükseliş yapısı."""
    tepeler = [n for n in noktalar if n[2] == "tepe"][-2:]
    dipler = [n for n in noktalar if n[2] == "dip"][-2:]
    if len(tepeler) < 2 or len(dipler) < 2:
        return {"kod": "belirsiz", "metin": "Tepe-dip yapısı için yeterli salınım yok.", "yon": 0}
    yt = tepeler[1][1] > tepeler[0][1]
    yd = dipler[1][1] > dipler[0][1]
    if yt and yd:
        return {"kod": "yukselis", "yon": 1, "metin": "Yükselen tepeler ve yükselen dipler: klasik yükseliş yapısı (Dow teorisi)."}
    if not yt and not yd:
        return {"kod": "dusus", "yon": -1, "metin": "Alçalan tepeler ve alçalan dipler: düşüş yapısı sürüyor."}
    if yd and not yt:
        return {"kod": "daralan", "yon": 0, "metin": "Dipler yükseliyor ama tepeler alçalıyor: daralan üçgen, kırılım bekleniyor."}
    return {"kod": "genisleyen", "yon": 0, "metin": "Tepeler yükseliyor ama dipler alçalıyor: genişleyen, oynak ve yönsüz yapı."}


def dow_okumasi(df, atr_seri, katsayi=6.0):
    """
    Dow teorisi (Altay 1997, s. 15–27): birincil trend büyük salınımların tepe-dip dizisinden; ikincil düzeltme
    son birincil hareketin 1/3–2/3'ünü geri alır; "çizgi" fiyatın ortalamanın ±%5'i içinde en az 15 gün gitmesidir.
    Yalnızca kapanışlar ve teyitli noktalar kullanılır: trend, kesin dönüş gelene kadar sürüyor sayılır.
    """
    noktalar, _ = zigzag_teyitli(df, atr_seri, katsayi)
    tepeler = [n for n in noktalar if n[2] == "tepe"][-2:]
    dipler = [n for n in noktalar if n[2] == "dip"][-2:]
    c = df["Close"]
    son = float(c.iloc[-1])
    birincil = "belirsiz"
    if len(tepeler) == 2 and len(dipler) == 2:
        yt, yd = tepeler[1][1] > tepeler[0][1], dipler[1][1] > dipler[0][1]
        birincil = "yukselis" if yt and yd else "dusus" if not yt and not yd else "belirsiz"
    # Son teyitli tepe/dip kırıldıysa dizi de değişmiştir
    if tepeler and dipler:
        if son > tepeler[-1][1] and dipler[-1][1] >= (dipler[0][1] if len(dipler) == 2 else 0):
            birincil = "yukselis"
        elif son < dipler[-1][1] and tepeler[-1][1] <= (tepeler[0][1] if len(tepeler) == 2 else float("inf")):
            birincil = "dusus"
    ikincil = None
    if birincil == "yukselis" and dipler:
        ucu = float(df["High"].iloc[dipler[-1][0]:].max())
        if ucu > dipler[-1][1]:
            ikincil = (ucu - son) / (ucu - dipler[-1][1])
    elif birincil == "dusus" and tepeler:
        ucu = float(df["Low"].iloc[tepeler[-1][0]:].min())
        if tepeler[-1][1] > ucu:
            ikincil = (son - ucu) / (tepeler[-1][1] - ucu)
    cizgi_gun = 0
    kapanis = c.to_numpy()
    for n in range(15, min(len(kapanis), 121)):
        parca = kapanis[-n:]
        if parca.max() <= parca.mean() * 1.05 and parca.min() >= parca.mean() * 0.95:
            cizgi_gun = n
        else:
            break
    hacim = df["Volume"].iloc[-50:]
    fark = c.diff().iloc[-50:]
    yuk, dus = hacim[fark > 0].mean(), hacim[fark < 0].mean()
    hacim_teyit = None
    if birincil != "belirsiz" and yuk and dus and yuk == yuk and dus == dus:
        hacim_teyit = bool(yuk > dus) if birincil == "yukselis" else bool(dus > yuk)
    return {"birincil": birincil, "yon": {"yukselis": 1, "dusus": -1}.get(birincil, 0), "ikincil": ikincil,
            "cizgi_gun": cizgi_gun, "hacim_teyit": hacim_teyit}


def dow_metni(d):
    ad = {"yukselis": "birincil trend yükseliş (yükselen tepe ve dipler)", "dusus": "birincil trend düşüş (alçalan tepe ve dipler)",
          "belirsiz": "birincil trend belirsiz: tepe ve dipler aynı yönü göstermiyor"}[d["birincil"]]
    parca = [ad[0].upper() + ad[1:] + "."]
    if d["ikincil"] is not None and d["birincil"] != "belirsiz":
        oran = round(d["ikincil"] * 100)
        hareket = "yükselişin" if d["birincil"] == "yukselis" else "düşüşün"
        if d["ikincil"] > 1:
            parca.append(f"Fiyat son {hareket} tamamını geri aldı: trend dönmüş olabilir.")
        elif d["ikincil"] > 2 / 3:
            parca.append(f"Fiyat son {hareket} %{oran} kadarını geri aldı; bu, olağan ikincil hareketin (1/3–2/3) ötesinde: uyarı.")
        elif d["ikincil"] >= 1 / 3:
            parca.append(f"Fiyat son {hareket} %{oran} kadarını geri aldı: olağan ikincil hareket (1/3–2/3) içinde.")
        else:
            parca.append(f"Geri alınan kısım %{oran}: ikincil hareket sığ.")
    if d["cizgi_gun"]:
        parca.append(f"Fiyat {d['cizgi_gun']} gündür ±%5 içinde yatay (Dow'un \"çizgi\"si): hangi yöne kırarsa sinyal o yöndedir.")
    if d["hacim_teyit"] is not None:
        parca.append("Hacim trendle aynı yönde." if d["hacim_teyit"] else "Hacim trendle ters yönde: uyarı.")
    return " ".join(parca)


def uyumsuzluklar(g, noktalar, son_gun):
    """Fiyat ile RSI arasındaki uyumsuzluk (son iki tepe/dip, son 40 gün içinde)."""
    sonuc = []
    r = g["rsi"].to_numpy()
    m = g["macd_hist"].to_numpy()
    tepeler = [n for n in noktalar if n[2] == "tepe"][-2:]
    dipler = [n for n in noktalar if n[2] == "dip"][-2:]
    if len(tepeler) == 2 and son_gun - tepeler[1][0] <= 40:
        (i1, f1, _), (i2, f2, _) = tepeler
        if f2 > f1 and r[i2] < r[i1] - 2 and r[i1] > 55:
            ek = " MACD histogramı da daha zayıf." if m[i2] < m[i1] else ""
            sonuc.append({"ad": "Negatif uyumsuzluk", "yon": -1,
                          "aciklama": f"Fiyat daha yüksek tepe yaptı ({_p(f1)} → {_p(f2)}) ama RSI daha düşük ({r[i1]:.0f} → {r[i2]:.0f}): "
                                      f"yükselişin gücü azalıyor.{ek}"})
    if len(dipler) == 2 and son_gun - dipler[1][0] <= 40:
        (i1, f1, _), (i2, f2, _) = dipler
        if f2 < f1 and r[i2] > r[i1] + 2 and r[i1] < 45:
            ek = " MACD histogramı da daha güçlü." if m[i2] > m[i1] else ""
            sonuc.append({"ad": "Pozitif uyumsuzluk", "yon": 1,
                          "aciklama": f"Fiyat daha düşük dip yaptı ({_p(f1)} → {_p(f2)}) ama RSI daha yüksek ({r[i1]:.0f} → {r[i2]:.0f}): "
                                      f"satış baskısı zayıflıyor.{ek}"})
    return sonuc


def weinstein_evresi(df):
    """
    Stan Weinstein'ın evre analizi (haftalık 30 haftalık ortalama):
    1 taban, 2 yükseliş, 3 tepe, 4 düşüş. Uzun vadeli yatırımda yalnızca 2. evrede alım önerir.
    """
    haftalik = df["Close"].resample("W-FRI").last().dropna()
    if len(haftalik) < 40:
        return None
    ort = haftalik.rolling(30).mean()
    egim = ort.iloc[-1] / ort.iloc[-5] - 1
    ustunde = haftalik.iloc[-1] > ort.iloc[-1]
    yil_getiri = haftalik.iloc[-1] / haftalik.iloc[-min(52, len(haftalik) - 1)] - 1
    if egim > 0.01 and ustunde:
        evre, metin, yon = 2, "2. evre (yükseliş): fiyat yükselen 30 haftalık ortalamanın üstünde. Trend takipçileri için en verimli evre.", 1
    elif egim < -0.01 and not ustunde:
        evre, metin, yon = 4, "4. evre (düşüş): fiyat alçalan 30 haftalık ortalamanın altında. Uzun vadeli alım için erken.", -1
    elif yil_getiri > 0.15:
        evre, metin, yon = 3, "3. evre (tepe oluşumu): uzun yükselişten sonra 30 haftalık ortalama yataylaştı; dağıtım olabilir.", -0.5
    else:
        evre, metin, yon = 1, "1. evre (taban): düşüşten sonra 30 haftalık ortalama yataylaştı; birikim olabilir, kırılım beklenir.", 0
    return {"evre": evre, "metin": metin, "yon": yon, "egim": float(egim), "ort30": float(ort.iloc[-1])}


def fibonacci(df, pencere=126):
    """Son ~6 ayın en büyük salınımına göre Fibonacci düzeltme seviyeleri."""
    parca = df.iloc[-pencere:]
    if len(parca) < 30:
        return None
    i_ust, i_alt = parca["High"].to_numpy().argmax(), parca["Low"].to_numpy().argmin()
    ust, alt = float(parca["High"].iloc[i_ust]), float(parca["Low"].iloc[i_alt])
    if ust <= alt:
        return None
    yukari = i_alt < i_ust            # önce dip sonra tepe: yükseliş salınımı, düzeltme aşağı ölçülür
    oranlar = (0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0)
    seviyeler = [{"oran": o, "fiyat": round(ust - (ust - alt) * o if yukari else alt + (ust - alt) * o, 4)} for o in oranlar]
    fiyat = float(df["Close"].iloc[-1])
    duzeltme = (ust - fiyat) / (ust - alt) if yukari else (fiyat - alt) / (ust - alt)
    return {"yon": "yukari" if yukari else "asagi", "ust": ust, "alt": alt,
            "ust_tarih": parca.index[i_ust].date(), "alt_tarih": parca.index[i_alt].date(),
            "seviyeler": seviyeler, "duzeltme": float(duzeltme)}
