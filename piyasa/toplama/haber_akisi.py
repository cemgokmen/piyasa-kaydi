"""
Finans haberleri: Türkiye'nin ekonomi haber kaynaklarının RSS akışlarından son haberler.
Canlı güncelleme 30 dakikada bir çalıştırır (bkz. __main__.CANLI_GUNCELLEME).

Her haber bir konuya ayrılır (faiz, döviz ve altın, borsa, enerji, kripto, dünya, ekonomi) ve
önem puanı alır: piyasayla ilgisi, kaç kaynağın aynı haberi verdiği ve yeniliği. Aynı olayı
anlatan haberler tek kümede toplanır. Üç günden eski haberler silinir: site hep günceldir.

Haber fotoğrafları kaynakların telifli görselleridir; sitede ve paylaşım kartlarında kullanılmaz.

Çalıştırmak için:  python -m piyasa haberler
"""

import html
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import requests

from piyasa.veritabani import get_connection, init_db

TARAYICI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36"
# (ad, RSS adresi, güvenilirlik sırası: küçük olan aynı haberde öne geçer)
KAYNAKLAR = [
    ("AA", "https://www.aa.com.tr/tr/rss/default?cat=ekonomi", 1),
    ("Bloomberg HT", "https://www.bloomberght.com/rss", 2),
    ("TRT Haber", "https://www.trthaber.com/ekonomi_articles.rss", 3),
    ("Dünya", "https://www.dunya.com/rss?dunya", 4),
    ("Ekonomim", "https://www.ekonomim.com/export/rss", 5),
    ("Habertürk", "https://www.haberturk.com/rss/ekonomi.xml", 6),
    ("Investing", "https://tr.investing.com/rss/news.rss", 7),
]
SAKLAMA_GUN = 3
ARALIK = 30 * 60                # saniye: en sık 30 dakikada bir

# Konu: (anahtar, ad, kelime kökleri, piyasa önemi). Kökler sözcük başında aranır ("ons" konseri yakalamaz).
KONULAR = [
    ("faiz", "Faiz ve enflasyon", ("faiz", "merkez bankas", "tcmb", "fed", "powell", "para politika", "enflasyon",
                                   "tüfe", "üfe", "ecb", "avrupa merkez", "karahan", "tahvil"), 4),
    ("doviz", "Döviz ve altın", ("dolar/tl", "dolar kuru", "doların", "dolar endeks", "euro/tl", "avro/tl", "döviz kuru",
                                 "kur ", "kurlar", "altın", "gümüş", "ons altın", "sterlin"), 4),
    ("kripto", "Kripto", ("bitcoin", "kripto", "ethereum", "btc", "stablecoin"), 3),
    ("borsa", "Borsa", ("borsa", "bist", "hisse", "endeks", "halka arz", "temettü", "bedelsiz", "pay geri",
                        "sermaye artırım", "wall street", "nasdaq", "s&p", "dow jones"), 4),
    ("enerji", "Enerji", ("petrol", "brent", "doğal gaz", "doğalgaz", "akaryakıt", "benzin", "motorin",
                                   "elektrik", "opec"), 3),
    ("dunya", "Dünya ekonomisi", ("abd ekonomi", "çin ekonomi", "avrupa ekonomi", "gümrük vergi", "tarife", "küresel piyasa",
                                  "resesyon", "imf", "dünya bankası"), 2),
]
# Konusu olmayan haber ancak bunlardan birini içeriyorsa alınır (kaynaklar arada genel haber de veriyor)
EKONOMI = ("ekonomi", "ihracat", "ithalat", "büyüme", "istihdam", "işsizlik", "bütçe", "vergi", "şirket", "yatırım",
           "banka", "kredi", "fiyat", "zam", "maaş", "asgari ücret", "emekli", "konut", "satış", "üretim", "sanayi",
           "ticaret", "milyar", "milyon dolar", "milyon lira", "piyasa", "hazine", "cari açık", "turizm geliri", "ihale")
KONU_ADLARI = {k: ad for k, ad, _, _ in KONULAR} | {"ekonomi": "Ekonomi"}
ONEMLI = ("rekor", "son dakika", "faiz kararı", "açıklandı", "beklenti", "sert", "tarihi", "zirve", "dip", "çöktü",
          "fırladı", "yükseldi", "geriledi", "düştü")
