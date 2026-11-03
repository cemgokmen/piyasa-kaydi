"""
Temel analiz: şirketin kalitesi, büyümesi, finansal sağlığı ve değerlemesi.

Girdi : Yahoo'nun yıllık gelir tablosu, bilanço ve nakit akışı (son 4-5 yıl), son çeyrek
        bilançosu ve 'info' özeti. Hesap (degerlendir) saf bir fonksiyondur, ağa çıkmaz;
        veriyi veri_al indirir.
Çıktı : dört bileşen puanı (−1..+1), 0-100 temel puan, Piotroski F, Altman Z'', güçlü
        yanlar, kırmızı bayraklar ve Türkçe okuma.

Kullanılan modeller ve dayandıkları çalışmalar:
  Piotroski F skoru   9 maddelik muhasebe sağlığı testi (Piotroski 2000). 8-9 güçlü, 0-3 zayıf.
  Altman Z'' (EM)     gelişmekte olan piyasalar ve imalat dışı şirketler için iflas riski
                      (Altman 2005): 3,25 + 6,56·X1 + 3,26·X2 + 6,72·X3 + 1,05·X4.
  Tahakkuk oranı      net karın nakde dönüşmeyen kısmı; yüksek tahakkuk gelecekteki
                      düşük getiriyle ilişkili (Sloan 1996).
  Kalite / karlılık   brüt kar / varlık (Novy-Marx 2013), ROIC, marj istikrarı
                      (Asness, Frazzini, Pedersen "Quality minus junk" 2019).
  Değerleme           F/K, PD/DD, FD/FAVÖK, serbest nakit verimi; tek başına değil,
                      aynı piyasadaki şirketlerin medyanına göre okunur (Fama-French değer etkisi).
  Ters İNA            bugünkü fiyatın 10 yıl boyunca yıllık ne kadar nakit akışı büyümesi
                      varsaydığı (Mauboussin & Rappaport, "Expectations Investing").

TL raporlayan şirketlerde büyüme ve özkaynak karlılığı TÜFE'den arındırılarak (reel)
değerlendirilir: %50 enflasyonda %40 büyüme küçülmedir.
"""

import math

import numpy as np

from piyasa.bicim import ondalik, para

# Bileşen ağırlıkları (toplam 1). Finans şirketlerinde borç oranları ve Altman anlamsızdır.
AGIRLIK = {"kalite": 0.30, "buyume": 0.20, "saglik": 0.25, "degerleme": 0.25}
AGIRLIK_FINANS = {"kalite": 0.40, "buyume": 0.25, "saglik": 0.0, "degerleme": 0.35}

BILESEN_ADLARI = {"kalite": "Kalite ve karlılık", "buyume": "Büyüme", "saglik": "Finansal sağlık",
                  "degerleme": "Değerleme"}

# Karşılaştırma için piyasa medyanı yoksa kullanılan kabaca medyanlar (2024-2026 aralığı)
VARSAYILAN_MEDYAN = {
    "TR": {"fk": 9.0, "pddd": 1.6, "fd_favok": 7.0, "fcf_verimi": 0.04},
    "US": {"fk": 22.0, "pddd": 3.5, "fd_favok": 14.0, "fcf_verimi": 0.04},
}

# Ters İNA için iskonto oranları (yatırımcının beklediği yıllık getiri, raporlama para biriminde)
ISKONTO = {"USD": 0.09, "EUR": 0.08}
UC_BUYUME = 0.025


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _sayi(x):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _bol(a, b):
    a, b = _sayi(a), _sayi(b)
    if a is None or not b:
        return None
    return a / b


def _kirp(x, olcek=1.0):
    if x is None:
        return None
    return max(-1.0, min(1.0, x / olcek))


def _tanh(x, olcek):
    return None if x is None else math.tanh(x / olcek)


def _ort(*degerler, agirlik=None):
    """None olmayanların (ağırlıklı) ortalaması."""
    agirlik = agirlik or [1.0] * len(degerler)
    cift = [(d, w) for d, w in zip(degerler, agirlik, strict=True) if d is not None]
    if not cift:
        return None
    return sum(d * w for d, w in cift) / sum(w for _, w in cift)


def _oran_yazi(x, basamak=1):
    if x is None:
        return "—"
    return f"{'−' if x < 0 else ''}%{ondalik(abs(x) * 100, basamak)}"


def _kat_yazi(x, basamak=1):
    return "—" if x is None else ondalik(x, basamak)


class Tablolar:
    """Yahoo tablolarına güvenli erişim: sütunlar eskiden yeniye sıralı yıllar."""

    def __init__(self, gelir, bilanco, nakit):
        self.gelir, self.bilanco, self.nakit = gelir, bilanco, nakit
        tarihler = set()
        for t in (gelir, bilanco):
            if t is not None and not t.empty:
                tarihler |= set(t.columns)
        # Yalnızca gelir tablosunda geliri olan yıllar
        yillar = []
        for s in sorted(tarihler):
            if self._ham(gelir, ("Total Revenue", "Operating Revenue"), s) is not None:
                yillar.append(s)
        self.yillar = yillar[-5:]

    @staticmethod
    def _ham(tablo, satirlar, sutun):
        if tablo is None or tablo.empty or sutun not in tablo.columns:
            return None
        for satir in satirlar if isinstance(satirlar, tuple) else (satirlar,):
            if satir in tablo.index:
                deger = _sayi(tablo.at[satir, sutun])
                if deger is not None:
                    return deger
        return None

    def g(self, satir, i=-1):
        return self._yil(self.gelir, satir, i)

    def b(self, satir, i=-1):
        return self._yil(self.bilanco, satir, i)

    def n(self, satir, i=-1):
        return self._yil(self.nakit, satir, i)

    def _yil(self, tablo, satir, i):
        if not self.yillar or -i > len(self.yillar):
            return None
        return self._ham(tablo, satir, self.yillar[i])

    def seri(self, kaynak, satir):
        return [self._yil(getattr(self, kaynak), satir, i) for i in range(-len(self.yillar), 0)]


