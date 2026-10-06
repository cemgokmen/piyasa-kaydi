"""
ABD Temsilciler Meclisi üyelerinin hisse işlemlerini (STOCK Act
"Periodic Transaction Report" bildirimleri) çekip veritabanına yazar.

Kaynak: House Clerk — https://disclosures-clerk.house.gov
  - Yıllık bildirim listesi: financial-pdfs/<yıl>FD.zip (XML)
  - Her bildirim bir PDF: ptr-pdfs/<yıl>/<DocID>.pdf

Elektronik doldurulan PDF'ler metin içerir ve sütun konumlarıyla
ayrıştırılır. Elle doldurulup taranmış bildirimler (DocID 8 veya 9 ile
başlar) resimdir; onlar atlanır.

Parti bilgisi PDF'te yok; açık "congress-legislators" veri setinden
eyalet + seçim bölgesiyle eşleştirilir. Aynı veri setindeki resmî tam ad,
House Clerk listesindeki hatalı yazımların yerine kullanılır
(ör. listede ad alanı "Scott Scott" olarak geçiyor).

Çalıştırmak için:  python kongre_toplayici.py [yıl ...]
Tekrar çalıştırılabilir: işlenmiş bildirimleri atlar.
"""

import io
import re
import sys
import time
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

import pdfplumber
import requests

from ayarlar import USER_AGENT
from database import get_connection, init_db
from slug import slugify
from toplayici import kaydet

KAYNAK = "house_ptr"
LISTE_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{yil}FD.zip"
PDF_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{yil}/{doc}.pdf"
UYELER_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"

BEKLEME = 0.3

ISLEM_TURLERI = {"P": "buy", "S": "sell"}   # E (değişim) yatırım kararı değil

# Yalnızca hisse senetleri. Varlık türü kodları:
# https://fd.house.gov/reference/asset-type-codes.aspx
KABUL_EDILEN_TURLER = {"ST"}

PARTI_KISA = {"Democrat": "D", "Republican": "R", "Independent": "I"}

TARIH = re.compile(r"^\d{2}/\d{2}/\d{4}$")
TICKER = re.compile(r"\(([A-Z][A-Z0-9.\-]{0,7})\)")
VARLIK_TURU = re.compile(r"\[([A-Z]{2})\]")
TUTAR = re.compile(r"\$([\d,]+)")


def indir(url):
    cevap = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    cevap.raise_for_status()
    return cevap.content


# ---------------------------------------------------------------------------
# BİLDİRİM LİSTESİ VE ÜYELER
# ---------------------------------------------------------------------------

def bildirim_listesi(yil):
    """Yılın işlem bildirimlerini (FilingType = P) döndürür."""
    zf = zipfile.ZipFile(io.BytesIO(indir(LISTE_URL.format(yil=yil))))
    kok = ET.fromstring(zf.read(f"{yil}FD.xml"))

    liste = []
    for m in kok:
        if m.findtext("FilingType") != "P":
            continue
        ad = " ".join(
            p for p in (m.findtext("First"), m.findtext("Last"), m.findtext("Suffix")) if p
        )
        soyad = m.findtext("Last") or ""
        ay, gun, yil_ = m.findtext("FilingDate").split("/")
        liste.append({
            "doc": m.findtext("DocID"),
            "yil": yil,
            "ad": ad,
            "soyad": soyad,
            "bolge": m.findtext("StateDst") or "",
            "tarih": f"{yil_}-{int(ay):02d}-{int(gun):02d}",
        })
    return liste


def uye_bilgileri():
    """
    'IL01' -> {'parti': 'D', 'ad': 'Jonathan L. Jackson', 'soyad': 'Jackson'}
    (Temsilciler Meclisi'nin güncel üyeleri)
    """
    try:
        uyeler = requests.get(UYELER_URL, timeout=60).json()
    except Exception as hata:
        print(f"Parti bilgisi alınamadı ({hata}); parti boş kalacak.")
        return {}

    eslesme = {}
    for u in uyeler:
        t = u["terms"][-1]
        if t["type"] != "rep":
            continue
        bolge = f"{t['state']}{int(t.get('district') or 0):02d}"
        eslesme[bolge] = {
            "parti": PARTI_KISA.get(t.get("party"), (t.get("party") or "")[:1]),
            "ad": u["name"].get("official_full"),
            "soyad": u["name"].get("last", ""),
        }
    return eslesme


def sade(metin):
    """'Sánchez' -> 'sanchez': aksanlı ve aksansız yazımlar eşleşsin."""
    ayrik = unicodedata.normalize("NFKD", metin or "")
    return "".join(c for c in ayrik if not unicodedata.combining(c)).lower()


