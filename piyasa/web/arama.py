"""
Arama önerileri: arama kutusuna yazılırken altta açılan liste.

Hisseler, siyasetçiler, şirket yöneticileri, fonlar ve emtialardan oluşan
bir dizin bellekte tutulur (10 dakikada bir yenilenir). Eşleşme büyük/küçük
harf ve Türkçe karakterlerden bağımsızdır: "sandisk", "SanDisk", "altin",
"altın" hepsi bulunur.
"""

import html
import math
import re
import unicodedata
from collections import Counter, defaultdict
from contextlib import closing

from piyasa.bicim import sirket_gorunen_ad, unvan
from piyasa.emtia.tanimlar import EMTIALAR
from piyasa.kurallar import GECERLI_KOD, TEMIZ, parti_bilgisi
from piyasa.onbellek import sureli
from piyasa.uyeler import YURUTME
from piyasa.veritabani import get_connection

ONBELLEK_SURESI = 10 * 60
EN_FAZLA = 8

# Emtialar için ek arama sözcükleri
EMTIA_ESANLAMLILARI = {
    "altin": "gold ons gram altin xau",
    "gumus": "silver ons xag",
    "platin": "platinum",
    "bakir": "copper",
    "brent": "oil petrol ham petrol akaryakit",
}

TUR_SIRASI = {"Hisse": 0, "Emtia": 1, "Siyasetçi": 2, "Yönetici": 3, "Fon": 4}


