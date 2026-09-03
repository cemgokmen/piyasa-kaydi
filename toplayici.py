"""
SEC EDGAR'dan Form 4 bildirimlerini çekip veritabanına yazar.
Çalıştırmak için:  python toplayici.py
"""

import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

import requests

from database import get_connection, init_db

# SEC'in istediği kimlik. Kendi e-posta adresini yaz.
USER_AGENT = "PiyasaKaydi cemgokmen101@gmail.com"

# Kaç bildirim işlensin. Test için düşük tut.
LIMIT = 1196

# SEC saniyede en fazla 10 istek istiyor.
BEKLEME = 0.15

# P = açık piyasada alım, S = açık piyasada satış.
# A (hisse hibesi), M (opsiyon kullanımı), F (vergi kesintisi) yatırım
# kararı değil, o yüzden dışarıda bırakıyoruz.
ISLEM_KODLARI = {"P": "buy", "S": "sell"}

# Sadece adi hisse senedi alıyoruz. Tahvil, bono ve benzeri borçlanma
# araçlarında "adet" ile "fiyat" alanları hisse mantığıyla dolmuyor —
# ikisi de anapara tutarını gösterebiliyor ve çarpım anlamsız çıkıyor.
KABUL_EDILEN_MENKUL = (
    "common stock",
    "common shares",
    "ordinary shares",
    "class a common stock",
    "class b common stock",
    "common share",
)

ELENEN_KELIMELER = (
    "note", "bond", "debenture", "warrant", "option",
    "unit", "preferred", "rsu", "restricted",
)


def menkul_uygun_mu(ad):
    """Bu menkul kıymet adi hisse mi?"""
    if not ad:
        return False

    ad = ad.strip().lower()

    if any(kelime in ad for kelime in ELENEN_KELIMELER):
        return False

    return ad in KABUL_EDILEN_MENKUL


def gunluk_index_url(gun):
    ceyrek = (gun.month - 1) // 3 + 1
    return (
        f"https://www.sec.gov/Archives/edgar/daily-index/"
        f"{gun.year}/QTR{ceyrek}/form.{gun:%Y%m%d}.idx"
    )


def indir(url, deneme=4):
    """
    Adresi indirir. Ağ hatası olursa bekleyip tekrar dener.
    SEC'e uzun süreli bağlantılarda ara sıra zaman aşımı oluyor;
    tek bir aksaklık yüzünden saatlerce süren işin durmaması için.
    """
    son_hata = None

    for sira in range(deneme):
        try:
            cevap = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
            cevap.raise_for_status()
            return cevap.text
        except requests.HTTPError:
            # 404 gibi durumlarda tekrar denemenin anlamı yok
            raise
        except requests.RequestException as hata:
            son_hata = hata
            bekleme = 3 * (sira + 1)
            print(f"      ağ hatası, {bekleme} sn sonra tekrar denenecek...", flush=True)
            time.sleep(bekleme)

    raise son_hata


def son_is_gunu():
    """Bugünden geriye giderek dosyası olan ilk günü bulur."""
    gun = date.today()
    for _ in range(7):
        try:
            return gun, indir(gunluk_index_url(gun))
        except requests.HTTPError:
            gun -= timedelta(days=1)
    raise RuntimeError("Son 7 günde index dosyası bulunamadı.")


def index_satirini_coz(satir):
    """
    Şirket adında boşluk olduğu için sağdan bölüyoruz:
    son üç alan sabit, kalan her şey isim.
    """
    parcalar = satir.rsplit(None, 3)
    if len(parcalar) != 4:
        return None

    sol, cik, tarih, yol = parcalar
    sol_parcalar = sol.split(None, 1)
    if len(sol_parcalar) != 2:
        return None

    return {
        "form_type": sol_parcalar[0],
        "company": sol_parcalar[1].strip(),
        "cik": cik,
        "filed_date": f"{tarih[0:4]}-{tarih[4:6]}-{tarih[6:8]}",
        "path": yol,
    }


def isim_duzelt(ham):
    """'GRAVES JEFFREY A' -> 'Graves Jeffrey A'"""
    if not ham:
        return ""
    return " ".join(kelime.capitalize() for kelime in ham.split())

def tarih_temizle(ham):
    """
    '2026-06-12-05:00' -> '2026-06-12'
    Bazı bildirimlerde tarihe saat dilimi ekleniyor. İlk 10 karakter
    her zaman YYYY-AA-GG biçiminde, gerisini atıyoruz.
    """
    if not ham:
        return None
    ham = ham.strip()
    return ham[:10] if len(ham) >= 10 else None


def tutar_hesapla(adet, fiyat):
    if not adet or not fiyat:
        return None
    try:
        return int(round(float(adet) * float(fiyat)))
    except ValueError:
        return None


def unvan_belirle(kok):
    iliski = "reportingOwner/reportingOwnerRelationship/"
    unvan = kok.findtext(iliski + "officerTitle")
    if unvan and unvan.strip():
        return unvan.strip()
    if kok.findtext(iliski + "isDirector") == "1":
        return "Yönetim kurulu üyesi"
    if kok.findtext(iliski + "isTenPercentOwner") == "1":
        return "%10 üzeri ortak"
    return "Bildirim yükümlüsü"

