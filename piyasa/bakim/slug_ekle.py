"""
transactions tablosundaki person_slug sütununu doldurur.
Yeni kayıtlarda toplayici.py bunu kendisi dolduruyor; bu dosya eski
kayıtlar için.
Bir kez çalıştırılır.
"""

from piyasa.slug import slugify
from piyasa.veritabani import get_connection, init_db


def main():
    init_db()  # person_slug sütunu ve indeksi yoksa ekler
    conn = get_connection()

    kisiler = conn.execute(
        "SELECT DISTINCT person FROM transactions WHERE person IS NOT NULL"
    ).fetchall()

    print(f"{len(kisiler)} farklı kişi bulundu, adresler üretiliyor...")

    for satir in kisiler:
        conn.execute(
            "UPDATE transactions SET person_slug = ? WHERE person = ?",
            (slugify(satir["person"]), satir["person"]),
        )

    conn.commit()
    conn.close()
    print("Bitti.")


if __name__ == "__main__":
    main()
