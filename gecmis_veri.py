"""
Geçmişe dönük SEC Form 4 verisi indirir.
Yarıda kesilirse tekrar çalıştırabilirsin: tamamlanan günleri atlar.
"""

import time
from datetime import date, datetime, timedelta, timezone

import requests

from database import get_connection, init_db
from toplayici import (
    BEKLEME,
    bildirimi_coz,
    gunluk_index_url,
    index_satirini_coz,
    indir,
    kaydet,
)

# Kaç gün geriye gidilsin (takvim günü, hafta sonları dahil sayılır)
GERIYE_GUN = 90


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

    simdi = datetime.now(timezone.utc).isoformat()
    eklenen = 0
    hatali = 0

    for i, kayit in enumerate(kayitlar, start=1):
        try:
            islemler = bildirimi_coz(kayit)
        except Exception:
            hatali += 1
            time.sleep(BEKLEME)
            continue

        for islem in islemler:
            islem["fetched_at"] = simdi
            eklenen += kaydet(conn, islem)

        if i % 100 == 0:
            conn.commit()
            print(f"      {i}/{len(kayitlar)} bildirim...", flush=True)

        time.sleep(BEKLEME)

    conn.commit()
    return {"bildirim": len(kayitlar), "eklenen": eklenen, "hatali": hatali}


def main():
    init_db()
    conn = get_connection()
    gun_tablosunu_hazirla(conn)

    bugun = date.today()
    gunler = [bugun - timedelta(days=i) for i in range(GERIYE_GUN)]
    gunler.reverse()

    print(f"Taranacak aralık: {gunler[0]} — {gunler[-1]}")
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
            print("      dosya yok (hafta sonu / tatil)")
            conn.execute(
                "INSERT OR REPLACE INTO fetched_days VALUES (?, ?, ?)",
                (gun.isoformat(), 0, datetime.now(timezone.utc).isoformat()),
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
            (gun.isoformat(), sonuc["eklenen"], datetime.now(timezone.utc).isoformat()),
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