def belge_url(yol):
    """
    Ham dosya yolunu, tarayıcıda açılabilen bildirim sayfasına çevirir.
    """
    parcalar = yol.strip("/").split("/")
    if len(parcalar) < 4:
        return f"https://www.sec.gov/Archives/{yol}"

    cik = parcalar[2]
    dosya_no = parcalar[3].replace(".txt", "")
    tiresiz = dosya_no.replace("-", "")

    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik}/"
        f"{tiresiz}/{dosya_no}-index.htm"
    )

def xml_ayikla(metin):
    bas = metin.find("<ownershipDocument>")
    son = metin.find("</ownershipDocument>")
    if bas == -1 or son == -1:
        return None
    return metin[bas:son + len("</ownershipDocument>")]


def bildirimi_coz(kayit):
    """Bir Form 4 dosyasını indirip içindeki alım satım işlemlerini çıkarır."""
    metin = indir(f"https://www.sec.gov/Archives/{kayit['path']}")

    xml_metni = xml_ayikla(metin)
    if xml_metni is None:
        return []

    try:
        kok = ET.fromstring(xml_metni)
    except ET.ParseError:
        return []

    sembol = (kok.findtext("issuer/issuerTradingSymbol") or "").strip()
    if not sembol:
        return []

    sirket = (kok.findtext("issuer/issuerName") or kayit["company"]).strip()
    kisi = isim_duzelt(kok.findtext("reportingOwner/reportingOwnerId/rptOwnerName"))
    unvan = unvan_belirle(kok)

    dosya_no = kayit["path"].split("/")[-1].replace(".txt", "")

    sonuclar = []
    islemler = kok.findall("nonDerivativeTable/nonDerivativeTransaction")

    for sira, islem in enumerate(islemler, start=1):
        kod = islem.findtext("transactionCoding/transactionCode")
        if kod not in ISLEM_KODLARI:
            continue

        menkul_adi = islem.findtext("securityTitle/value")
        if not menkul_uygun_mu(menkul_adi):
            continue

        tarih = tarih_temizle(islem.findtext("transactionDate/value"))
        adet = islem.findtext("transactionAmounts/transactionShares/value")
        fiyat = islem.findtext("transactionAmounts/transactionPricePerShare/value")
        tutar = tutar_hesapla(adet, fiyat)

        if not tarih or tutar is None:
            continue

        sonuclar.append({
            "source_id": f"{dosya_no}-{sira}",
            "source": "edgar_form4",
            "person": kisi,
            "chamber": None,
            "state": None,
            "party": None,
            "committee": None,
            "job_title": unvan,
            "company": sirket,
            "ticker": sembol,
            "asset_name": sirket,
            "action": ISLEM_KODLARI[kod],
            "amount_min": tutar,
            "amount_max": tutar,
            "currency": "USD",
            "transaction_date": tarih,
            "disclosed_date": kayit["filed_date"],
            "source_url": belge_url(kayit["path"]),
            "share_count": float(adet) if adet else None,
            "share_price": float(fiyat) if fiyat else None,
            "security_name": menkul_adi,
            "suspect": 0,
        })

    return sonuclar


COLUMNS = [
    "source_id", "source", "person", "chamber", "state", "party", "committee",
    "job_title", "company", "ticker", "asset_name", "action",
    "amount_min", "amount_max", "currency",
    "transaction_date", "disclosed_date", "source_url", "fetched_at",
    "share_count", "share_price", "security_name", "suspect",
]


def kaydet(conn, kayit):
    degerler = [kayit.get(sutun) for sutun in COLUMNS]
    yer_tutucu = ", ".join("?" for _ in COLUMNS)
    imlec = conn.execute(
        f"INSERT OR IGNORE INTO transactions ({', '.join(COLUMNS)}) "
        f"VALUES ({yer_tutucu})",
        degerler,
    )
    return imlec.rowcount


def main():
    init_db()

    gun, icerik = son_is_gunu()
    print(f"İndex günü: {gun}")

    satirlar = [s for s in icerik.splitlines() if s.startswith("4 ")]
    kayitlar = [index_satirini_coz(s) for s in satirlar]
    kayitlar = [k for k in kayitlar if k and k["form_type"] == "4"]

    print(f"Toplam Form 4 bildirimi: {len(kayitlar)}")
    print(f"İşlenecek: {min(LIMIT, len(kayitlar))}\n")

    conn = get_connection()
    simdi = datetime.now(timezone.utc).isoformat()

    eklenen = 0
    atlanan = 0
    hatali = 0

    for i, kayit in enumerate(kayitlar[:LIMIT], start=1):
        try:
            islemler = bildirimi_coz(kayit)
        except Exception as hata:
            hatali += 1
            print(f"  [{i}] HATA {kayit['company']}: {hata}")
            time.sleep(BEKLEME)
            continue

        if not islemler:
            atlanan += 1
        else:
            for islem in islemler:
                islem["fetched_at"] = simdi
                eklenen += kaydet(conn, islem)
            ornek = islemler[0]
            print(f"  [{i}] {ornek['ticker']:6} {ornek['person']}")

        time.sleep(BEKLEME)

    conn.commit()
    toplam = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()

    print(f"\nYeni eklenen işlem : {eklenen}")
    print(f"Alım satım içermeyen bildirim : {atlanan}")
    print(f"Hatalı : {hatali}")
    print(f"Veritabanındaki toplam kayıt : {toplam}")


if __name__ == "__main__":
    main()