GELIR = ("Total Revenue", "Operating Revenue")
NET = ("Net Income Common Stockholders", "Net Income")
FAALIYET = ("Operating Income", "EBIT")
FAVOK = ("EBITDA", "Normalized EBITDA")
BRUT = ("Gross Profit",)
VARLIK = ("Total Assets",)
OZKAYNAK = ("Stockholders Equity", "Common Stock Equity")
BORC = ("Total Debt",)
NAKIT = ("Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents")
DONEN = ("Current Assets",)
KV_BORC = ("Current Liabilities",)
UV_BORC = ("Long Term Debt", "Long Term Debt And Capital Lease Obligation")
YUKUMLULUK = ("Total Liabilities Net Minority Interest",)
DAGITILMAMIS = ("Retained Earnings",)
ISLETME_SERMAYESI = ("Working Capital",)
HISSE = ("Ordinary Shares Number", "Share Issued")
ISLETME_NAKDI = ("Operating Cash Flow",)
YATIRIM = ("Capital Expenditure",)
SNA = ("Free Cash Flow",)
FAIZ = ("Interest Expense", "Interest Expense Non Operating")
VERGI_ONCESI = ("Pretax Income",)
VERGI = ("Tax Provision",)
TEMETTU = ("Cash Dividends Paid", "Common Stock Dividend Paid")
GERI_ALIM = ("Repurchase Of Capital Stock", "Common Stock Payments")


def _cagr(bas, son, yil):
    bas, son = _sayi(bas), _sayi(son)
    if not bas or son is None or bas <= 0 or son <= 0 or yil <= 0:
        return None
    return (son / bas) ** (1 / yil) - 1


def finans_mi(bilgi, sektor=None):
    s = (bilgi.get("sector") or "") + " " + (bilgi.get("industry") or "")
    return "Financial" in s or "Bank" in s or "Insurance" in s or (sektor or "").startswith("MALİ")


# ---------------------------------------------------------------------------
# Modeller
# ---------------------------------------------------------------------------

def piotroski(t):
    """Piotroski F skoru: 9 ikili test. Son iki yılın tabloları gerekir."""
    if len(t.yillar) < 2:
        return None
    va0, va1 = t.b(VARLIK, -1), t.b(VARLIK, -2)
    net0, net1 = t.g(NET, -1), t.g(NET, -2)
    ian0 = t.n(ISLETME_NAKDI, -1)
    if None in (va0, va1, net0, net1):
        return None
    roa0, roa1 = net0 / va0, net1 / va1
    testler = []

    def test(ad, sonuc, aciklama):
        if sonuc is not None:
            testler.append({"ad": ad, "gecti": bool(sonuc), "aciklama": aciklama})

    test("Karlı", net0 > 0, "Son yılın net karı pozitif")
    test("Nakit üretiyor", ian0 > 0 if ian0 is not None else None, "İşletme faaliyetlerinden nakit akışı pozitif")
    test("Varlık karlılığı arttı", roa0 > roa1, "Net kar / toplam varlık geçen yıldan yüksek")
    test("Kar nakde dayanıyor", ian0 > net0 if ian0 is not None else None, "İşletme nakdi net kardan büyük (tahakkuk düşük)")
    uv0, uv1 = t.b(UV_BORC, -1), t.b(UV_BORC, -2)
    if uv0 is not None and uv1 is not None:
        test("Uzun vadeli borç oranı azaldı", uv0 / va0 <= uv1 / va1, "Uzun vadeli borç / varlık geçen yıldan düşük")
    co0 = _bol(t.b(DONEN, -1), t.b(KV_BORC, -1))
    co1 = _bol(t.b(DONEN, -2), t.b(KV_BORC, -2))
    if co0 is not None and co1 is not None:
        test("Likidite arttı", co0 > co1, "Cari oran geçen yıldan yüksek")
    h0, h1 = t.b(HISSE, -1), t.b(HISSE, -2)
    if h0 and h1:
        test("Hisse sayısı artmadı", h0 <= h1 * 1.005, "Sermaye artırımıyla ortakların payı sulandırılmadı")
    bm0 = _bol(t.g(BRUT, -1), t.g(GELIR, -1))
    bm1 = _bol(t.g(BRUT, -2), t.g(GELIR, -2))
    if bm0 is not None and bm1 is not None:
        test("Brüt marj arttı", bm0 > bm1, "Brüt kar / gelir geçen yıldan yüksek")
    ad0 = _bol(t.g(GELIR, -1), va0)
    ad1 = _bol(t.g(GELIR, -2), va1)
    if ad0 is not None and ad1 is not None:
        test("Varlık devir hızı arttı", ad0 > ad1, "Gelir / toplam varlık geçen yıldan yüksek")
    if len(testler) < 7:
        return None
    puan = sum(x["gecti"] for x in testler)
    # Eksik test varsa 9 üzerinden ölçekle
    olcekli = round(puan * 9 / len(testler))
    return {"puan": puan, "toplam": len(testler), "olcekli": olcekli, "testler": testler}


