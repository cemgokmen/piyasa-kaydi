"""
transactions tablosuna ham veri sütunlarını ekler.
Bir kez çalıştırılır.
"""

from database import get_connection

YENI_SUTUNLAR = [
    ("share_count", "REAL"),      # işlem gören adet
    ("share_price", "REAL"),      # birim fiyat
    ("security_name", "TEXT"),    # menkul kıymetin adı
    ("suspect", "INTEGER"),       # 1 ise şüpheli, sitede gösterilmez
]


def main():
    conn = get_connection()

    mevcut = [s["name"] for s in conn.execute("PRAGMA table_info(transactions)")]

    for ad, tur in YENI_SUTUNLAR:
        if ad in mevcut:
            print(f"{ad} zaten var, atlandı.")
        else:
            conn.execute(f"ALTER TABLE transactions ADD COLUMN {ad} {tur}")
            print(f"{ad} eklendi.")

    conn.commit()
    conn.close()
    print("Bitti.")


if __name__ == "__main__":
    main()