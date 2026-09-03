"""
Veritabanındaki eski ham dosya adreslerini okunabilir bildirim
sayfası adresleriyle değiştirir. Bir kez çalıştırılır.
"""

from database import get_connection
from toplayici import belge_url

ON_EK = "https://www.sec.gov/Archives/"


def main():
    conn = get_connection()

    rows = conn.execute(
        "SELECT id, source_url FROM transactions "
        "WHERE source_url LIKE ? AND source_url LIKE ?",
        (ON_EK + "%", "%.txt"),
    ).fetchall()

    print(f"Düzeltilecek kayıt: {len(rows)}")

    for row in rows:
        yol = row["source_url"][len(ON_EK):]
        conn.execute(
            "UPDATE transactions SET source_url = ? WHERE id = ?",
            (belge_url(yol), row["id"]),
        )

    conn.commit()

    ornek = conn.execute(
        "SELECT source_url FROM transactions WHERE source = 'edgar_form4' LIMIT 1"
    ).fetchone()
    conn.close()

    print("Bitti. Örnek adres:")
    print(" ", ornek["source_url"] if ornek else "kayıt yok")


if __name__ == "__main__":
    main()