def altman(t):
    """Altman Z'' (gelişmekte olan piyasa): imalat dışı ve borsa dışı şirketlerde de geçerli."""
    va = t.b(VARLIK)
    if not va:
        return None
    isl = t.b(ISLETME_SERMAYESI)
    if isl is None and t.b(DONEN) is not None and t.b(KV_BORC) is not None:
        isl = t.b(DONEN) - t.b(KV_BORC)
    dk = t.b(DAGITILMAMIS)
    ebit = t.g(FAALIYET)
    ok = t.b(OZKAYNAK)
    yuk = t.b(YUKUMLULUK)
    if None in (isl, dk, ebit, ok, yuk) or not yuk:
        return None
    z = 3.25 + 6.56 * isl / va + 3.26 * dk / va + 6.72 * ebit / va + 1.05 * ok / yuk
    if z > 5.85:
        bolge, etiket, metin = "guvenli", "güvenli bölge", "Yakın vadede finansal sıkıntı riski düşük."
    elif z >= 4.15:
        bolge, etiket, metin = "gri", "gri bölge", "Sıkıntı belirtisi yok ama tampon da geniş değil."
    else:
        bolge, etiket, metin = "riskli", "riskli bölge", "Bu düzeydeki şirketlerde finansal sıkıntı oranı belirgin şekilde yüksek."
    return {"z": round(z, 2), "bolge": bolge, "etiket": etiket, "metin": metin}


def ters_ina(piyasa_degeri, sna, net_borc, para_birimi):
    """
    Bugünkü firma değeri, 10 yıl boyunca serbest nakit akışının yıllık kaç büyümesini varsayıyor?
    Yalnızca sabit para birimlerinde (TL enflasyonunda nominal İNA yanıltıcıdır).
    """
    r = ISKONTO.get(para_birimi)
    if not r or not sna or sna <= 0 or not piyasa_degeri:
        return None
    fd = piyasa_degeri + (net_borc or 0)
    if fd <= 0:
        return None

    def deger(g):
        toplam, akis = 0.0, sna
        for y in range(1, 11):
            akis *= 1 + g
            toplam += akis / (1 + r) ** y
        uc = akis * (1 + UC_BUYUME) / (r - UC_BUYUME) / (1 + r) ** 10
        return toplam + uc

    alt, ust = -0.5, 1.0
    if deger(alt) > fd:
        return {"buyume": alt, "iskonto": r, "metin": "Fiyat, nakit akışının hızla küçüleceğini varsayıyor."}
    if deger(ust) < fd:
        return None
    for _ in range(80):
        orta = (alt + ust) / 2
        if deger(orta) < fd:
            alt = orta
        else:
            ust = orta
    return {"buyume": (alt + ust) / 2, "iskonto": r}


# ---------------------------------------------------------------------------
# Ana değerlendirme
# ---------------------------------------------------------------------------