# Her gün tekrarlanan fiyat sayfaları ("Altın bugün ne kadar?"): haber değeri düşük
SIRADAN = re.compile(r"ne kadar|kaç tl|kaç lira|güncel .*fiyat|fiyatları bugün|canlı|\d{1,2} \w+ 20\d\d", re.IGNORECASE)
GURULTU = re.compile(r"burç|\bmaç|futbol|\btff\b|teknik direktör|milli takım|süper lig|basketbol|dizi |magazin|"
                     r"horoskop|şans oyunu|loto|kupon|tutuklandı|gözaltı", re.IGNORECASE)


def _metin(oge, ad, ns=None):
    e = oge.find(ad, ns) if ns else oge.find(ad)
    return (e.text or "").strip() if e is not None and e.text else ""


def sade(metin):
    """HTML ve fazla boşlukları temizler."""
    metin = re.sub(r"<[^>]+>", " ", html.unescape(metin or ""))
    return re.sub(r"\s+", " ", metin).strip()


def kisa_ozet(metin, sinir=260):
    """İlk bir-iki cümle, en çok 'sinir' karakter."""
    metin = sade(metin)
    cumleler = re.split(r"(?<=[.!?])\s+", metin)
    ozet = ""
    for c in cumleler:
        if len(ozet) + len(c) > sinir:
            break
        ozet = f"{ozet} {c}".strip()
    if ozet or not metin:
        return ozet
    return metin[:sinir].rsplit(" ", 1)[0] + "…"


def _zaman(metin):
    """RSS tarihini UTC ISO biçimine çevirir; okunamazsa None."""
    if not metin:
        return None
    try:
        z = parsedate_to_datetime(metin)
    except (TypeError, ValueError):
        try:
            z = datetime.fromisoformat(metin.replace("Z", "+00:00"))
        except ValueError:
            return None
    if z.tzinfo is None:          # Investing saat dilimi yazmıyor: Türkiye saati
        z = z.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return z.astimezone(UTC).isoformat(timespec="seconds")


def akisi_coz(icerik, kaynak):
    """RSS → [{adres, kaynak, baslik, ozet, gorsel, yayin}]"""
    kok = ET.fromstring(icerik)
    medya = {"media": "http://search.yahoo.com/mrss/"}
    haberler = []
    for oge in kok.iter("item"):
        baslik = sade(_metin(oge, "title"))
        adres = _metin(oge, "link") or _metin(oge, "guid")
        if not baslik or not adres.startswith("http"):
            continue
        aciklama = _metin(oge, "description")
        m = oge.find("media:content", medya)
        e = oge.find("enclosure")
        gorsel = (m.get("url") if m is not None else None) or (e.get("url") if e is not None else None)
        haberler.append({"adres": adres, "kaynak": kaynak, "baslik": baslik, "ozet": kisa_ozet(aciklama),
                         "gorsel": gorsel, "yayin": _zaman(_metin(oge, "pubDate"))})
    return haberler


def _kucuk(metin):
    return metin.replace("I", "ı").replace("İ", "i").lower()


# Aynı yazılan farklı sözcükler: "altında" (aşağısında) altın değildir
_ISTISNA = {"altın": r"(?!d[ae]|ın[ae]\b|a\b|dan|den)",
            "fed": r"(?![a-zçğıöşü])",            # Federasyon, federal değil
            "bist": r"(?![a-zçğıöşü])", "btc": r"(?![a-zçğıöşü])", "imf": r"(?![a-zçğıöşü])"}


def _icerir(metin, kok):
    """Kök sözcük başında geçiyor mu ('altın' → 'altının' evet, 'ons' → 'konser' hayır, 'altında' hayır)."""
    return re.search(r"(?<![a-zçğıöşü0-9])" + re.escape(kok) + _ISTISNA.get(kok, ""), metin) is not None


def konu(baslik, ozet=""):
    """(konu anahtarı, piyasa önemi); ekonomiyle ilgisi yoksa (None, 0). Başlık özetten önceliklidir."""
    b, o = _kucuk(baslik), _kucuk(ozet)
    for metin in (b, f"{b} {o}"):
        for anahtar, _, kelimeler, onem in KONULAR:
            if any(_icerir(metin, k) for k in kelimeler):
                return anahtar, onem
    if any(_icerir(f"{b} {o}", k) for k in EKONOMI):
        return "ekonomi", 1
    return None, 0


# Her haberde geçen, olayı ayırt etmeyen sözcükler
_SIRADAN_SOZCUKLER = {"türkiye", "türkiye'nin", "milyon", "milyar", "dolar", "dolara", "doları", "yüzde", "ayda", "yılda",
                      "oldu", "geldi", "açıkladı", "ilişkin", "sonra", "önce", "kadar", "olarak", "ekim", "eylül", "bugün"}


