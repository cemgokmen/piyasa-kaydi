"""
transactions tablosuna person_slug sütunu ekler ve doldurur.
Bir kez çalıştırılır.
"""

from database import get_connection
from slug import slugify


def main():
    conn = get_connection()

    sutunlar = [s["name"] for s in conn.execute("PRAGMA table_info(transactions)")]
    if "person_slug" not in sutunlar:
        conn.execute("ALTER TABLE transactions ADD COLUMN person_slug TEXT")
        print("person_slug sütunu eklendi.")
    else:
        print("person_slug sütunu zaten var.")

    kisiler = conn.execute(
        "SELECT DISTINCT person FROM transactions WHERE person IS NOT NULL"
    ).fetchall()

    print(f"{len(kisiler)} farklı kişi bulundu, adresler üretiliyor...")

    for satir in kisiler:
        conn.execute(
            "UPDATE transactions SET person_slug = ? WHERE person = ?",
            (slugify(satir["person"]), satir["person"]),
        )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_person_slug ON transactions(person_slug)"
    )
    conn.commit()
    conn.close()
    print("Bitti.")


if __name__ == "__main__":
    main()