"""
Kamuyu Aydınlatma Platformu (KAP): Borsa İstanbul şirketlerinin bildirimleri.

  - BIST 100 ve BIST 30 bileşenleri: KAP "Endeksler" sayfası
  - Bildirim listesi: KAP sitesinin kendi kullandığı liste servisi (tarih aralığına göre)
  - Toplanan bildirimler:
      Pay Alım Satım Bildirimi            içeriden ve büyük ortak işlemleri (bütün BIST şirketleri)
      Payların Geri Alınmasına İlişkin…   şirketin kendi payını geri alması (bütün BIST şirketleri)
      Özel Durum Açıklaması (Genel)       yalnızca başlık ve özet (BIST 100 şirketleri)
  - Pay alım satım ve geri alım bildirimlerinin ayrıntısı bildirim sayfasından okunur:
    açıklama metni SPK'nın standart cümlesiyle yazılır ("… tarihinde X payları ile ilgili
    olarak … TL fiyattan … nominal tutarlı alış işlemi Y tarafınca gerçekleştirilmiştir"),
    geri alımlar ise tabloyla verilir.

KAP'ı yormamak için istekler arasında beklenir. Her kayıtta KAP bildirimine bağlantı vardır.

Çalıştırmak için:
  python -m piyasa kap               son 7 günün bildirimleri ve ayrıntıları
  python -m piyasa kap --gun 90      geçmişe dönük doldurma
  python -m piyasa kap --canli --gun 1   gün içi (şirket listesini yeniden indirmez)
"""

import html
import io
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
import zipfile
from datetime import UTC, date, datetime, timedelta

import pdfplumber
import requests

from piyasa.bicim import tr_baslik
from piyasa.veritabani import get_connection, init_db

SITE = "https://www.kap.org.tr"
LISTE_URL = SITE + "/tr/api/disclosure/list/main"
BILDIRIM_URL = SITE + "/tr/Bildirim/{indeks}"
ENDEKS_URL = SITE + "/tr/Endeksler"
SIRKETLER_URL = SITE + "/tr/bist-sirketler"
SEKTORLER_URL = SITE + "/tr/api/company/sectors/excel"
# KAP sıradan program isteklerini geri çeviriyor; tarayıcı gibi görünmek gerekiyor
BASLIK = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/140.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
}
BEKLEME = 3            # saniye, bildirim sayfaları arasında (KAP sık isteği engelliyor)
PENCERE = 7            # liste servisi gün aralığı

TURLER = {
    "Pay Alım Satım Bildirimi": "pay",
    "Payların Geri Alınmasına İlişkin Bildirim": "geri_alim",
    "Özel Durum Açıklaması (Genel)": "ozel",
}


def _istek(yontem, adres, deneme=4, **kw):
    """KAP isteği; istek sınırına (429) takılınca bir dakika bekleyip yeniden dener."""
    basliklar = {**BASLIK, **kw.pop("headers", {})}
    for sira in range(deneme):
        try:
            cevap = requests.request(yontem, adres, headers=basliklar, timeout=60, **kw)
            if cevap.status_code == 429:
                print("  KAP istek sınırı: 2 dk bekleniyor", flush=True)
                time.sleep(120)
                continue
            cevap.raise_for_status()
            return cevap
        except requests.RequestException:
            if sira == deneme - 1:
                raise
            time.sleep(5 * (sira + 1))
    raise requests.HTTPError(f"KAP istek sınırı aşıldı: {adres}")


# ---------------------------------------------------------------------------
# ENDEKSLER
# ---------------------------------------------------------------------------

def endeks_bilesenleri(sayfa, kod):
    """Endeksler sayfasındaki gömülü veriden bir endeksin şirketleri: [{stockCode, title, mkkMemberOid}]."""
    metin = sayfa.replace('\\"', '"')
    m = re.search(r'\{"code":"' + kod + r'","content":(\[.*?\])', metin)
    return json.loads(m.group(1)) if m else []


def bist_sirketleri(sayfa):
    """BIST Şirketleri sayfasındaki gömülü liste: [{kod, unvan, sehir}]; çok kodlu şirketlerde her kod ayrı."""
    metin = sayfa.replace('\\"', '"')
    sirketler = []
    for m in re.finditer(r'\{"mkkMemberOid":"([^"]+)","kapMemberTitle":"([^"]+)"[^{}]*?"stockCode":"([^"]*)"'
                         r'(?:,"cityName":"([^"]*)")?', metin):
        oid, unvan, kodlar, sehir = m.groups()
        for kod in (k.strip() for k in kodlar.split(",")):
            if kod:
                sirketler.append({"kod": kod, "unvan": unvan, "sehir": sehir, "oid": oid})
    return sirketler


