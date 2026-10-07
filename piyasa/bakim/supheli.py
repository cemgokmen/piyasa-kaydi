"""
Anormal fiyatlı kayıtları bulup işaretler.

Mantık: aynı hissedeki işlemlerin fiyatları birbirine yakın olmalı.
Ortancadan 10 kat sapan bir fiyat, bildirimdeki yazım hatasına işaret eder.

Tarih hataları da işaretlenir: bildirim tarihinden sonraki ya da bildirimden
TARIH_SINIRI_GUN günden daha önceki işlem tarihi, formdaki yazım hatasıdır
(ör. 2026 yerine 2016, ya da gelecekteki bir tarih).

Bir kez veya veri her güncellendiğinde çalıştırılır.
"""

from statistics import median

from piyasa.kurallar import MUTLAK_FIYAT_TAVANI, TAVAN_ISTISNALARI
from piyasa.veritabani import get_connection

# Ortancanın kaç katı sapma şüpheli sayılsın
KAT_SINIRI = 10



# Bildirimden bu kadar gün önceki işlem tarihi yazım hatası sayılır
TARIH_SINIRI_GUN = 5 * 365

# Bir hisse için en az kaç kayıt olsun ki ortanca anlamlı olsun
ASGARI_KAYIT = 3


def main():
    conn = get_connection()

    # Önce hepsini temiz kabul et
    conn.execute("UPDATE transactions SET suspect = 0")

    tarih_hatasi = conn.execute(
        """UPDATE transactions SET suspect = 1
           WHERE transaction_date > disclosed_date
              OR julianday(disclosed_date) - julianday(transaction_date) > ?""",
        (TARIH_SINIRI_GUN,),
    ).rowcount
    print(f"Tarihi hatalı (bildirimden sonra ya da yıllar önce) kayıt: {tarih_hatasi}")

    tickerlar = [
        r["ticker"] for r in conn.execute(
            "SELECT DISTINCT ticker FROM transactions WHERE share_price IS NOT NULL"
        )
    ]

    print(f"{len(tickerlar)} hisse kontrol ediliyor...\n")

    toplam_supheli = 0

    for ticker in tickerlar:
        rows = conn.execute(
            "SELECT id, share_price FROM transactions "
            "WHERE ticker = ? AND share_price IS NOT NULL AND share_price > 0",
            (ticker,),
        ).fetchall()

        if len(rows) < ASGARI_KAYIT:
            continue

        fiyatlar = [r["share_price"] for r in rows]
        orta = median(fiyatlar)

        if orta <= 0:
            continue

        ust_sinir = orta * KAT_SINIRI
        alt_sinir = orta / KAT_SINIRI

        supheli_idler = [
            r["id"] for r in rows
            if r["share_price"] > ust_sinir or r["share_price"] < alt_sinir
        ]

        if supheli_idler:
            conn.executemany(
                "UPDATE transactions SET suspect = 1 WHERE id = ?",
                [(i,) for i in supheli_idler],
            )
            toplam_supheli += len(supheli_idler)
            print(f"{ticker:6} ortanca {orta:>12,.2f} $  ->  {len(supheli_idler)} şüpheli")


    # Ortanca hesaplanamayan hisseler için mutlak sınır kontrolü.
    # Bir hissede 3'ten az kayıt varsa karşılaştıracak veri yok;
    # bu durumda tek başına anlamsız olan fiyatları yakalıyoruz.
    yer_tutucu = ",".join("?" for _ in TAVAN_ISTISNALARI)
    tavan_supheli = conn.execute(
        f"""UPDATE transactions SET suspect = 1
            WHERE share_price > ?
              AND upper(ticker) NOT IN ({yer_tutucu})""",
        [MUTLAK_FIYAT_TAVANI] + [t.upper() for t in TAVAN_ISTISNALARI],
    ).rowcount

    print(f"\nMutlak tavanı aşan: {tavan_supheli}")
    conn.commit()

    kalan = conn.execute("SELECT COUNT(*) FROM transactions WHERE suspect = 0").fetchone()[0]
    conn.close()

    print(f"\nToplam şüpheli: {toplam_supheli}")
    print(f"Sitede gösterilecek kayıt: {kalan}")


if __name__ == "__main__":
    main()
