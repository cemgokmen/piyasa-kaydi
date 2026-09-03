"""
Elimizdeki örnek JSON kayıtlarını veritabanına aktarır.
Tekrar çalıştırırsan mükerrer kayıt oluşmaz.
"""

import json
from datetime import datetime, timezone

from database import get_connection, init_db, BASE_DIR

COLUMNS = [
    "source_id", "source", "person", "chamber", "state", "party", "committee",
    "job_title", "company", "ticker", "asset_name", "action",
    "amount_min", "amount_max", "currency",
    "transaction_date", "disclosed_date", "source_url", "fetched_at",
]


def save_transaction(conn, row):
    """Tek bir kaydı veritabanına yazar. Zaten varsa atlar."""
    values = [row.get(col) for col in COLUMNS]
    placeholders = ", ".join("?" for _ in COLUMNS)

    cursor = conn.execute(
        f"INSERT OR IGNORE INTO transactions ({', '.join(COLUMNS)}) "
        f"VALUES ({placeholders})",
        values,
    )
    return cursor.rowcount


def main():
    init_db()

    with open(BASE_DIR / "data" / "islemler.json", encoding="utf-8") as f:
        records = json.load(f)

    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()

    added = 0
    for i, record in enumerate(records, start=1):
        record.setdefault("source_id", f"ornek-{i:04d}")
        record.setdefault("source", "ornek")
        record.setdefault("currency", "USD")
        record["fetched_at"] = now
        added += save_transaction(conn, record)

    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    conn.close()

    print(f"{added} yeni kayıt eklendi.")
    print(f"Veritabanındaki toplam kayıt: {total}")


if __name__ == "__main__":
    main()