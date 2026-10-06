"""
Eski veritabanlarına eksik sütunları ekler.
Artık database.init_db() bunu kendisi yapıyor; bu dosya geriye dönük
uyumluluk için duruyor.
"""

from database import init_db


if __name__ == "__main__":
    init_db()
    print("Bitti.")