def uye_bul(bildirim, uyeler):
    """
    Bildirimi veren kişiyi güncel üye listesinde bulur. Bölge el değiştirmiş
    olabileceği için soyadı da tutmalı; tutmazsa None döner.
    """
    soyad = sade(bildirim["soyad"])
    if not soyad:
        return None

    def tutar_mi(uye):
        # 'Delaney' ile 'McClain Delaney' gibi birleşik soyadları da eşleşsin
        return sade(uye["soyad"]) in soyad or soyad in sade(uye["soyad"])

    uye = uyeler.get(bildirim["bolge"])
    if uye and tutar_mi(uye):
        return uye

    # Seçim bölgesi değişmiş olabilir: soyadı tek bir üyeye aitse onu al
    adaylar = [u for u in uyeler.values() if sade(u["soyad"]) == soyad]
    return adaylar[0] if len(adaylar) == 1 else None


# ---------------------------------------------------------------------------
# PDF AYRIŞTIRMA
# ---------------------------------------------------------------------------

def satirlara_bol(kelimeler, tolerans=3):
    """Kelimeleri dikey konumlarına göre satırlara toplar."""
    satirlar = []
    for k in sorted(kelimeler, key=lambda k: (round(k["top"]), k["x0"])):
        if satirlar and abs(satirlar[-1]["top"] - k["top"]) <= tolerans:
            satirlar[-1]["kelimeler"].append(k)
        else:
            satirlar.append({"top": k["top"], "kelimeler": [k]})
    for s in satirlar:
        s["kelimeler"].sort(key=lambda k: k["x0"])
    return satirlar


def sutunlari_bul(satirlar):
    """Başlık satırından sütunların x başlangıçlarını çıkarır."""
    for s in satirlar:
        metin = [k["text"] for k in s["kelimeler"]]
        if "Asset" in metin and "Amount" in metin and "Notification" in metin:
            x = {k["text"]: k["x0"] for k in s["kelimeler"]}
            return {
                "owner": x.get("Owner", 60),
                "asset": x["Asset"],
                "tur": x.get("Transaction", x["Asset"] + 150),
                "tarih": x["Date"],
                "bildirim": x["Notification"],
                "tutar": x["Amount"],
                "cap": x.get("Cap.", x["Amount"] + 75),
            }
    return None


def baslik_satiri_mi(satir):
    """Her sayfanın tepesinde tekrarlanan sütun başlığı satırları."""
    metin = {k["text"] for k in satir["kelimeler"]}
    return (
        {"Asset", "Amount", "Notification"} <= metin
        or {"Type", "Gains"} <= metin
        or metin == {"$200?"}
    )


def sutunda(k, bas, son):
    return bas - 4 <= k["x0"] < son - 4


def etiket_satiri_mi(satir, sutun):
    """'Filing Status: New' gibi alt satırlar PDF'te bozuk karakterlerle gelir."""
    ilk = [k for k in satir["kelimeler"] if k["x0"] >= sutun["asset"] - 4]
    return bool(ilk) and "\x00" in ilk[0]["text"]


def tutar_coz(metin):
    """'$1,001 - $15,000' -> (1001, 15000); 'Over $50,000,000' -> (50000000, 50000000)"""
    sayilar = [int(s.replace(",", "")) for s in TUTAR.findall(metin)]
    if not sayilar:
        return None, None
    return sayilar[0], sayilar[-1]


def pdf_ayristir(icerik):
    """PDF'teki işlem satırlarını sözlük listesi olarak döndürür."""
    # Bir işlem sayfa sonunda bölünüp devamı sonraki sayfanın başına
    # geçebiliyor. Bu yüzden tüm sayfaların satırları tek listede toplanır,
    # her sayfada tekrarlanan sütun başlığı atılır.
    satirlar = []
    sutun = None
    with pdfplumber.open(io.BytesIO(icerik)) as pdf:
        for no, sayfa in enumerate(pdf.pages):
            sayfa_satirlari = satirlara_bol(sayfa.extract_words())
            sutun = sutun or sutunlari_bul(sayfa_satirlari)
            for s in sayfa_satirlari:
                if not baslik_satiri_mi(s):
                    s["top"] += no * 10_000
                    satirlar.append(s)

    if sutun is None:
        return []

    # Çapa satırı: işlem tarihi ve bildirim tarihi sütunlarında tarih var
    capalar = [
        i for i, s in enumerate(satirlar)
        if any(sutunda(k, sutun["tarih"], sutun["bildirim"]) and TARIH.match(k["text"])
               for k in s["kelimeler"])
        and any(sutunda(k, sutun["bildirim"], sutun["tutar"]) and TARIH.match(k["text"])
                for k in s["kelimeler"])
    ]

    islemler = []
    for n, i in enumerate(capalar):
        son = capalar[n + 1] if n + 1 < len(capalar) else len(satirlar)
        blok = [satirlar[i]]
        for s in satirlar[i + 1:son]:
            if etiket_satiri_mi(s, sutun):
                break
            blok.append(s)

        def topla(bas, bit):
            return " ".join(
                k["text"] for s in blok for k in s["kelimeler"] if sutunda(k, bas, bit)
            ).strip()

        capa = satirlar[i]["kelimeler"]
        islemler.append({
            "sahip": " ".join(k["text"] for k in capa
                              if sutunda(k, sutun["owner"], sutun["asset"])),
            "varlik": topla(sutun["asset"], sutun["tur"]),
            "tur": topla(sutun["tur"], sutun["tarih"]),
            "islem_tarihi": next(k["text"] for k in capa
                                 if sutunda(k, sutun["tarih"], sutun["bildirim"])),
            "tutar": topla(sutun["tutar"], sutun["cap"]),
        })
    return islemler


