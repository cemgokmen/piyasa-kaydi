"""
Geçmişe dönük SEC Form 4 verisi indirir.
Yarıda kesilirse tekrar çalıştırabilirsin: tamamlanan günleri atlar.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import requests

from piyasa.toplama.form4 import (
    bildirimi_coz,
    gunluk_index_url,
    index_satirini_coz,
    indir,
    kaydet,
)
from piyasa.veritabani import get_connection, init_db

# Kaç gün geriye gidilsin (takvim günü, hafta sonları dahil sayılır)
GERIYE_GUN = 90

# SEC günlük indeksi gün bittikten sonra yayımlar. Dosyası henüz olmayan
# yakın bir gün "tatil" diye işaretlenirse bir daha hiç indirilmez; bu
# yüzden dosyasız günler ancak bu kadar gün geçtikten sonra kapanır.
KESINLESME_GUN = 3

# Bildirimler paralel indirilir. SEC saniyede en fazla 10 istek istiyor;
# hız sınırlayıcı bunun altında kalır.
ESZAMANLI = 10
SANIYEDE_ISTEK = 8


class HizSiniri:
    """İş parçacıkları arasında ortak, saniyede en fazla n istek."""

    def __init__(self, saniyede):
        self.aralik = 1 / saniyede
        self.sonraki = time.monotonic()
        self.kilit = threading.Lock()

    def bekle(self):
        with self.kilit:
            simdi = time.monotonic()
            bekleme = self.sonraki - simdi
            self.sonraki = max(simdi, self.sonraki) + self.aralik
        if bekleme > 0:
            time.sleep(bekleme)


SINIR = HizSiniri(SANIYEDE_ISTEK)


def bildirimi_indir(kayit):
    """Tek bir bildirimi indirip çözer; hata olursa None döner."""
    SINIR.bekle()
    try:
        return bildirimi_coz(kayit)
    except Exception:
        return None


def gun_tablosunu_hazirla(conn):
    """Tamamlanan günleri kaydettiğimiz tablo."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fetched_days (
            gun         TEXT PRIMARY KEY,
            kayit_sayisi INTEGER,
            biten_zaman  TEXT
        )
    """)
    conn.commit()


def erken_kapanan_gunleri_ac(conn):
    """
    Eski sürüm, indeksi henüz yayımlanmamış hafta içi günleri de 0 kayıtla
    tamamlandı saydı. Bu günleri listeden çıkarır ki yeniden indirilsin.
    """
    silinen = conn.execute("""
        DELETE FROM fetched_days
        WHERE kayit_sayisi = 0
          AND strftime('%w', gun) NOT IN ('0', '6')
          AND date(substr(biten_zaman, 1, 10)) < date(gun, '+' || ? || ' days')
    """, (KESINLESME_GUN,)).rowcount
    conn.commit()
    if silinen:
        print(f"Erken kapatılmış {silinen} gün yeniden indirilecek.\n")


def gun_tamamlandi_mi(conn, gun):
    satir = conn.execute(
        "SELECT 1 FROM fetched_days WHERE gun = ?", (gun.isoformat(),)
    ).fetchone()
    return satir is not None


def gunu_isle(conn, gun):
    """Tek bir günün tüm Form 4 bildirimlerini işler."""
    try:
        icerik = indir(gunluk_index_url(gun))
    except requests.HTTPError:
        return None

    satirlar = [s for s in icerik.splitlines() if s.startswith("4 ")]
    kayitlar = [index_satirini_coz(s) for s in satirlar]
    kayitlar = [k for k in kayitlar if k and k["form_type"] == "4"]

    simdi = datetime.now(UTC).isoformat()
    eklenen = 0
    hatali = 0

    # İndirme paralel, veritabanına yazma tek iş parçacığından
    with ThreadPoolExecutor(ESZAMANLI) as havuz:
        for i, islemler in enumerate(havuz.map(bildirimi_indir, kayitlar), start=1):
            if islemler is None:
                hatali += 1
                continue

            for islem in islemler:
                islem["fetched_at"] = simdi
                eklenen += kaydet(conn, islem)

            if i % 50 == 0:
                conn.commit()
            if i % 200 == 0:
                print(f"      {i}/{len(kayitlar)} bildirim...", flush=True)

    conn.commit()
    return {"bildirim": len(kayitlar), "eklenen": eklenen, "hatali": hatali}


def main():
    init_db()
    conn = get_connection()
    gun_tablosunu_hazirla(conn)
    erken_kapanan_gunleri_ac(conn)

    bugun = date.today()
    # En yeni günler önce: yarıda kesilse bile güncel veri hazır olur
    gunler = [bugun - timedelta(days=i) for i in range(GERIYE_GUN)]

    print(f"Taranacak aralık: {gunler[-1]} — {gunler[0]} (yeniden eskiye)")
    print(f"Toplam gün: {len(gunler)}\n")

    baslangic = time.time()
    toplam_eklenen = 0

    for sira, gun in enumerate(gunler, start=1):
        if gun_tamamlandi_mi(conn, gun):
            print(f"[{sira}/{len(gunler)}] {gun}  zaten indirilmiş, atlanıyor")
            continue

        print(f"[{sira}/{len(gunler)}] {gun}  işleniyor...", flush=True)
        sonuc = gunu_isle(conn, gun)

        if sonuc is None:
            if (bugun - gun).days < KESINLESME_GUN:
                print("      dosya henüz yayımlanmamış, sonra tekrar denenecek")
                continue
            print("      dosya yok (hafta sonu / tatil)")
            conn.execute(
                "INSERT OR REPLACE INTO fetched_days VALUES (?, ?, ?)",
                (gun.isoformat(), 0, datetime.now(UTC).isoformat()),
            )
            conn.commit()
            continue

        toplam_eklenen += sonuc["eklenen"]
        print(
            f"      {sonuc['bildirim']} bildirim, "
            f"{sonuc['eklenen']} yeni işlem, "
            f"{sonuc['hatali']} hata"
        )

        conn.execute(
            "INSERT OR REPLACE INTO fetched_days VALUES (?, ?, ?)",
            (gun.isoformat(), sonuc["eklenen"], datetime.now(UTC).isoformat()),
        )
        conn.commit()

    toplam = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()

    dakika = (time.time() - baslangic) / 60
    print(f"\nBitti. Süre: {dakika:.1f} dakika")
    print(f"Bu turda eklenen: {toplam_eklenen}")
    print(f"Veritabanındaki toplam kayıt: {toplam}")


if __name__ == "__main__":
    main()