def _kelimeler(metin):
    return {k for k in re.findall(r"[a-zçğıöşü0-9']{4,}", _kucuk(metin))} - _SIRADAN_SOZCUKLER


def benzer(a, b):
    """İki başlığın sözcük benzerliği (0–1): aynı olayın farklı kaynaklardaki haberi. En az 3 ortak sözcük gerekir."""
    ka, kb = _kelimeler(a), _kelimeler(b)
    ortak = len(ka & kb)
    return ortak / max(1, min(len(ka), len(kb))) if ortak >= 3 else 0


def puan(h, kume_buyuklugu=1, simdi=None):
    """Önem puanı: konu önemi + çarpıcı sözcükler + kaç kaynağın verdiği − eskime."""
    simdi = simdi or datetime.now(UTC)
    p = h["onem"] * 10
    if any(k in _kucuk(h["baslik"]) for k in ONEMLI):
        p += 6
    if SIRADAN.search(h["baslik"]):
        p -= 18
    p += min(kume_buyuklugu - 1, 4) * 8
    if h.get("yayin"):
        saat = (simdi - datetime.fromisoformat(h["yayin"])).total_seconds() / 3600
        p -= max(0.0, saat) * 1.2
    return round(p, 1)


def kaydet(conn, haberler):
    """Yeni haberleri ekler, kümeleri ve puanları günceller; eski haberleri siler. Eklenen sayı."""
    simdi = datetime.now(UTC)
    eklenen = 0
    for h in haberler:
        if GURULTU.search(f"{h['baslik']} {h['ozet']}"):
            continue
        h["konu"], h["onem"] = konu(h["baslik"], h["ozet"])
        if h["konu"] is None:
            continue
        yeni = conn.execute(
            """INSERT OR IGNORE INTO haber (adres, kaynak, baslik, ozet, konu, onem, gorsel, yayin, alindi)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (h["adres"], h["kaynak"], h["baslik"], h["ozet"], h["konu"], h["onem"], h["gorsel"],
             h["yayin"] or simdi.isoformat(timespec="seconds"), simdi.isoformat(timespec="seconds"))).rowcount
        eklenen += yeni
    conn.execute("DELETE FROM haber WHERE yayin < ?", ((simdi - timedelta(days=SAKLAMA_GUN)).isoformat(),))

    # Kümeler: son 36 saatin haberleri, benzer başlıklar aynı kümede (kümenin adı ilk haberin adresi)
    sira = {ad: s for ad, _, s in KAYNAKLAR}
    son = [dict(r) for r in conn.execute(
        "SELECT adres, kaynak, baslik, onem, yayin FROM haber WHERE yayin >= ? ORDER BY yayin",
        ((simdi - timedelta(hours=36)).isoformat(),))]
    kumeler = []
    for h in son:
        for k in kumeler:
            if any(benzer(h["baslik"], x["baslik"]) >= 0.6 for x in k):
                k.append(h)
                break
        else:
            kumeler.append([h])
    for k in kumeler:
        temsilci = min(k, key=lambda x: (sira.get(x["kaynak"], 9), x["yayin"]))
        kaynak_sayisi = len({x["kaynak"] for x in k})
        for h in k:
            conn.execute("UPDATE haber SET kume = ?, kaynak_sayisi = ?, puan = ? WHERE adres = ?",
                         (temsilci["adres"], kaynak_sayisi, puan(h, kaynak_sayisi, simdi), h["adres"]))
    conn.commit()
    return eklenen


def zamani_geldi_mi(conn, aralik=ARALIK):
    son = conn.execute("SELECT MAX(alindi) FROM haber").fetchone()[0]
    return not son or (datetime.now(UTC) - datetime.fromisoformat(son)).total_seconds() >= aralik - 60


def main():
    init_db()
    conn = get_connection()
    try:
        if "--zorla" not in sys.argv and not zamani_geldi_mi(conn):
            print("  Haberler 30 dakikadan yeni; atlandı.", flush=True)
            return
        toplam = []
        for ad, adres, _ in KAYNAKLAR:
            try:
                cevap = requests.get(adres, headers={"User-Agent": TARAYICI}, timeout=20)
                cevap.raise_for_status()
                liste = akisi_coz(cevap.content, ad)
                toplam += liste
            except Exception as hata:
                print(f"  {ad}: alınamadı ({str(hata)[:80]})", flush=True)
            time.sleep(0.5)
        eklenen = kaydet(conn, toplam)
        print(f"  Haberler: {len(toplam)} okundu, {eklenen} yeni", flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
