"""
Eski veritabanlarına eksik sütunları ekler.
Artık database.init_db() bunu kendisi yapıyor; bu dosya geriye dönük
uyumluluk için duruyor.
"""

from piyasa.veritabani import DB_PATH, init_db


def main():
    init_db()
    print(f"Veritabanı hazır: {DB_PATH}")


if __name__ == "__main__":
    main()