def xlsx_satirlari(icerik):
    """Basit bir .xlsx dosyasının ilk sayfası: [[hücre, ...], ...] (ek paket gerektirmez)."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    z = zipfile.ZipFile(io.BytesIO(icerik))
    ortak = ["".join(t.text or "" for t in si.iter(ns + "t"))
             for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(ns + "si")]
    satirlar = []
    for satir in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(ns + "row"):
        hucreler = []
        for c in satir.findall(ns + "c"):
            v = c.find(ns + "v")
            deger = v.text if v is not None else ""
            hucreler.append(ortak[int(deger)] if c.get("t") == "s" else deger)
        satirlar.append(hucreler)
    return satirlar


def sektor_eslemesi(satirlar):
    """
    KAP sektör listesi: başlık satırı (sektör adı), ardından 'Sıra, Kod, Unvan' satırları.
    Ana sektörlerin listesi alt sektörlerininkini kapsar. Dönen: {kod: (ana sektör, alt sektör)}.
    """
    bolumler, ad = [], None
    for h in satirlar:
        if len(h) == 1 and h[0] and h[0] != "Kayıt Bulunamadı":
            ad = h[0].strip()
            bolumler.append((ad, set()))
        elif len(h) >= 3 and ad and h[1] and h[1] != "Kod":
            for kod in h[1].split(","):
                bolumler[-1][1].add(kod.strip())
    bolumler = [(a, k) for a, k in bolumler if k and a != "DİĞER"]
    sonuc, ana = {}, None
    for i, (ad, kodlar) in enumerate(bolumler):
        sonraki = bolumler[i + 1][1] if i + 1 < len(bolumler) else set()
        # Bir başlık, ardındaki başlığın şirketlerini kapsıyorsa ana sektördür
        if ana is None or not kodlar <= ana[1] or (sonraki and sonraki <= kodlar and kodlar != sonraki):
            if ana is None or not kodlar <= ana[1]:
                ana = (ad, kodlar)
                for k in kodlar:
                    sonuc.setdefault(k, [ad, None])
                    sonuc[k][0] = ad
                continue
        for k in kodlar:
            sonuc.setdefault(k, [ana[0], None])
            if sonuc[k][1] is None or len(kodlar) < len(dict(bolumler).get(sonuc[k][1], kodlar) or kodlar):
                sonuc[k][1] = ad
    return {k: (a, alt) for k, (a, alt) in sonuc.items()}


def sektorleri_guncelle(conn):
    try:
        esleme = sektor_eslemesi(xlsx_satirlari(_istek("GET", SEKTORLER_URL).content))
    except (requests.RequestException, zipfile.BadZipFile, KeyError, ET.ParseError) as hata:
        print(f"  Sektörler alınamadı: {hata}", flush=True)
        return
    for kod, (ana, alt) in esleme.items():
        conn.execute("UPDATE bist_sirket SET ana_sektor = ?, sektor = ? WHERE kod = ?", (ana, alt or ana, kod))
    conn.commit()
    print(f"  Sektör bilgisi: {len(esleme)} şirket", flush=True)


def endeksleri_guncelle(conn):
    sayfa = _istek("GET", ENDEKS_URL).text
    xu100 = endeks_bilesenleri(sayfa, "XU100")
    xu030 = {s["stockCode"] for s in endeks_bilesenleri(sayfa, "XU030")}
    if len(xu100) < 90:                       # sayfa yapısı değiştiyse eski listeyi silme
        raise RuntimeError(f"BIST 100 listesi okunamadı ({len(xu100)} şirket)")
    simdi = datetime.now(UTC).isoformat()
    # Bütün BIST şirketleri (unvan ve şehir); endeks bayrakları aşağıda
    try:
        tum = bist_sirketleri(_istek("GET", SIRKETLER_URL).text)
    except requests.RequestException:
        tum = []
    for s in tum:
        conn.execute(
            """INSERT INTO bist_sirket (kod, unvan, mkk_oid, sehir, guncelleme) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(kod) DO UPDATE SET unvan = excluded.unvan, mkk_oid = excluded.mkk_oid,
                 sehir = excluded.sehir, guncelleme = excluded.guncelleme""",
            (s["kod"], s["unvan"], s["oid"], s["sehir"], datetime.now(UTC).isoformat()),
        )
    conn.execute("UPDATE bist_sirket SET xu100 = 0, xu030 = 0")
    for s in xu100:
        conn.execute(
            """INSERT INTO bist_sirket (kod, unvan, mkk_oid, xu100, xu030, guncelleme) VALUES (?, ?, ?, 1, ?, ?)
               ON CONFLICT(kod) DO UPDATE SET unvan = excluded.unvan, mkk_oid = excluded.mkk_oid,
                 xu100 = 1, xu030 = excluded.xu030, guncelleme = excluded.guncelleme""",
            (s["stockCode"], s["title"], s["mkkMemberOid"], int(s["stockCode"] in xu030), simdi),
        )
    conn.commit()
    print(f"  BIST şirketi: {len(tum)}, BIST 100: {len(xu100)}, BIST 30: {len(xu030)}", flush=True)
    sektorleri_guncelle(conn)
    return {s["stockCode"] for s in xu100}


# ---------------------------------------------------------------------------
# BİLDİRİM LİSTESİ
# ---------------------------------------------------------------------------

def bildirim_listesi(bas, bit):
    cevap = _istek("POST", LISTE_URL, json={
        "fromDate": f"{bas:%d.%m.%Y}", "toDate": f"{bit:%d.%m.%Y}",
        "disclosureTypes": None, "memberTypes": ["IGS"], "mkkMemberOid": None,
    }, headers={"Accept": "application/json"})
    return [x["disclosureBasic"] for x in cevap.json()]


def ilgili_kod(b):
    """Bildirimin ilgili olduğu şirket: portföy şirketlerinin ve KAP'ın aktardığı bildirimlerde ilgili şirket."""
    ilgili = [k.strip() for k in (b.get("relatedStocks") or "").split(",") if k.strip()]
    gonderen = b.get("stockCode")
    if ilgili and (not gonderen or "PORTFÖY" in (b.get("companyTitle") or "").upper()
                   or "EMEKLİLİK" in (b.get("companyTitle") or "").upper()):
        return ilgili[0]
    return (gonderen or (ilgili[0] if ilgili else None) or "").split(",")[0].strip() or None


