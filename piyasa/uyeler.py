"""
Siyasetçiler hakkında ek bilgi: resmi fotoğraf, liderlik görevi ve
"önemli siyasetçiler" listesi.

Fotoğraflar, kamu malı olan resmi Kongre portrelerinin congress-legislators
projesindeki kopyalarıdır.
"""

from contextlib import closing

from piyasa.analiz.sektorler import KOMITE_ADLARI
from piyasa.bicim import kisa_aralik
from piyasa.kurallar import parti_bilgisi
from piyasa.onbellek import sureli
from piyasa.veritabani import get_connection

FOTO = "https://unitedstates.github.io/images/congress/225x275/{}.jpg"

GOREVLER = {
    "Speaker of the House": "Temsilciler Meclisi Başkanı",
    "House Majority Leader": "Çoğunluk lideri",
    "House Minority Leader": "Azınlık lideri",
    "House Majority Whip": "Çoğunluk grup başkanvekili",
    "House Minority Whip": "Azınlık grup başkanvekili",
    "Assistant House Minority Leader": "Azınlık lider yardımcısı",
    "House Republican Conference Chair": "Cumhuriyetçi grup başkanı",
    "House Republican Policy Committee Chair": "Cumhuriyetçi politika komitesi başkanı",
    "House Democratic Caucus Chair": "Demokrat grup başkanı",
    "House Democratic Caucus Vice Chair": "Demokrat grup başkan yardımcısı",
}

# Liderlik görevi olmasa da kamuoyunda işlemleri çok takip edilen üyeler
TANINMIS = {
    "nancy-pelosi": "Eski Temsilciler Meclisi Başkanı; işlemleri en çok takip edilen üye",
    "marjorie-taylor-greene": "Cumhuriyetçi; sık hisse işlemi bildiren üyelerden",
    "josh-gottheimer": "Demokrat; en çok işlem bildiren üyelerden",
    "dan-crenshaw": "Cumhuriyetçi; İstihbarat ve Enerji komitelerinde",
}

# Yürütme: Başkan ve Başkan Yardımcısı (OGE bildirimleri)
YURUTME = [
    {"slug": "donald-j-trump", "ad": "Donald J. Trump", "gorev": "ABD Başkanı", "parti": "R",
     # Resmi Başkanlık portresi (kamu malı), Wikimedia Commons
     "foto": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/16/Official_Presidential_Portrait_of_President_Donald_J._Trump_%282025%29.jpg/250px-Official_Presidential_Portrait_of_President_Donald_J._Trump_%282025%29.jpg"},
    {"slug": "jd-vance", "ad": "JD Vance", "gorev": "ABD Başkan Yardımcısı", "parti": "R",
     "foto": FOTO.format("V000137")},
]
YURUTME_SLUG = {y["slug"]: y for y in YURUTME}


@sureli(10 * 60)
def _uyeler():
    with closing(get_connection()) as conn:
        return {s["slug"]: dict(s) for s in conn.execute("SELECT * FROM uye")}


@sureli(10 * 60)
def _baskanliklar():
    """{bioguide: ['Yargı Komitesi', ...]} — ana komite başkanlıkları."""
    sonuc = {}
    with closing(get_connection()) as conn:
        for s in conn.execute("SELECT bioguide, komite FROM komite_uyeligi WHERE unvan IN ('Chair', 'Chairman')"):
            if s["komite"] in KOMITE_ADLARI:
                sonuc.setdefault(s["bioguide"], []).append(KOMITE_ADLARI[s["komite"]])
    return sonuc


def onbellegi_temizle():
    _uyeler.temizle()
    _baskanliklar.temizle()


def foto(slug):
    """Üyenin resmi fotoğrafının adresi; bilinmiyorsa None."""
    uye = _uyeler().get(slug)
    return FOTO.format(uye["bioguide"]) if uye else None


def gorev(slug):
    """Türkçe görev: liderlik ya da komite başkanlığı; yoksa None."""
    uye = _uyeler().get(slug)
    if not uye:
        return None
    if uye.get("gorev"):
        return GOREVLER.get(uye["gorev"], uye["gorev"])
    baskanliklar = _baskanliklar().get(uye["bioguide"])
    return f"{baskanliklar[0]} başkanı" if baskanliklar else None


def fotolu(kayitlar, slug_alani="slug"):
    """Liste öğelerine 'foto' alanı ekler."""
    for k in kayitlar:
        k["foto"] = foto(k.get(slug_alani))
    return kayitlar


def onemli_siyasetciler():
    """
    Önce liderler, sonra tanınmış üyeler, sonra komite başkanları — yalnızca
    işlem bildirmiş olanlar.
    """
    uyeler = _uyeler()
    baskanliklar = _baskanliklar()
    with closing(get_connection()) as conn:
        islemler = {s["person_slug"]: dict(s) for s in conn.execute(
            """SELECT person_slug, MAX(person) AS ad, MAX(party) AS parti, MAX(state) AS bolge,
                      COUNT(*) AS adet, SUM(amount_min) AS alt, SUM(amount_max) AS ust,
                      MAX(disclosed_date) AS son
               FROM transactions WHERE chamber IS NOT NULL GROUP BY person_slug"""
        )}

    def kart(slug, aciklama, oncelik):
        i = islemler[slug]
        return {"slug": slug, "ad": i["ad"], "parti": parti_bilgisi(i["parti"]), "bolge": i["bolge"],
                "aciklama": aciklama, "adet": i["adet"], "hacim": kisa_aralik(i["alt"], i["ust"]),
                "son": i["son"], "foto": foto(slug), "oncelik": oncelik}

    kartlar = {}
    for slug, uye in uyeler.items():
        if slug in islemler and uye.get("gorev"):
            kartlar[slug] = kart(slug, GOREVLER.get(uye["gorev"], uye["gorev"]), 0)
    for slug, aciklama in TANINMIS.items():
        if slug in islemler and slug not in kartlar:
            kartlar[slug] = kart(slug, aciklama, 1)
    for slug, uye in uyeler.items():
        if slug in islemler and slug not in kartlar and uye["bioguide"] in baskanliklar:
            kartlar[slug] = kart(slug, f"{baskanliklar[uye['bioguide']][0]} başkanı", 2)

    return sorted(kartlar.values(), key=lambda k: (k["oncelik"], -k["adet"]))


def yurutme_bildirimleri(slug):
    with closing(get_connection()) as conn:
        return [dict(s) for s in conn.execute(
            "SELECT * FROM yurutme_bildirimi WHERE kisi = ? ORDER BY tarih DESC", (slug,)
        )]
