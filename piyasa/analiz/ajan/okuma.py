"""Bir hissede bugün hangi kural ne diyor; kaynağı ve kanıtıyla."""

from datetime import date

from piyasa.analiz.ajan import KURALLAR, Baglam
from piyasa.analiz.ajan import kanit as kanit_modulu

KANIT_ADLARI = {
    "calisiyor": ("Çalışıyor", "iyi", 1.0),
    "zayif": ("Zayıf kanıt", "orta", 0.5),
    "maliyet": ("Maliyeti karşılamıyor", "yok", 0.0),
    "sans": ("Şanstan farksız", "yok", 0.0),
    "ters_zayif": ("Ters çalışıyor olabilir", "kotu", 0.0),
    "ters": ("Ters çalışıyor", "kotu", 0.0),
    "yetersiz": ("Yetersiz örnek", "yok", 0.0),
    None: ("Henüz sınanmadı", "yok", 0.0),
}


TEKRAR_ADLARI = {"tekrarladi": "Önceki yıllarda da görüldü", "ayni_yon": "Önceki yıllarda aynı yönde, zayıf",
                 "tekrarlamadi": "Önceki yıllarda görülmedi"}


def oku(df, g, kanitlar=None, seans_acik=False):
    """
    Dönüş: {'sinyaller': [...], 'oy': kanıtla ağırlıklı net yön, 'kanitli': oy veren kural sayısı, 'toplam': kural sayısı}.
    Yalnızca olağan dönemde kanıtı olan ve önceki yıllarda ters çıkmayan kural oy verir; ötekiler bilgi olarak gösterilir.
    seans_acik: bugünün barı kapanmadı. Bugünkü sinyal geçicidir, kapanışa kadar kaybolabilir ve oy vermez.
    """
    kanitlar = kanit_modulu.oku().get("kurallar") if kanitlar is None else kanitlar
    b = Baglam(df, g)
    sinyaller, oy, kanitli = [], 0.0, 0
    bugun = date.today()
    for k, r in KURALLAR.items():
        s = r.fonksiyon(b).iloc[-r.gecerlilik:]
        dolu = s[s != 0]
        if dolu.empty:
            continue
        yon = int(dolu.iloc[-1])
        taraf = "al" if yon > 0 else "sat"
        kn = ((kanitlar or {}).get(k) or {}).get(taraf) or {}
        ad, ton, agirlik = KANIT_ADLARI.get(kn.get("kanit"), KANIT_ADLARI[None])
        gecici = seans_acik and dolu.index[-1].date() == bugun
        if kn.get("tekrar") == "tekrarlamadi" or gecici:
            agirlik = 0.0
        oy += yon * agirlik
        kanitli += agirlik > 0
        sinyaller.append({"kimlik": k, "ad": r.ad, "yon": yon, "tarih": dolu.index[-1].date(),
                          "metin": r.al if yon > 0 else r.sat, "kaynak": r.kaynak.atif, "sayfa": r.sayfa, "aile": r.aile,
                          "kanit": ad, "kanit_ton": ton, "agirlik": agirlik, "ufuk": r.ufuk, "ortalama": kn.get("ortalama"),
                          "yenme": kn.get("yenme"), "n": kn.get("n"), "gecici": gecici,
                          "tekrar": TEKRAR_ADLARI.get(kn.get("tekrar"))})
    sinyaller.sort(key=lambda s: s["tarih"], reverse=True)
    sinyaller.sort(key=lambda s: -s["agirlik"])
    return {"sinyaller": sinyaller, "oy": oy, "kanitli": kanitli, "toplam": len(KURALLAR)}


def ozet_tablosu(kanitlar=None, donemler=None):
    """/analiz sayfası: bütün kurallar, olağan dönemdeki kanıtları ve öteki dönemlerdeki sonuçları."""
    veri = kanit_modulu.oku()
    kanitlar = veri.get("kurallar") if kanitlar is None else kanitlar
    donemler = veri.get("donemler") if donemler is None else donemler
    satirlar = []
    for k, r in KURALLAR.items():
        kn = (kanitlar or {}).get(k) or {}
        satir = {"ad": r.ad, "kaynak": r.kaynak.atif, "sayfa": r.sayfa, "ufuk": r.ufuk}
        for taraf in ("al", "sat"):
            s = kn.get(taraf) or {}
            ad, ton, _ = KANIT_ADLARI.get(s.get("kanit"), KANIT_ADLARI[None])
            satir[taraf] = {"kanit": ad, "ton": ton, "ortalama": s.get("ortalama"), "sinyal": s.get("sinyal"),
                            "p": s.get("p_duzeltilmis", s.get("p")), "tekrar": TEKRAR_ADLARI.get(s.get("tekrar")),
                            "eski": ((((donemler or {}).get("eski") or {}).get("kurallar") or {}).get(k) or {}).get(taraf, {}).get("ortalama"),
                            "sok": ((((donemler or {}).get("sok") or {}).get("kurallar") or {}).get(k) or {}).get(taraf, {}).get("ortalama")}
        satirlar.append(satir)
    return satirlar