def sade(metin):
    """Karşılaştırma için: küçük harf, aksansız, Türkçe harfler Latin karşılığıyla."""
    metin = (metin or "").replace("ı", "i").replace("İ", "i")
    metin = unicodedata.normalize("NFKD", metin)
    metin = "".join(c for c in metin if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", metin).strip()


def sirket_adi_temizle(ad):
    """'Sandisk Corporation - Common Stock' → 'Sandisk Corporation'"""
    ad = html.unescape(re.sub(r"&amp(?!;)", "&", ad or ""))
    ad = re.sub(r"\s+", " ", ad).strip()
    ad = re.sub(r"\s+-\s+.*$", "", ad)
    ad = re.sub(r"\s+(common stock|ordinary shares|class [a-c] .*)$", "", ad, flags=re.IGNORECASE)
    return ad.strip(" ,.-")


def _guzel_ad(adlar):
    """Bir hissenin farklı yazımlarından en okunaklısını seçer."""
    sayac = Counter(sirket_adi_temizle(a) for a in adlar if a)
    if not sayac:
        return ""
    # Büyük-küçük harf karışık yazım, tamamı büyük harf olandan daha okunaklıdır
    karisik = [a for a, _ in sayac.most_common() if not a.isupper()]
    secilen = karisik[0] if karisik else sayac.most_common(1)[0][0].title()
    return secilen


def _dizin_kur():
    girdiler = []
    with closing(get_connection()) as conn:
        hisse_adlari = defaultdict(list)
        hisse_sayisi = Counter()
        for s in conn.execute(
            f"""SELECT ticker, asset_name, COUNT(*) AS n FROM transactions
               WHERE {TEMIZ} AND {GECERLI_KOD}
               GROUP BY ticker, asset_name"""
        ):
            hisse_adlari[s["ticker"]] += [s["asset_name"]] * min(s["n"], 50)
            hisse_sayisi[s["ticker"]] += s["n"]
        for s in conn.execute(
            "SELECT ticker, sirket_adi, COUNT(*) AS n FROM holdings WHERE ticker IS NOT NULL GROUP BY ticker, sirket_adi"
        ):
            hisse_adlari[s["ticker"]] += [s["sirket_adi"]] * min(s["n"], 50)
            hisse_sayisi[s["ticker"]] += s["n"]

        for ticker, adlar in hisse_adlari.items():
            ad = _guzel_ad(adlar)
            girdiler.append({
                "tur": "Hisse", "etiket": ticker, "alt": ad,
                "adres": f"/hisse/{ticker}", "kod": sade(ticker), "metin": sade(ad),
                "agirlik": hisse_sayisi[ticker],
            })

        for s in conn.execute(
            f"""SELECT person_slug, MAX(person) AS ad, MAX(chamber) AS meclis, MAX(party) AS parti,
                      MAX(state) AS bolge, MAX(job_title) AS unvan, MAX(company) AS sirket, COUNT(*) AS n
               FROM transactions WHERE {TEMIZ} AND person_slug IS NOT NULL
               GROUP BY person_slug"""
        ):
            if s["meclis"]:
                p = parti_bilgisi(s["parti"])
                alt = " · ".join(x for x in ((p or {}).get("ad"), s["meclis"], s["bolge"]) if x)
                tur = "Siyasetçi"
            else:
                alt = " · ".join(x for x in (unvan(s["unvan"]), sirket_gorunen_ad(s["sirket"]) if s["sirket"] else None) if x)
                tur = "Yönetici"
            girdiler.append({
                "tur": tur, "etiket": s["ad"], "alt": alt, "adres": f"/kisi/{s['person_slug']}",
                "kod": "", "metin": sade(s["ad"]), "agirlik": s["n"],
            })

        for s in conn.execute("SELECT fon_slug, MAX(fon_adi) AS ad, COUNT(*) AS n FROM holdings GROUP BY fon_slug"):
            girdiler.append({
                "tur": "Fon", "etiket": s["ad"], "alt": "Fon / banka portföyü", "adres": f"/fon/{s['fon_slug']}",
                "kod": "", "metin": sade(s["ad"]), "agirlik": s["n"],
            })

    for y in YURUTME:
        girdiler.append({
            "tur": "Siyasetçi", "etiket": y["ad"], "alt": f"{y['gorev']} · mali durum bildirimleri", "one_cikar": True,
            "adres": f"/yurutme/{y['slug']}", "kod": "", "metin": sade(y["ad"]), "agirlik": 5_000,
        })

    for e in EMTIALAR:
        girdiler.append({
            "tur": "Emtia", "etiket": e["ad"], "alt": f"{e['grup']} · {e['birim']}",
            "adres": f"/emtia/{e['slug']}", "kod": "",
            "metin": sade(f"{e['ad']} {EMTIA_ESANLAMLILARI.get(e['slug'], '')}"), "agirlik": 10_000,
        })
    return girdiler


@sureli(ONBELLEK_SURESI)
def dizin():
    return _dizin_kur()


def onbellegi_temizle():
    dizin.temizle()


def _puan(girdi, aranan):
    """Eşleşmenin gücü; eşleşme yoksa 0."""
    kod, metin = girdi["kod"], girdi["metin"]
    if kod and kod == aranan:
        taban = 1000
    elif kod and kod.startswith(aranan):
        taban = 700
    elif metin.startswith(aranan):
        taban = 600
    elif f" {aranan}" in f" {metin}":          # bir sözcüğün başında
        taban = 450
    elif len(aranan) >= 3 and aranan in metin:
        taban = 250
    else:
        return 0
    # Sitenin kendi emtia sayfaları "altın", "gold", "petrol" aramalarında öne çıksın
    if girdi["tur"] == "Emtia" or girdi.get("one_cikar"):
        taban += 200
    # Çok işlem görenler öne; kısa adlar (tam eşleşmeye yakın) biraz önde
    return taban + 25 * math.log10(1 + girdi["agirlik"]) - min(len(metin), 60) * 0.3


def oneriler(sorgu, en_fazla=EN_FAZLA):
    aranan = sade(sorgu)
    if not aranan:
        return []
    puanli = [(p, g) for g in dizin() if (p := _puan(g, aranan)) > 0]
    puanli.sort(key=lambda x: (-x[0], TUR_SIRASI[x[1]["tur"]]))
    return [
        {k: g[k] for k in ("tur", "etiket", "alt", "adres")}
        for _, g in puanli[:en_fazla]
    ]