def degerlendir(bilgi, gelir=None, bilanco=None, nakit=None, ceyrek_bilanco=None, kur=1.0,
                enflasyon=None, medyan=None, sektor=None):
    """
    bilgi       : yfinance 'info'
    gelir...    : yıllık tablolar (yfinance income_stmt, balance_sheet, cashflow)
    kur         : fiyat para birimi / raporlama para birimi (ör. THYAO: USD raporlar, TL işlem görür → USDTRY)
    enflasyon   : {yil: yıllık TÜFE oranı} — TL raporlayanlar için
    medyan      : aynı piyasadaki şirketlerin değerleme medyanları {fk, pddd, fd_favok, fcf_verimi}
    """
    if not bilgi or bilgi.get("quoteType") not in (None, "EQUITY"):
        return None
    t = Tablolar(gelir, bilanco, nakit)
    if not t.yillar:
        return None

    pb = bilgi.get("currency") or "USD"
    rb = bilgi.get("financialCurrency") or pb
    tr = pb == "TRY"
    finans = finans_mi(bilgi, sektor)
    medyan = {**VARSAYILAN_MEDYAN["TR" if tr else "US"], **(medyan or {})}
    kur = kur or 1.0

    # --- Son durum (son 12 ay info'dan, yoksa son yıllık tablodan)
    pd_fiyat = _sayi(bilgi.get("marketCap"))
    pd_rapor = pd_fiyat / kur if pd_fiyat else None             # piyasa değeri, raporlama para biriminde
    # Yabancı para raporlayanlarda Yahoo'nun son 12 ay rakamları bazen raporlama, bazen fiyat
    # para birimindedir (TAVHL: tablolar EUR, özet TL). Yıllık gelirle karşılaştırıp hangisi olduğu bulunur.
    ttm_bolen = 1.0
    if rb != pb and kur > 1.5:
        ozet_gelir, yillik_gelir = _sayi(bilgi.get("totalRevenue")), t.g(GELIR)
        if ozet_gelir and yillik_gelir and yillik_gelir > 0:
            oran = ozet_gelir / yillik_gelir
            if abs(math.log(oran / kur)) < abs(math.log(oran)):
                ttm_bolen = kur

    def ttm(alan):
        deger = _sayi(bilgi.get(alan))
        return deger / ttm_bolen if deger is not None else None

    gelir_12 = ttm("totalRevenue") or t.g(GELIR)
    net_12 = ttm("netIncomeToCommon")
    if net_12 is None:
        net_12 = t.g(NET)
    favok_12 = ttm("ebitda") or t.g(FAVOK)
    sna_12 = ttm("freeCashflow")
    if sna_12 is None:
        sna_12 = t.n(SNA)
    ian_12 = ttm("operatingCashflow") or t.n(ISLETME_NAKDI)

    def son_bilanco(satirlar):
        if ceyrek_bilanco is not None and not ceyrek_bilanco.empty:
            s = sorted(ceyrek_bilanco.columns)[-1]
            d = Tablolar._ham(ceyrek_bilanco, satirlar, s)
            if d is not None:
                return d
        return t.b(satirlar)

    ozk = son_bilanco(OZKAYNAK)
    borc = son_bilanco(BORC) or 0.0
    nakit_ = son_bilanco(NAKIT) or 0.0
    net_borc = borc - nakit_
    varlik = son_bilanco(VARLIK)

    # --- Enflasyon. TL raporlayan şirketler 2023'ten beri TMS 29 (enflasyon muhasebesi) uygular:
    # kar ve özkaynak bugünün satın alma gücüyle yazılır, özkaynak karlılığı zaten reeldir.
    # Yahoo'da son yıl kendi yıl sonu TL'siyle, önceki her yıl bir sonraki yılın raporundaki
    # düzeltilmiş haliyle (bir yıl sonraki TL'yle) durur. Bankalar ve sigortacılar TMS 29
    # uygulamaz: her yıl kendi nominal TL'siyledir.
    tl = rb == "TRY" and bool(enflasyon)
    tms29 = tl and not finans

    def reel_adimlar(seri):
        """Ardışık yıllar arasındaki reel büyümeler (TL değilse nominal)."""
        adimlar = []
        yillar = [y.year for y in t.yillar]
        for i in range(1, len(seri)):
            a, b = seri[i - 1], seri[i]
            if a is None or b is None or a <= 0 or b <= 0:
                adimlar.append(None)
                continue
            oran = b / a
            if tl:
                if tms29:
                    enf = 0.0 if i == len(seri) - 1 else (enflasyon.get(yillar[i] + 1) or 0.0)
                else:
                    enf = enflasyon.get(yillar[i]) or 0.0
                oran /= 1 + enf
            adimlar.append(oran - 1)
        return adimlar

    def reel_cagr(seri):
        adimlar = reel_adimlar(seri)
        if not adimlar or any(a is None for a in adimlar):
            return None
        return math.prod(1 + a for a in adimlar) ** (1 / len(adimlar)) - 1

    # Bankalarda (TMS 29 yok) özkaynak karlılığı son yılın enflasyonuyla reelleştirilir
    son_enf = enflasyon.get(t.yillar[-1].year) if tl and not tms29 else None

    # -----------------------------------------------------------------
    # 1. KALİTE VE KARLILIK
    # -----------------------------------------------------------------
    ozk_ort = _ort(t.b(OZKAYNAK, -1), t.b(OZKAYNAK, -2)) if len(t.yillar) > 1 else t.b(OZKAYNAK)
    roe = _bol(net_12, ozk_ort) if ozk_ort and ozk_ort > 0 else None
    roe_reel = (1 + roe) / (1 + son_enf) - 1 if roe is not None and son_enf is not None else roe
    roa = _bol(net_12, varlik)
    ebit = t.g(FAALIYET)
    vergi_orani = _bol(t.g(VERGI), t.g(VERGI_ONCESI))
    vergi_orani = min(max(vergi_orani, 0.0), 0.4) if vergi_orani is not None else 0.22
    yatirilan = (t.b(OZKAYNAK) or 0) + (t.b(BORC) or 0) - (t.b(NAKIT) or 0)
    roic = ebit * (1 - vergi_orani) / yatirilan if ebit is not None and yatirilan > 0 else None
    roic_reel = (1 + roic) / (1 + son_enf) - 1 if roic is not None and son_enf is not None else roic
    brut_marj = _bol(t.g(BRUT), t.g(GELIR))
    faaliyet_marj = _bol(t.g(FAALIYET), t.g(GELIR))
    net_marj = _bol(net_12, gelir_12)
    brut_varlik = _bol(t.g(BRUT), t.b(VARLIK))          # Novy-Marx karlılık ölçüsü
    marjlar = [_bol(f, g) for f, g in zip(t.seri("gelir", FAALIYET), t.seri("gelir", GELIR), strict=True)]
    marjlar = [m for m in marjlar if m is not None]
    marj_oynaklik = float(np.std(marjlar)) if len(marjlar) >= 3 else None
    zarar_yili = sum(1 for n in t.seri("gelir", NET) if n is not None and n < 0)

    kalite = _ort(
        _tanh((roe_reel - 0.10) if roe_reel is not None else None, 0.10),
        None if finans else _tanh((roic_reel - 0.08) if roic_reel is not None else None, 0.08),
        None if finans else _tanh((brut_varlik - 0.25) if brut_varlik is not None else None, 0.20),
        None if finans or marj_oynaklik is None else _kirp(1 - marj_oynaklik / 0.05),
        _kirp(1 - zarar_yili) if len(t.yillar) >= 3 else None,
        agirlik=[0.30, 0.25, 0.15, 0.15, 0.15],
    )

    # -----------------------------------------------------------------
    # 2. BÜYÜME (TL raporlayanlarda reel)
    # -----------------------------------------------------------------
    n_yil = len(t.yillar) - 1
    gelir_s, net_s = t.seri("gelir", GELIR), t.seri("gelir", NET)
    hbk_s = [_bol(n, h) for n, h in zip(net_s, t.seri("bilanco", HISSE), strict=True)]
    gelir_cagr = _cagr(gelir_s[0], gelir_s[-1], n_yil) if n_yil >= 1 else None
    net_cagr = _cagr(net_s[0], net_s[-1], n_yil) if n_yil >= 1 else None
    gelir_1y = _cagr(gelir_s[-2], gelir_s[-1], 1) if n_yil >= 1 else None
    hbk_cagr = _cagr(hbk_s[0], hbk_s[-1], n_yil) if n_yil >= 1 else None
    gelir_cagr_r, net_cagr_r, hbk_cagr_r = reel_cagr(gelir_s), reel_cagr(net_s), reel_cagr(hbk_s)
    gelir_1y_r = (reel_adimlar(gelir_s) or [None])[-1]
    buyume = _ort(
        _tanh((gelir_cagr_r - 0.05) if gelir_cagr_r is not None else None, 0.10),
        _tanh((hbk_cagr_r - 0.05) if hbk_cagr_r is not None else None, 0.15),
        _tanh((gelir_1y_r - 0.05) if gelir_1y_r is not None else None, 0.12),
        agirlik=[0.40, 0.35, 0.25],
    )

    # -----------------------------------------------------------------
    # 3. FİNANSAL SAĞLIK
    # -----------------------------------------------------------------
    f_skor = piotroski(t)
    z = None if finans else altman(t)
    nb_favok = net_borc / favok_12 if favok_12 and favok_12 > 0 else None
    faiz = t.g(FAIZ)
    faiz_karsilama = ebit / abs(faiz) if ebit is not None and faiz else None
    cari = _bol(son_bilanco(DONEN), son_bilanco(KV_BORC))
    # Bankalarda işletme nakdi mevduat ve kredi hareketleriyle oynar: tahakkuk ölçüsü anlamsız
    tahakkuk = (net_12 - ian_12) / varlik if None not in (net_12, ian_12) and varlik and not finans else None
    nakit_donusum = _bol(ian_12, net_12) if net_12 and net_12 > 0 and not finans else None
    if finans:
        saglik = _ort(_kirp((f_skor["olcekli"] - 4.5) / 3.5) if f_skor else None)
    else:
        saglik = _ort(
            _kirp((f_skor["olcekli"] - 4.5) / 3.5) if f_skor else None,
            _kirp((z["z"] - 5.0) / 2.0) if z else None,
            (_kirp((2.5 - nb_favok) / 2.0) if nb_favok > 0 else 1.0) if nb_favok is not None else
            (-1.0 if net_borc > 0 and (favok_12 or 0) <= 0 else None),
            _kirp((math.log(max(faiz_karsilama, 0.01)) - math.log(4)) / math.log(4)) if faiz_karsilama is not None else None,
            _kirp((cari - 1.2) / 0.8) if cari is not None else None,
            _kirp(-tahakkuk / 0.08) if tahakkuk is not None else None,
            agirlik=[0.25, 0.20, 0.20, 0.15, 0.10, 0.10],
        )

    # -----------------------------------------------------------------
    # 4. DEĞERLEME (aynı piyasadaki medyanlara göre)
    # -----------------------------------------------------------------
    fk = pd_rapor / net_12 if pd_rapor and net_12 and net_12 > 0 else None
    pddd = pd_rapor / ozk if pd_rapor and ozk and ozk > 0 else None
    fd = pd_rapor + net_borc if pd_rapor else None
    fd_favok = fd / favok_12 if fd and favok_12 and favok_12 > 0 and not finans else None
    fcf_verimi = sna_12 / pd_rapor if pd_rapor and sna_12 is not None and not finans else None
    fs = pd_rapor / gelir_12 if pd_rapor and gelir_12 and not finans else None
    temettu = _sayi(bilgi.get("dividendYield"))
    temettu = temettu / 100 if temettu is not None else None
    geri_alim = t.n(GERI_ALIM)
    geri_alim_verimi = abs(geri_alim) / pd_rapor if geri_alim and pd_rapor else None
    h_son, h_ilk = t.b(HISSE), t.b(HISSE, 0 - len(t.yillar))
    sulanma = _cagr(h_ilk, h_son, n_yil) if n_yil >= 1 else None

    def goreli(deger, ref, ters=False):
        """Medyanın yarısı +1, medyan 0, iki katı −1 (log ölçek)."""
        if deger is None or not ref:
            return None
        x = math.log(ref / deger) if not ters else math.log(deger / ref)
        return _kirp(x / math.log(2))

    degerleme = _ort(
        goreli(fk, medyan["fk"]) if fk else (-0.8 if net_12 is not None and net_12 <= 0 else None),
        goreli(pddd, medyan["pddd"]),
        goreli(fd_favok, medyan["fd_favok"]),
        _kirp((fcf_verimi - medyan["fcf_verimi"]) / 0.05) if fcf_verimi is not None else None,
        agirlik=[0.30, 0.20 if not finans else 0.50, 0.25, 0.25],
    )

    bilesen = {"kalite": kalite, "buyume": buyume, "saglik": saglik, "degerleme": degerleme}
    agirlik = AGIRLIK_FINANS if finans else AGIRLIK
    toplam_w = sum(w for k, w in agirlik.items() if bilesen[k] is not None and w > 0)
    puan = None
    if toplam_w >= 0.5:
        puan = 50 + 50 * sum(bilesen[k] * w for k, w in agirlik.items() if bilesen[k] is not None and w > 0) / toplam_w

    ina = ters_ina(pd_rapor, sna_12, net_borc, rb) if not finans else None

    sonuc = {
        "puan": round(puan, 1) if puan is not None else None,
        "bilesen": {k: (round(v, 3) if v is not None else None) for k, v in bilesen.items()},
        "agirlik": agirlik,
        "finans": finans,
        "para": pb, "rapor_para": rb, "kur": kur,
        "yillar": [y.year for y in t.yillar],
        "son_yil": t.yillar[-1].date().isoformat(),
        "reel": tl, "tms29": tms29,
        "oranlar": {
            "roe": roe, "roe_reel": roe_reel, "roa": roa, "roic": roic, "roic_reel": roic_reel,
            "brut_marj": brut_marj, "faaliyet_marj": faaliyet_marj, "net_marj": net_marj, "brut_varlik": brut_varlik,
            "marj_oynaklik": marj_oynaklik, "zarar_yili": zarar_yili,
            "gelir_cagr": gelir_cagr, "gelir_cagr_reel": gelir_cagr_r, "net_cagr": net_cagr, "net_cagr_reel": net_cagr_r,
            "gelir_1y": gelir_1y, "gelir_1y_reel": gelir_1y_r, "hbk_cagr": hbk_cagr, "hbk_cagr_reel": hbk_cagr_r,
            "nb_favok": nb_favok, "faiz_karsilama": faiz_karsilama, "cari": cari, "tahakkuk": tahakkuk,
            "nakit_donusum": nakit_donusum,
            "fk": fk, "pddd": pddd, "fd_favok": fd_favok, "fcf_verimi": fcf_verimi, "fs": fs,
            "temettu": temettu, "geri_alim_verimi": geri_alim_verimi, "sulanma": sulanma,
            "net_borc": net_borc, "piyasa_degeri": pd_rapor, "son_enflasyon": son_enf,
        },
        "medyan": medyan,
        "piotroski": f_skor,
        "altman": z,
        "ters_ina": ina,
        "tarihce": _tarihce(t, rb),
    }
    sonuc["guclu"], sonuc["bayraklar"] = _yanlar(sonuc)
    sonuc["okuma"] = _okuma(sonuc)
    return sonuc


