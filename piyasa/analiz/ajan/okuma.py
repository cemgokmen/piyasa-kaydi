"""Bir hissede bugün hangi kural ne diyor; kaynağı ve kanıtıyla."""

from piyasa.analiz.ajan import KURALLAR, Baglam
from piyasa.analiz.ajan import kanit as kanit_modulu

KANIT_ADLARI = {
    "calisiyor": ("Çalışıyor", "iyi", 1.0),
    "zayif": ("Zayıf kanıt", "orta", 0.5),
    "sans": ("Şanstan farksız", "yok", 0.0),
    "ters_zayif": ("Ters çalışıyor olabilir", "kotu", 0.0),
    "ters": ("Ters çalışıyor", "kotu", 0.0),
    "yetersiz": ("Yetersiz örnek", "yok", 0.0),
    None: ("Henüz sınanmadı", "yok", 0.0),
}


def oku(df, g, kanitlar=None):
    """
    Dönüş: {'sinyaller': [...], 'oy': kanıtla ağırlıklı net yön, 'kanitli': oy veren kural sayısı, 'toplam': kural sayısı}.
    Yalnızca kanıtı olan kural oy verir; ötekiler bilgi olarak gösterilir.
    """
    kanitlar = kanit_modulu.oku().get("kurallar") if kanitlar is None else kanitlar
    b = Baglam(df, g)
    sinyaller, oy, kanitli = [], 0.0, 0
    for k, r in KURALLAR.items():
        s = r.fonksiyon(b).iloc[-r.gecerlilik:]
        dolu = s[s != 0]
        if dolu.empty:
            continue
        yon = int(dolu.iloc[-1])
        taraf = "al" if yon > 0 else "sat"
        kn = ((kanitlar or {}).get(k) or {}).get(taraf) or {}
        ad, ton, agirlik = KANIT_ADLARI.get(kn.get("kanit"), KANIT_ADLARI[None])
        oy += yon * agirlik
        kanitli += agirlik > 0
        sinyaller.append({"kimlik": k, "ad": r.ad, "yon": yon, "tarih": dolu.index[-1].date(),
                          "metin": r.al if yon > 0 else r.sat, "kaynak": r.kaynak.atif, "sayfa": r.sayfa, "aile": r.aile,
                          "kanit": ad, "kanit_ton": ton, "agirlik": agirlik, "ufuk": r.ufuk, "ortalama": kn.get("ortalama"),
                          "yenme": kn.get("yenme"), "n": kn.get("n")})
    sinyaller.sort(key=lambda s: s["tarih"], reverse=True)
    sinyaller.sort(key=lambda s: -s["agirlik"])
    return {"sinyaller": sinyaller, "oy": oy, "kanitli": kanitli, "toplam": len(KURALLAR)}


def ozet_tablosu(kanitlar=None):
    """/analiz sayfası: bütün kurallar ve kanıtları, kaynağa göre."""
    kanitlar = kanit_modulu.oku().get("kurallar") if kanitlar is None else kanitlar
    satirlar = []
    for k, r in KURALLAR.items():
        kn = (kanitlar or {}).get(k) or {}
        satir = {"ad": r.ad, "kaynak": r.kaynak.atif, "sayfa": r.sayfa, "ufuk": r.ufuk}
        for taraf in ("al", "sat"):
            s = kn.get(taraf) or {}
            ad, ton, _ = KANIT_ADLARI.get(s.get("kanit"), KANIT_ADLARI[None])
            satir[taraf] = {"kanit": ad, "ton": ton, "ortalama": s.get("ortalama"), "sinyal": s.get("sinyal"),
                            "p": s.get("p_duzeltilmis", s.get("p"))}
        satirlar.append(satir)
    return satirlar
