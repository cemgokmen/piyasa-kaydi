"""
Emtia sayfalarının veritabanı sorguları ve hesapları: CFTC fon konumları,
EIA stokları, faiz kararları. Fiyatlar burada değil, web/fiyat.py'de.
"""

from contextlib import closing
from datetime import date, timedelta

from piyasa.emtia.tanimlar import EIA_SERILERI
from piyasa.veritabani import get_connection


def baglanti():
    return closing(get_connection())


def _yuzdelik(deger, liste):
    """Değer listenin neresinde: 0 en düşük, 100 en yüksek."""
    if not liste:
        return None
    alttakiler = sum(1 for v in liste if v < deger)
    return round(alttakiler / max(len(liste) - 1, 1) * 100)


# ---------------------------------------------------------------------------
# CFTC: büyük spekülatif fonların konumu
# ---------------------------------------------------------------------------

def _cot_yorumu(konum, degisim):
    if konum is None:
        return ""
    if konum >= 85:
        durum = "Fonlar son bir yılın en iyimser seviyesine yakın (çok fazla alım pozisyonu)."
    elif konum >= 60:
        durum = "Fonlar yükseliş beklentisinde, son bir yılın ortalamasının üstünde."
    elif konum <= 15:
        durum = "Fonlar son bir yılın en kötümser seviyesine yakın."
    elif konum <= 40:
        durum = "Fonların iyimserliği son bir yılın ortalamasının altında."
    else:
        durum = "Fonların konumu son bir yılın ortalaması civarında."
    yon = "artırdı" if degisim > 0 else "azalttı"
    return f"{durum} Geçen hafta net alım pozisyonlarını {yon}."


def cot(slug, hafta=104):
    """Bir emtianın haftalık fon konumu serisi ve özeti; veri yoksa None."""
    with baglanti() as conn:
        satirlar = [dict(s) for s in conn.execute(
            "SELECT * FROM cot WHERE emtia = ? ORDER BY tarih DESC LIMIT ?", (slug, hafta)
        )]
    if not satirlar:
        return None
    satirlar.reverse()

    for s in satirlar:
        s["fon_net"] = s["fon_uzun"] - s["fon_kisa"]
        s["uretici_net"] = s["uretici_uzun"] - s["uretici_kisa"]

    son = satirlar[-1]
    onceki = satirlar[-2] if len(satirlar) > 1 else son
    dort_once = satirlar[-5] if len(satirlar) > 4 else satirlar[0]
    yillik = [s["fon_net"] for s in satirlar[-52:]]
    konum = _yuzdelik(son["fon_net"], yillik)
    degisim = son["fon_net"] - onceki["fon_net"]

    return {
        "tarih": son["tarih"],
        "fon_net": son["fon_net"],
        "fon_uzun": son["fon_uzun"],
        "fon_kisa": son["fon_kisa"],
        "uretici_net": son["uretici_net"],
        "acik_pozisyon": son["acik_pozisyon"],
        "haftalik_degisim": degisim,
        "dort_haftalik_degisim": son["fon_net"] - dort_once["fon_net"],
        "konum": konum,
        "yorum": _cot_yorumu(konum, degisim),
        "seri": [[s["tarih"], s["fon_net"]] for s in satirlar],
    }


def cot_tablosu(emtialar):
    """Genel bakış tablosu: her emtianın son fon konumu."""
    tablo = []
    for e in emtialar:
        if not e["cot"]:
            continue
        ozet = cot(e["slug"], hafta=53)
        if ozet:
            tablo.append({"emtia": e, **{k: v for k, v in ozet.items() if k != "seri"}})
    return tablo


# ---------------------------------------------------------------------------
# EIA: ABD stokları
# ---------------------------------------------------------------------------

def eia(seri_adi, yil=3):
    """Haftalık stok serisi, geçen yılla ve 5 yıllık ortalamayla karşılaştırma."""
    tanim = EIA_SERILERI[seri_adi]
    bolen = tanim["bolen"]
    baslangic = (date.today() - timedelta(days=365 * 6)).isoformat()
    with baglanti() as conn:
        satirlar = [(s["tarih"], s["deger"] / bolen) for s in conn.execute(
            "SELECT tarih, deger FROM eia_stok WHERE seri = ? AND tarih >= ? ORDER BY tarih",
            (seri_adi, baslangic),
        )]
    if len(satirlar) < 2:
        return None

    son_tarih, son = satirlar[-1]
    onceki = satirlar[-2][1]
    son_gun = date.fromisoformat(son_tarih)

    def yakin_hafta(hedef):
        """Hedef tarihe en yakın haftanın değeri (±4 gün)."""
        for t, v in satirlar:
            if abs((date.fromisoformat(t) - hedef).days) <= 4:
                return v
        return None

    gecen_yil = yakin_hafta(son_gun - timedelta(days=364))
    bes_yil = [v for n in range(1, 6) if (v := yakin_hafta(son_gun - timedelta(days=364 * n))) is not None]
    bes_yil_ort = sum(bes_yil) / len(bes_yil) if bes_yil else None

    def oran(a, b):
        return (a / b - 1) if b else None

    return {
        "ad": tanim["ad"],
        "birim": tanim["birim"],
        "tarih": son_tarih,
        "deger": son,
        "haftalik_degisim": son - onceki,
        "gecen_yila_gore": oran(son, gecen_yil),
        "bes_yil_ortalamasi": bes_yil_ort,
        "bes_yila_gore": oran(son, bes_yil_ort),
        "seri": [[t, round(v, 2)] for t, v in satirlar if t >= (son_gun - timedelta(days=365 * yil)).isoformat()],
    }


# ---------------------------------------------------------------------------
# FRED: faiz kararları ve tahvil faizleri
# ---------------------------------------------------------------------------

def _seri(conn, ad, baslangic):
    return [(s["tarih"], s["deger"]) for s in conn.execute(
        "SELECT tarih, deger FROM makro WHERE seri = ? AND tarih >= ? ORDER BY tarih",
        (ad, baslangic),
    )]


def faiz_kararlari(yil=4):
    """Fed politika faizindeki değişiklikler (en yeni önce) ve tahvil faizleri."""
    baslangic = (date.today() - timedelta(days=365 * yil)).isoformat()
    with baglanti() as conn:
        fed = _seri(conn, "fed_faiz", baslangic)
        tahvil = _seri(conn, "abd_10y", baslangic)
        reel = _seri(conn, "reel_faiz", baslangic)

    if not fed:
        return None

    kararlar = []
    for (t0, v0), (t1, v1) in zip(fed, fed[1:]):
        if v1 != v0:
            kararlar.append({"tarih": t1, "faiz": v1, "degisim": v1 - v0})
    kararlar.reverse()

    def ozet(seri):
        if not seri:
            return None
        son_t, son = seri[-1]
        ay_once = next((v for t, v in reversed(seri)
                        if t <= (date.fromisoformat(son_t) - timedelta(days=30)).isoformat()), None)
        return {"tarih": son_t, "deger": son,
                "aylik_degisim": None if ay_once is None else son - ay_once}

    return {
        "fed": {"deger": fed[-1][1], "tarih": fed[-1][0]},
        "kararlar": kararlar,
        "son_karar": kararlar[0] if kararlar else None,
        "tahvil": ozet(tahvil),
        "reel": ozet(reel),
        "tahvil_serisi": [[t, v] for t, v in tahvil[-520:]],
    }


def son_guncelleme():
    with baglanti() as conn:
        satir = conn.execute(
            "SELECT zaman FROM emtia_guncelleme WHERE anahtar = 'son'"
        ).fetchone()
    return satir["zaman"][:10] if satir else None