def _tarihce(t, rb):
    """Yıllara göre ana kalemler (grafik ve tablo için)."""
    satirlar = []
    for i, y in enumerate(t.yillar):
        j = i - len(t.yillar)
        gelir, net = t.g(GELIR, j), t.g(NET, j)
        satirlar.append({
            "yil": y.year, "gelir": gelir, "net": net, "faaliyet": t.g(FAALIYET, j),
            "ian": t.n(ISLETME_NAKDI, j), "sna": t.n(SNA, j), "ozkaynak": t.b(OZKAYNAK, j),
            "borc": t.b(BORC, j), "net_marj": _bol(net, gelir),
            "gelir_yazi": para(gelir, rb), "net_yazi": para(net, rb),
            "sna_yazi": para(t.n(SNA, j), rb) if t.n(SNA, j) is not None else "—",
        })
    return satirlar


def _yanlar(s):
    o = s["oranlar"]
    guclu, bayrak = [], []
    roe = o["roe_reel"]
    reel = " (enflasyondan arındırılmış)" if s["reel"] else ""
    if roe is not None and roe > 0.20:
        guclu.append(f"Özkaynak karlılığı yüksek: {_oran_yazi(roe)}{reel}.")
    if o["roic_reel"] is not None and o["roic_reel"] > 0.15 and not s["finans"]:
        guclu.append(f"Yatırılan sermayenin getirisi (ROIC) {_oran_yazi(o['roic_reel'])}{reel}: sermayeyi verimli kullanıyor.")
    if s["piotroski"] and s["piotroski"]["olcekli"] >= 7:
        guclu.append(f"Piotroski F skoru {s['piotroski']['puan']}/{s['piotroski']['toplam']}: muhasebe göstergeleri iyileşiyor.")
    if s["altman"] and s["altman"]["bolge"] == "guvenli":
        guclu.append(f"Altman Z'' {ondalik(s['altman']['z'], 2)}: iflas riski bölgesinden uzak.")
    if o["nb_favok"] is not None and o["nb_favok"] < 0:
        guclu.append("Net nakit pozisyonunda: borcundan fazla nakdi var.")
    if o["gelir_cagr_reel"] is not None and o["gelir_cagr_reel"] > 0.15:
        guclu.append(f"Gelir yılda ortalama {_oran_yazi(o['gelir_cagr_reel'])} büyüyor{reel}.")
    if o["fcf_verimi"] is not None and o["fcf_verimi"] > 0.07:
        guclu.append(f"Serbest nakit verimi {_oran_yazi(o['fcf_verimi'])}: piyasa değerine göre bol nakit üretiyor.")
    if o["nakit_donusum"] is not None and o["nakit_donusum"] > 1.1:
        guclu.append("Kar nakde dönüşüyor: işletme nakdi net kardan büyük.")
    if o["temettu"] and o["temettu"] > 0.04:
        guclu.append(f"Temettü verimi {_oran_yazi(o['temettu'])}.")

    if o["zarar_yili"] and o["zarar_yili"] >= 2:
        bayrak.append(f"Son {len(s['yillar'])} yılın {o['zarar_yili']} yılında zarar.")
    if s["altman"] and s["altman"]["bolge"] == "riskli":
        bayrak.append(f"Altman Z'' {ondalik(s['altman']['z'], 2)}: finansal sıkıntı riski bölgesinde.")
    if s["piotroski"] and s["piotroski"]["olcekli"] <= 3:
        bayrak.append(f"Piotroski F skoru {s['piotroski']['puan']}/{s['piotroski']['toplam']}: muhasebe göstergeleri kötüleşiyor.")
    if o["nb_favok"] is not None and o["nb_favok"] > 4:
        bayrak.append(f"Net borç FAVÖK'ün {ondalik(o['nb_favok'], 1)} katı: borç yükü ağır.")
    if o["faiz_karsilama"] is not None and o["faiz_karsilama"] < 1.5 and not s["finans"]:
        bayrak.append(f"Faaliyet karı faiz giderini yalnızca {ondalik(o['faiz_karsilama'], 1)} kat karşılıyor.")
    if o["tahakkuk"] is not None and o["tahakkuk"] > 0.10:
        bayrak.append("Karın büyük kısmı nakde dönmüyor (yüksek tahakkuk): kar kalitesi zayıf.")
    if o["sulanma"] is not None and o["sulanma"] > 0.08:
        bayrak.append(f"Hisse sayısı yılda {_oran_yazi(o['sulanma'])} artıyor: bedelli sermaye artırımlarıyla sulanma.")
    if o["roe_reel"] is not None and o["roe_reel"] < 0 and s["reel"]:
        bayrak.append(f"Enflasyondan arındırılmış özkaynak karlılığı eksi ({_oran_yazi(o['roe_reel'])}): ortakların sermayesi reel olarak eriyor.")
    if o["gelir_cagr_reel"] is not None and o["gelir_cagr_reel"] < -0.05:
        bayrak.append(f"Gelir reel olarak küçülüyor (yılda {_oran_yazi(o['gelir_cagr_reel'])}).")
    if o["fk"] is not None and o["fk"] > 3 * s["medyan"]["fk"]:
        bayrak.append(f"F/K {ondalik(o['fk'], 1)}: piyasa medyanının ({ondalik(s['medyan']['fk'], 1)}) üç katından fazla; beklentiler çok yüksek.")
    return guclu, bayrak