def _yayin(tarih):
    """'08.10.2026 18:46:07' -> '2026-10-08 18:46:07'"""
    try:
        return datetime.strptime(tarih, "%d.%m.%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return tarih


def listeyi_kaydet(conn, bildirimler, bist100):
    eklenen = 0
    for b in bildirimler:
        tur = TURLER.get((b.get("title") or "").strip())
        if not tur:
            continue
        kod = ilgili_kod(b)
        if tur == "ozel" and kod not in bist100:
            continue
        eklenen += conn.execute(
            """INSERT OR IGNORE INTO kap_bildirim (indeks, kod, gonderen, baslik, ozet, yayin, tur)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (b["disclosureIndex"], kod, b.get("companyTitle"), b.get("title"),
             (b.get("summary") or "").strip() or None, _yayin(b.get("publishDate")), tur),
        ).rowcount
    conn.commit()
    return eklenen


# ---------------------------------------------------------------------------
# BİLDİRİM AYRINTISI
# ---------------------------------------------------------------------------

def _coz(sayfa):
    """Bildirim içeriği sayfada kaçışlı (\\u003c) HTML olarak gömülü."""
    return (sayfa.replace("\\u003c", "<").replace("\\u003e", ">").replace("\\u0026", "&")
            .replace('\\"', '"'))


def _duz(parca):
    parca = re.sub(r"<br\s*/?>|</div>|</p>", "\n", parca)
    metin = html.unescape(re.sub(r"<[^>]+>", " ", parca))
    return re.sub(r"[ \t\xa0]+", " ", re.sub(r"\s*\n\s*", "\n", metin)).strip()


def aciklama_metni(sayfa):
    """Bildirimin Türkçe açıklama metni (pay alım satım) ya da özet bilgi metni."""
    s = _coz(sayfa)
    m = re.search(r'oda_ExplanationTextBlock\|</div>.*?content-tr"[^>]*>(.*?)</td>', s, re.S)
    if m:
        return _duz(m.group(1))
    # Eski biçim ve KAP'ın aktardığı bildirimler: "Açıklamalar" başlığından sonrası
    duz = _duz(re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S))
    m = re.search(r"(?:Açıklamalar|Ek Açıklamalar)\s+(.*?)(?:Yukarıdaki açıklamalarımızın|Bildirimlerin MKK tarafından|$)",
                  duz, re.S)
    return m.group(1).strip()[:3000] if m else None


def _sayi(metin):
    """'1.250.000' -> 1250000.0; '19,23' -> 19.23"""
    if metin is None:
        return None
    try:
        return float(metin.replace(".", "").replace(",", "."))
    except ValueError:
        return None


TARIH = r"(\d{1,2}[./]\d{1,2}[./]\d{4})"
SAYI = r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
SPK_CUMLESI = re.compile(
    TARIH + r"\s+tarihinde\s+(.+?)\s+payları\s+ile\s+ilgili\s+olarak\s+(.*?)\s*" + SAYI
    + r"\s*(?:TL\s+)?(?:toplam\s+)?nominal\s+tutarlı\s+(alış|alım|satış|satım)\s+işlemi\s+(.+?)\s+"
      r"(?:tarafı(?:nca|ndan|mızca)\s+)?gerçekleştiril",
    re.S | re.IGNORECASE,
)
FIYAT_ARALIGI = re.compile(SAYI + r"\s*(?:TL)?\s*[-–]\s*" + SAYI + r"\s*TL")
FIYAT_TEK = re.compile(SAYI + r"\s*TL")
ORAN = re.compile(r"%\s*" + SAYI + r"|" + SAYI + r"\s*%")
# "ortaklığımızca", "şirketimizce", "tarafımızca" gibi gönderenin kendisini anlatan sözcükler
KENDISI = re.compile(r"^(ortaklığ|şirket|taraf|kurum)\w*(ca|ce|ımızca|imizce|ımca|imce)$"
                     r"|^(ortaklığımız|şirketimiz|tarafımız|tarafım)$", re.I)
OZET_EKI = re.compile(r"\s*['’]?(?:nin|nın|nun|nün|in|ın|un|ün)?\s*pay\s+(?:alım|satım|alış|satış)(?:\s*/?\s*(?:satım|satış))?\s+"
                      r"(?:bildirimi|işlemi|işlemleri).*$", re.I)
KAP_AKTARIM = re.compile(r"kapsamında\s+(.+?)\s+tarafından\s+Kuruluşumuza\s+gönderilen", re.S)


def _tarih(metin):
    gun, ay, yil = re.split(r"[./]", metin)
    return f"{yil}-{int(ay):02d}-{int(gun):02d}"


def _kisi_turu(kisi, metin):
    if re.search(r"kurucusu olduğu(?:muz)? (?:yatırım )?fonlar", metin, re.I):
        return "fon"
    if re.search(r"\b(A\.?Ş\.?|Ltd|Limited|Şirketi|Holding|Portföy|Bankası|Fonu|Vakfı|Inc|LLC|GmbH|S\.A\.|"
                 r"Corporation|Corp|Group|Bank|Fund|N\.V\.|B\.V\.|PLC|Trust|Capital|Partners|Yatırım|Sanayi|Ticaret)\b",
                 kisi, re.I):
        return "sirket"
    return "kisi"


def ozetten_kisi(ozet):
    """'Gülermak Emlak Yapı İnşaat Yatırım A.Ş. pay alım bildirimi' -> 'Gülermak Emlak Yapı İnşaat Yatırım A.Ş.'"""
    if not ozet:
        return None
    kisi = OZET_EKI.sub("", ozet.strip())
    return kisi if kisi and kisi != ozet.strip() and len(kisi) > 3 else None


def pay_islemi_coz(metin, gonderen=None, ozet=None):
    """
    Açıklama metninden işlem bilgisi. SPK cümlesi bulunamazsa ve bildirim KAP'ın aktardığı
    bir bildirimse yalnızca kişi döner (ayrıntı ekteki belgede).
    """
    if not metin:
        return None
    duz = " ".join(metin.split())
    m = SPK_CUMLESI.search(duz)
    if m:
        tarih, _sirket, fiyat_metni, nominal, yon, kisi = m.groups()
        kisi = re.sub(r"\s+(?:tarafı(?:nca|ndan))$", "", kisi.strip(" ,."))
        fon = re.search(r"kurucusu olduğu(?:muz)? (?:yatırım )?fonlar", kisi, re.I)
        if fon:
            kisi = gonderen or kisi
        elif KENDISI.match(kisi):
            # Şirket, ortağının bildirimini kendi ağzından aktarmış: işlemi yapan özetteki ad
            kisi = ozetten_kisi(ozet) or gonderen or kisi
        fiyat_alt = fiyat_ust = None
        if (a := FIYAT_ARALIGI.search(fiyat_metni)):
            fiyat_alt, fiyat_ust = _sayi(a.group(1)), _sayi(a.group(2))
        elif (t := FIYAT_TEK.search(fiyat_metni)):
            fiyat_alt = fiyat_ust = _sayi(t.group(1))
        ortalama = re.search(r"ortalama\s+" + SAYI + r"\s*TL", fiyat_metni)
        fiyat = (_sayi(ortalama.group(1)) if ortalama
                 else (fiyat_alt + fiyat_ust) / 2 if fiyat_alt and fiyat_ust else None)
        # İşlemden sonraki pay oranı: cümleden sonraki ilk yüzde
        sonrasi = duz[m.end():m.end() + 600]
        o = ORAN.search(sonrasi)
        oran = _sayi(o.group(1) or o.group(2)) if o else None
        nominal_sayi = _sayi(nominal)
        return {
            "kisi": kisi[:200], "kisi_turu": "fon" if fon else _kisi_turu(kisi, duz),
            "islem": "buy" if yon.lower() in ("alış", "alım") else "sell",
            "islem_tarihi": _tarih(tarih), "nominal": nominal_sayi,
            "fiyat": fiyat, "fiyat_alt": fiyat_alt, "fiyat_ust": fiyat_ust,
            "tutar": nominal_sayi * fiyat if nominal_sayi and fiyat else None,
            "oran_sonra": oran if oran is not None and oran <= 100 else None,
        }
    bos = {"islem": None, "islem_tarihi": None, "nominal": None, "fiyat": None, "fiyat_alt": None,
           "fiyat_ust": None, "tutar": None, "oran_sonra": None}
    a = KAP_AKTARIM.search(duz)
    if a:
        kisi = a.group(1).strip(" ,.")
        return {"kisi": kisi[:200], "kisi_turu": _kisi_turu(kisi, duz), **bos}
    # Portföy ve emeklilik şirketlerinin fon eşiği bildirimleri: işlemi yapan gönderenin fonları
    if gonderen and re.search(r"PORTFÖY|EMEKLİLİK", gonderen, re.I):
        return {"kisi": gonderen, "kisi_turu": "fon", **bos}
    return None


# MKK'nın aktardığı bildirimlerin ekindeki standart form (PDF)
EK_ADRESI = re.compile(r"/tr/api/file/download/([A-Za-z0-9]+)")
FORM_ALANI = re.compile(r"^(Ad Soyad / Ticaret Ünvanı|Görevi|Bildirime Konu Borsa Şirketi)[ \t]*:[ \t]*(.*)$", re.M)
FORM_SATIRI = re.compile(r"^(\d{2}/\d{2}/\d{4})\s+((?:-?[\d.,]+\s+){8,}-?[\d.,]+)\s*$", re.M)


def ek_metni(sayfa):
    """Bildirimin ilk ekini (PDF) indirip metnini döndürür; yoksa None."""
    m = EK_ADRESI.search(_coz(sayfa))
    if not m:
        return None
    icerik = _istek("GET", f"{SITE}/tr/api/file/download/{m.group(1)}").content
    bas = icerik.find(b"%PDF")              # dosyanın başında birkaç baytlık sarmalayıcı var
    if bas < 0:
        return None
    try:
        with pdfplumber.open(io.BytesIO(icerik[bas:])) as pdf:
            return "\n".join((s.extract_text() or "") for s in pdf.pages[:3])
    except Exception:
        return None


def form_coz(metin, gonderen=None):
    """MKK formu: kişi ve görevi alanlardan, işlem SPK cümlesinden ya da günlük işlem tablosundan."""
    if not metin:
        return None
    alanlar = {a: d.strip() for a, d in FORM_ALANI.findall(metin)}
    kisi = tr_baslik(alanlar.get("Ad Soyad / Ticaret Ünvanı") or "") or None
    gorev = alanlar.get("Görevi") or None
    if gorev and (len(gorev) < 2 or gorev.startswith("Varsa")):
        gorev = None
    bilgi = pay_islemi_coz(metin, kisi or gonderen)
    satirlar = []
    for tarih, sayilar in FORM_SATIRI.findall(metin):
        s = [_sayi(x) for x in sayilar.split()]
        satirlar.append({"tarih": _tarih(tarih), "alim": s[0], "satim": s[1], "net": s[2], "oran_sonra": s[-2]})
    if satirlar:
        alim, satim = sum(x["alim"] or 0 for x in satirlar), sum(x["satim"] or 0 for x in satirlar)
        tablo = {"islem": "buy" if alim >= satim else "sell", "nominal": abs(alim - satim) or max(alim, satim),
                 "islem_tarihi": satirlar[-1]["tarih"], "oran_sonra": satirlar[-1]["oran_sonra"]}
        if not bilgi or not bilgi.get("islem"):
            bilgi = {"kisi": kisi or gonderen, "kisi_turu": _kisi_turu(kisi or "", metin), "fiyat": None,
                     "fiyat_alt": None, "fiyat_ust": None, "tutar": None, **tablo}
        else:
            bilgi["oran_sonra"] = tablo["oran_sonra"] if tablo["oran_sonra"] is not None else bilgi["oran_sonra"]
    if not bilgi:
        return None
    # Alımdan sonra pay oranı sıfır olamaz: formda oran boş bırakılmış
    if bilgi.get("islem") == "buy" and not bilgi.get("oran_sonra"):
        bilgi["oran_sonra"] = None
    if kisi:
        bilgi["kisi"] = kisi
        bilgi["kisi_turu"] = _kisi_turu(kisi, metin) if bilgi["kisi_turu"] != "fon" else "fon"
    bilgi["gorev"] = gorev
    return bilgi


def ilgili_sirketler(sayfa):
    """Bildirim sayfasındaki "İlgili Şirketler" alanı (fon kodları hariç): ['LOGO']"""
    duz = _duz(_coz(sayfa))
    m = re.search(r"İlgili Şirketler\s*(?:Related Companies)?\s*\[?([A-Z0-9][A-Z0-9, ]*?)\]?\s*(?:İlgili Fonlar|Related|Açıklamalar|\n)", duz)
    return [k.strip() for k in m.group(1).split(",") if k.strip()] if m else []


def geri_alim_tablosu(sayfa):
    """Geri alım bildirimindeki işlem tablosu: [{islem_tarihi, nominal, oran, fiyat}]."""
    s = _coz(sayfa)
    satirlar = []
    for tablo in re.findall(r"<table[^>]*>(.*?)</table>", s, re.S):
        if "İşlem Tarihi" not in tablo or "İşlem Fiyatı" not in tablo:
            continue
        hucre_satirlari = [[_duz(h) for h in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
                           for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tablo, re.S)]
        if not hucre_satirlari:
            continue
        baslik = hucre_satirlari[0]
        try:
            i_tarih = next(i for i, b in enumerate(baslik) if b.startswith("İşlem Tarihi"))
            i_nominal = next(i for i, b in enumerate(baslik) if "Nominal" in b and "Daha Önce" not in b)
            i_fiyat = next(i for i, b in enumerate(baslik) if b.startswith("İşlem Fiyatı"))
            i_oran = next((i for i, b in enumerate(baslik) if b.startswith("Sermayeye Oranı")), None)
        except StopIteration:
            continue
        for h in hucre_satirlari[1:]:
            if len(h) <= max(i_tarih, i_nominal, i_fiyat) or not re.match(TARIH, h[i_tarih]):
                continue
            nominal, fiyat = _sayi(h[i_nominal]), _sayi(h[i_fiyat])
            if not nominal or not fiyat:
                continue
            satirlar.append({"islem_tarihi": _tarih(re.match(TARIH, h[i_tarih]).group(1)), "nominal": nominal,
                             "fiyat": fiyat, "oran": _sayi(h[i_oran]) if i_oran is not None and i_oran < len(h) else None})
    return satirlar


def ek_metni_kisa(bilgi):
    if not bilgi.get("islem"):
        return None
    return f"(Ekteki formdan: {bilgi['kisi']}{', ' + bilgi['gorev'] if bilgi.get('gorev') else ''})"


def ayrintilari_al(conn, en_fazla=800, bist100=frozenset()):
    """Ayrıntısı alınmamış pay alım satım ve geri alım bildirimleri (yeniden eskiye)."""
    # Geri alım bildirimleri programın bütün işlemlerini içerir: her şirketin yalnızca en
    # son bildirimini okumak yeter, eskileri okunmuş sayılır
    conn.execute(
        """UPDATE kap_bildirim SET detay_alindi = 1
           WHERE tur = 'geri_alim' AND detay_alindi = 0 AND indeks < (
               SELECT MAX(k.indeks) FROM kap_bildirim k WHERE k.tur = 'geri_alim' AND k.kod = kap_bildirim.kod)""")
    conn.commit()
    bekleyen = conn.execute(
        """SELECT indeks, kod, gonderen, ozet, tur FROM kap_bildirim
           WHERE tur IN ('pay', 'geri_alim') AND detay_alindi = 0 ORDER BY yayin DESC LIMIT ?""",
        (en_fazla,),
    ).fetchall()
    print(f"  Ayrıntısı alınacak bildirim: {len(bekleyen)}", flush=True)
    islem = geri = 0
    for n, b in enumerate(bekleyen, 1):
        try:
            sayfa = _istek("GET", BILDIRIM_URL.format(indeks=b["indeks"])).text
        except requests.RequestException as hata:
            print(f"  {b['indeks']} alınamadı: {hata}", flush=True)
            time.sleep(BEKLEME * 3)
            continue
        metin = aciklama_metni(sayfa)
        # Liste servisi şirket ve fon kodlarını karıştırabiliyor; sayfadaki "İlgili Şirketler" esas
        kod = b["kod"]
        ilgili = ilgili_sirketler(sayfa)
        if ilgili:
            # Birden çok kod varsa (KRDMA, KRDMB, KRDMD) BIST 100'deki öne alınır
            secilen = next((k for k in ilgili if k in bist100), kod if kod in ilgili else ilgili[0])
            if secilen != kod:
                kod = secilen
            conn.execute("UPDATE kap_bildirim SET kod = ? WHERE indeks = ?", (kod, b["indeks"]))
        if b["tur"] == "pay":
            bilgi = pay_islemi_coz(metin, b["gonderen"], b["ozet"])
            # MKK'nın aktardığı bildirimlerde ayrıntı ekteki formda
            if not bilgi or not bilgi.get("islem"):
                try:
                    form = form_coz(ek_metni(sayfa), b["gonderen"])
                except requests.RequestException:
                    form = None
                if form:
                    bilgi = form
                    metin = (metin or "") + "\n\n" + (ek_metni_kisa(form) or "")
            if bilgi:
                bilgi.setdefault("gorev", None)
                conn.execute(
                    """INSERT OR REPLACE INTO kap_pay_islem (indeks, kod, kisi, kisi_turu, islem, islem_tarihi,
                         nominal, fiyat, fiyat_alt, fiyat_ust, tutar, oran_sonra, gorev)
                       VALUES (:indeks, :kod, :kisi, :kisi_turu, :islem, :islem_tarihi, :nominal, :fiyat,
                               :fiyat_alt, :fiyat_ust, :tutar, :oran_sonra, :gorev)""",
                    {"indeks": b["indeks"], "kod": kod, **bilgi},
                )
                islem += 1
        else:
            for s in geri_alim_tablosu(sayfa):
                geri += conn.execute(
                    "INSERT OR IGNORE INTO kap_geri_alim (kod, islem_tarihi, nominal, oran, fiyat, indeks) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (kod, s["islem_tarihi"], s["nominal"], s["oran"], s["fiyat"], b["indeks"]),
                ).rowcount
        conn.execute("UPDATE kap_bildirim SET metin = ?, detay_alindi = 1 WHERE indeks = ?",
                     ((metin or "")[:4000] or None, b["indeks"]))
        conn.commit()
        if n % 100 == 0:
            print(f"  {n}/{len(bekleyen)}", flush=True)
        time.sleep(BEKLEME)
    print(f"  Çözülen pay işlemi: {islem}, yeni geri alım satırı: {geri}", flush=True)


# ---------------------------------------------------------------------------
# ŞİRKET GENEL BİLGİ FORMU: ortaklık yapısı, halka açıklık, yönetim
# ---------------------------------------------------------------------------

GENEL_BILGI_URL = SITE + "/tr/sirket-bilgileri/genel/{oid}"
RSC_PARCASI = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')


def rsc_metni(sayfa):
    """Next.js sayfasına gömülü veri parçalarını birleştirir (kaçışlar çözülmüş haliyle)."""
    return "".join(json.loads(p) for p in RSC_PARCASI.findall(sayfa))


def form_kalemi(rsc, anahtar):
    """Genel bilgi formundaki bir kalemin değeri (liste ya da metin); yoksa None."""
    i = rsc.find(f'"itemKey":"{anahtar}"')
    if i < 0:
        return None
    j = rsc.find('"value":', i)
    if j < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(rsc, j + len('"value":'))[0]
    except ValueError:
        return None


def genel_bilgi_coz(sayfa):
    rsc = rsc_metni(sayfa)
    ortaklar = []
    for o in form_kalemi(rsc, "kpy41_acc5_sermayede_dogrudan") or []:
        ad = (o.get("shareholder") or "").strip()
        if not ad or ad.upper() in ("TOPLAM", "DİĞER", "DIĞER", "DİĞER ORTAKLAR", "HALKA AÇIK"):
            continue
        ortaklar.append({"ortak": ad, "oran": _sayi(o.get("ratioInCapital")),
                         "oy_orani": _sayi(o.get("votingRightRatio")), "tutar": _sayi(o.get("shareInCapital"))})
    fiili = form_kalemi(rsc, "kpy41_acc5_fiili_dolasimdaki_pay") or []
    halka = _sayi(fiili[0].get("actualOutstandingSharesRatio")) if fiili and isinstance(fiili, list) else None
    tescil = form_kalemi(rsc, "kpy41_acc4_tescil_tarihi")
    yil = re.search(r"(\d{4})", tescil or "")
    yonetim = [{"ad": (y.get("nameSurname") or "").strip(),
                "gorev": ((y.get("title") or {}).get("text") or "").strip()}
               for y in form_kalemi(rsc, "kpy41_acc6_yonetim_kurulu_uyeleri") or [] if y.get("nameSurname")]
    bagli = [{"ad": (b.get("companyTitle") or "").strip(), "faaliyet": (b.get("scopeOfActivitiesOfCompany") or "").strip(),
              "oran": _sayi(b.get("ratioOfCapitalShareOfCompany"))}
             for b in form_kalemi(rsc, "kpy41_acc7_bagli_ortakliklar") or [] if b.get("companyTitle")]
    site = form_kalemi(rsc, "kpy41_acc1_int_addres")
    tarih = re.search(r'"itemKey":"kpy41_acc5_sermayede_dogrudan".*?"creationDate":"([^"]+)"', rsc)
    return {
        "ortaklar": ortaklar, "halka_aciklik": halka,
        "odenmis_sermaye": _sayi(form_kalemi(rsc, "kpy41_acc5_odenmis_sermaye")) if isinstance(
            form_kalemi(rsc, "kpy41_acc5_odenmis_sermaye"), str) else None,
        "tescil_yili": int(yil.group(1)) if yil else None,
        "site": (site.split("/")[0].strip() if isinstance(site, str) and site.strip() else None),
        "yonetim": yonetim, "bagli": bagli[:40], "tarih": tarih.group(1) if tarih else None,
    }


def sirket_bilgileri_guncelle(conn, en_fazla=150, yas_gun=7):
    """
    Genel bilgi formu eski (ya da hiç alınmamış) şirketler, BIST 100 önce. KAP'ı yormamak
    için her çalıştırmada en fazla 'en_fazla' şirket.
    """
    from piyasa.slug import slugify

    sinir = (datetime.now(UTC) - timedelta(days=yas_gun)).isoformat()
    sirketler = conn.execute(
        """SELECT s.kod, s.mkk_oid FROM bist_sirket s LEFT JOIN bist_profil p ON p.kod = s.kod
           WHERE (s.ana_sektor IS NOT NULL OR s.xu100 = 1) AND s.mkk_oid IS NOT NULL
             AND (p.guncelleme IS NULL OR p.guncelleme < ?)
           ORDER BY s.xu100 DESC, p.guncelleme IS NOT NULL, s.kod LIMIT ?""",
        (sinir, en_fazla),
    ).fetchall()
    # Aynı şirketin birden çok kodu (KRDMA, KRDMB, KRDMD) tek sayfadan
    sayfalar = {}
    for n, s in enumerate(sirketler, 1):
        try:
            if s["mkk_oid"] not in sayfalar:
                sayfalar[s["mkk_oid"]] = genel_bilgi_coz(_istek("GET", GENEL_BILGI_URL.format(oid=s["mkk_oid"])).text)
                time.sleep(BEKLEME)
            b = sayfalar[s["mkk_oid"]]
        except (requests.RequestException, ValueError) as hata:
            print(f"  {s['kod']} genel bilgi alınamadı: {hata}", flush=True)
            continue
        conn.execute("DELETE FROM bist_ortak WHERE kod = ?", (s["kod"],))
        for o in b["ortaklar"]:
            conn.execute("INSERT OR REPLACE INTO bist_ortak VALUES (?, ?, ?, ?, ?, ?)",
                         (s["kod"], o["ortak"], slugify(o["ortak"]), o["oran"], o["oy_orani"], o["tutar"]))
        conn.execute(
            """INSERT OR REPLACE INTO bist_profil (kod, halka_aciklik, odenmis_sermaye, tescil_yili, site, yonetim,
                 bagli, tarih, guncelleme) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (s["kod"], b["halka_aciklik"], b["odenmis_sermaye"], b["tescil_yili"], b["site"],
             json.dumps(b["yonetim"], ensure_ascii=False), json.dumps(b["bagli"], ensure_ascii=False), b["tarih"],
             datetime.now(UTC).isoformat()),
        )
        conn.commit()
        if n % 50 == 0:
            print(f"  Genel bilgi: {n}/{len(sirketler)}", flush=True)
    print(f"  Şirket genel bilgisi güncellendi: {len(sirketler)}", flush=True)


# ---------------------------------------------------------------------------
# ANA AKIŞ
# ---------------------------------------------------------------------------

def main():
    argumanlar = sys.argv[1:]
    gun = int(argumanlar[argumanlar.index("--gun") + 1]) if "--gun" in argumanlar else 7
    en_fazla = int(argumanlar[argumanlar.index("--en-fazla") + 1]) if "--en-fazla" in argumanlar else 800
    if "--genel" in argumanlar:            # yalnızca şirket genel bilgileri (ortaklık yapısı)
        init_db()
        conn = get_connection()
        try:
            sirket_bilgileri_guncelle(conn, en_fazla=en_fazla)
        finally:
            conn.close()
        return
    init_db()
    conn = get_connection()
    try:
        if "--canli" in argumanlar:       # 15 dakikalık çalıştırma: şirket listesi veritabanından
            bist100 = {r[0] for r in conn.execute("SELECT kod FROM bist_sirket WHERE xu100 = 1")}
        else:
            bist100 = endeksleri_guncelle(conn)
        bit = date.today()
        eklenen = 0
        while gun > 0:
            bas = bit - timedelta(days=min(gun, PENCERE) - 1)
            eklenen += listeyi_kaydet(conn, bildirim_listesi(bas, bit), bist100)
            gun -= PENCERE
            bit = bas - timedelta(days=1)
            time.sleep(BEKLEME)
        print(f"  Yeni KAP bildirimi: {eklenen}", flush=True)
        ayrintilari_al(conn, en_fazla, bist100)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