def iso_tarih(abd):
    ay, gun, yil = abd.split("/")
    return f"{yil}-{ay}-{gun}"


def kayitlara_cevir(bildirim, satirlar, uyeler):
    """Ayrıştırılan satırları transactions tablosunun biçimine çevirir."""
    uye = uye_bul(bildirim, uyeler)
    ad = (uye and uye["ad"]) or bildirim["ad"]

    kayitlar = []
    for sira, s in enumerate(satirlar):
        tur = VARLIK_TURU.search(s["varlik"])
        tickerlar = TICKER.findall(s["varlik"])
        islem = ISLEM_TURLERI.get(s["tur"][:1])
        if not tur or tur.group(1) not in KABUL_EDILEN_TURLER or not tickerlar or not islem:
            continue

        alt, ust = tutar_coz(s["tutar"])
        varlik_adi = VARLIK_TURU.sub("", TICKER.sub("", s["varlik"])).strip(" -")
        bolge = bildirim["bolge"]

        kayitlar.append({
            "source_id": f"house-{bildirim['doc']}-{sira}",
            "source": KAYNAK,
            "person": ad,
            "person_slug": slugify(ad),
            "chamber": "Temsilciler Meclisi",
            "state": f"{bolge[:2]}-{bolge[2:]}" if len(bolge) > 2 else bolge,
            "party": uye and uye["parti"],
            "job_title": "Temsilciler Meclisi üyesi",
            "ticker": tickerlar[-1].replace(".", "-"),
            "asset_name": varlik_adi,
            "company": varlik_adi,
            "action": islem,
            "amount_min": alt,
            "amount_max": ust,
            "currency": "USD",
            "transaction_date": iso_tarih(s["islem_tarihi"]),
            "disclosed_date": bildirim["tarih"],
            "source_url": PDF_URL.format(yil=bildirim["yil"], doc=bildirim["doc"]),
            "security_name": "Hisse senedi" + (f" ({s['sahip']})" if s["sahip"] else ""),
        })
    return kayitlar


# ---------------------------------------------------------------------------
# ANA AKIŞ
# ---------------------------------------------------------------------------

def islenmis_bildirimler(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kongre_bildirimleri (
            doc          TEXT PRIMARY KEY,
            kayit_sayisi INTEGER,
            durum        TEXT,
            biten_zaman  TEXT
        )
    """)
    conn.commit()
    return {r["doc"] for r in conn.execute("SELECT doc FROM kongre_bildirimleri")}


def main():
    yillar = [int(y) for y in sys.argv[1:]] or [date.today().year]

    init_db()
    conn = get_connection()
    islenmis = islenmis_bildirimler(conn)
    uyeler = uye_bilgileri()

    toplam_eklenen = 0
    for yil in yillar:
        liste = bildirim_listesi(yil)
        yeni = [b for b in liste if b["doc"] not in islenmis]
        print(f"{yil}: {len(liste)} işlem bildirimi, {len(yeni)} tanesi yeni.\n")

        for n, b in enumerate(yeni, start=1):
            simdi = datetime.now(timezone.utc).isoformat()

            if b["doc"][:1] in ("8", "9"):
                durum, eklenen = "taranmis", 0
            else:
                try:
                    satirlar = pdf_ayristir(indir(PDF_URL.format(yil=yil, doc=b["doc"])))
                    kayitlar = kayitlara_cevir(b, satirlar, uyeler)
                    eklenen = 0
                    for k in kayitlar:
                        k["fetched_at"] = simdi
                        eklenen += kaydet(conn, k)
                    durum = "tamam"
                except requests.HTTPError as hata:
                    print(f"  {b['doc']} indirilemedi: {hata}")
                    continue
                except Exception as hata:
                    print(f"  {b['doc']} ayrıştırılamadı: {hata}")
                    durum, eklenen = "hata", 0
                time.sleep(BEKLEME)

            conn.execute(
                "INSERT OR REPLACE INTO kongre_bildirimleri VALUES (?, ?, ?, ?)",
                (b["doc"], eklenen, durum, simdi),
            )
            conn.commit()
            toplam_eklenen += eklenen

            if eklenen:
                print(f"  [{n}/{len(yeni)}] {b['tarih']}  {b['ad']:28} {eklenen} işlem")

    toplam = conn.execute(
        "SELECT COUNT(*) FROM transactions WHERE source = ?", (KAYNAK,)
    ).fetchone()[0]
    conn.close()
    print(f"\nBu turda eklenen: {toplam_eklenen}")
    print(f"Veritabanındaki Meclis işlemi: {toplam}")


if __name__ == "__main__":
    main()