def _okuma(s):
    """Her bileşen için iki-üç cümlelik açıklama."""
    o, m = s["oranlar"], []
    reel = s["reel"]

    def ekle(baslik, puan, metin):
        m.append({"baslik": baslik, "yon": 0 if puan is None else (1 if puan > 0.2 else -1 if puan < -0.2 else 0), "metin": metin})

    # Kalite
    p = []
    if o["roe"] is not None:
        if s["tms29"]:
            p.append(f"Özkaynak karlılığı {_oran_yazi(o['roe'])} (enflasyon muhasebesiyle, yani reel)")
        else:
            p.append(f"Özkaynak karlılığı {_oran_yazi(o['roe'])}" + (f", enflasyondan arındırınca {_oran_yazi(o['roe_reel'])}" if reel and o["roe_reel"] is not None else ""))
    if o["roic"] is not None and not s["finans"]:
        p.append(f"yatırılan sermaye getirisi {_oran_yazi(o['roic'])}")
    if o["faaliyet_marj"] is not None:
        p.append(f"faaliyet kar marjı {_oran_yazi(o['faaliyet_marj'])}")
    metin = (", ".join(p) + ".") if p else "Karlılık verisi eksik."
    metin = metin[0].upper() + metin[1:]
    if o["marj_oynaklik"] is not None:
        metin += (" Marjlar yıllar içinde istikrarlı." if o["marj_oynaklik"] < 0.03 else
                  " Marjlar yıldan yıla çok oynuyor: döngüsel ya da fiyatlama gücü zayıf bir iş." if o["marj_oynaklik"] > 0.08 else "")
    ekle(BILESEN_ADLARI["kalite"], s["bilesen"]["kalite"], metin)

    # Büyüme
    if o["gelir_cagr"] is not None:
        n = len(s["yillar"]) - 1
        if reel and o["gelir_cagr_reel"] is not None:
            metin = f"Son {n} yılda gelir enflasyondan arındırılmış olarak yılda ortalama {_oran_yazi(o['gelir_cagr_reel'])} değişti"
        else:
            metin = f"Son {n} yılda gelir yılda ortalama {_oran_yazi(o['gelir_cagr'])} değişti"
        if o["hbk_cagr"] is not None:
            hbk = o["hbk_cagr_reel"] if reel else o["hbk_cagr"]
            if hbk is not None:
                metin += f"; hisse başına kar yılda {_oran_yazi(hbk)}" + (" (reel)" if reel else "")
        metin += "."
        if reel and o["gelir_1y_reel"] is not None:
            metin += f" Son yıl reel gelir değişimi {_oran_yazi(o['gelir_1y_reel'])}."
        if reel:
            metin += (" Yıllar enflasyon muhasebesi (TMS 29) düzeltmeleri hesaba katılarak karşılaştırıldı." if s["tms29"] else
                      " Bankalar enflasyon muhasebesi uygulamadığı için her yıl o yılın TÜFE'siyle arındırıldı.")
    else:
        metin = "Büyüme için yeterli yıllık veri yok."
    ekle(BILESEN_ADLARI["buyume"], s["bilesen"]["buyume"], metin)

    # Sağlık
    if s["finans"]:
        metin = "Banka ve finans şirketlerinde borç, mevduat ve kredinin kendisidir; borç oranları ve Altman skoru uygulanmaz. Özkaynak karlılığı ve PD/DD öne çıkar."
    else:
        p = []
        if o["nb_favok"] is not None:
            p.append("net nakit pozisyonunda" if o["nb_favok"] < 0 else f"net borç / FAVÖK {ondalik(o['nb_favok'], 1)}")
        if o["faiz_karsilama"] is not None:
            p.append(f"faiz karşılama {ondalik(o['faiz_karsilama'], 1)} kat")
        if o["cari"] is not None:
            p.append(f"cari oran {ondalik(o['cari'], 2)}")
        metin = (", ".join(p) + ".") if p else ""
        metin = metin[:1].upper() + metin[1:]
        if s["altman"]:
            metin += f" Altman Z'' {ondalik(s['altman']['z'], 2)} ({s['altman']['etiket']}): {s['altman']['metin'][0].lower()}{s['altman']['metin'][1:]}"
    if s["piotroski"]:
        metin += f" Piotroski F skoru {s['piotroski']['puan']}/{s['piotroski']['toplam']}."
    ekle(BILESEN_ADLARI["saglik"], s["bilesen"]["saglik"], metin.strip())

    # Değerleme
    md = s["medyan"]
    p = []
    if o["fk"] is not None:
        p.append(f"F/K {_kat_yazi(o['fk'])} (piyasa medyanı {_kat_yazi(md['fk'])})")
    if o["pddd"] is not None:
        p.append(f"PD/DD {_kat_yazi(o['pddd'], 2)} (medyan {_kat_yazi(md['pddd'], 2)})")
    if o["fd_favok"] is not None:
        p.append(f"FD/FAVÖK {_kat_yazi(o['fd_favok'])} (medyan {_kat_yazi(md['fd_favok'])})")
    if o["fcf_verimi"] is not None:
        p.append(f"serbest nakit verimi {_oran_yazi(o['fcf_verimi'])}")
    metin = ("; ".join(p) + ".") if p else "Değerleme oranları hesaplanamadı."
    if s["ters_ina"]:
        g = s["ters_ina"]["buyume"]
        metin += (f" Ters İNA: bugünkü fiyat, serbest nakit akışının 10 yıl boyunca yılda {_oran_yazi(g)} büyüyeceğini varsayıyor "
                  f"(yıllık %{ondalik(s['ters_ina']['iskonto'] * 100, 0)} getiri beklentisiyle). ")
        metin += ("Bu, çoğu şirketin ulaşamadığı bir hız: fiyat iyimser." if g > 0.15 else
                  "Ulaşılabilir bir beklenti." if g > 0.03 else "Fiyat neredeyse hiç büyüme beklemiyor: hayal kırıklığına karşı tampon var.")
    ekle(BILESEN_ADLARI["degerleme"], s["bilesen"]["degerleme"], metin)
    return m


# ---------------------------------------------------------------------------
# Veri
# ---------------------------------------------------------------------------

def veri_al(kod):
    """Yahoo'dan ham tablolar. Ağ hatası yükselir (çağıran önbelleğe almasın diye)."""
    import yfinance as yf
    t = yf.Ticker(kod)
    bilgi = t.info or {}
    if len(bilgi) <= 5:
        raise RuntimeError(f"{kod}: Yahoo özeti boş")

    def guvenli(al):
        try:
            return al()
        except Exception:
            return None

    gelir, bilanco, nakit = guvenli(lambda: t.income_stmt), guvenli(lambda: t.balance_sheet), guvenli(lambda: t.cashflow)
    ceyrek = guvenli(lambda: t.quarterly_balance_sheet)
    kur = 1.0
    pb, rb = bilgi.get("currency"), bilgi.get("financialCurrency")
    if pb and rb and pb != rb:
        hizli = guvenli(lambda: yf.Ticker(f"{rb}{pb}=X").fast_info.last_price)
        kur = float(hizli) if hizli else None
        if not kur:
            raise RuntimeError(f"{rb}{pb} kuru alınamadı")
    return {"bilgi": bilgi, "gelir": gelir, "bilanco": bilanco, "nakit": nakit, "ceyrek_bilanco": ceyrek, "kur": kur}


def yillik_enflasyon(aylik):
    """{'2024-12': endeks, ...} → {2024: yıl sonu / önceki yıl sonu − 1}"""
    if not aylik:
        return {}
    sonuc = {}
    yillar = sorted({int(a[:4]) for a in aylik})
    for y in yillar:
        son = aylik.get(f"{y}-12")
        onceki = aylik.get(f"{y - 1}-12")
        if son and onceki:
            sonuc[y] = son / onceki - 1
    # İçinde bulunulan yıl: son 12 ay
    aylar = sorted(aylik)
    if len(aylar) > 12:
        son_ay = aylar[-1]
        y = int(son_ay[:4])
        if y not in sonuc:
            onceki = aylik.get(f"{y - 1}{son_ay[4:]}")
            if onceki:
                sonuc[y] = aylik[son_ay] / onceki - 1
    return sonuc
