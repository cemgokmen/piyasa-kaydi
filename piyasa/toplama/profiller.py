"""
Son bir yılda işlem görmüş, profili olmayan hisselerin "Şirket hakkında"
bilgisini önceden doldurur; hisse sayfası ilk açılışta beklemez.
Profili olmayan hisse sayfası açıldığında da profil o an alınır.

Çalıştırmak için:  python -m piyasa profiller [en çok kaç hisse, varsayılan 150]
"""

import sys
import time
from contextlib import closing

from piyasa.sirket_profili import profil
from piyasa.veritabani import get_connection, init_db


def eksikler(conn, sinir):
    return [s[0] for s in conn.execute(
        """SELECT ticker FROM transactions
           WHERE transaction_date >= date('now', '-365 day') AND ticker != ''
             AND ticker NOT IN (SELECT ticker FROM sirket_profili WHERE ozet IS NOT NULL)
           GROUP BY ticker ORDER BY COUNT(*) DESC LIMIT ?""",
        (sinir,),
    )]


def main():
    init_db()
    argumanlar = [a for a in sys.argv[1:] if a.isdigit()]
    sinir = int(argumanlar[0]) if argumanlar else 150
    with closing(get_connection()) as conn:
        liste = eksikler(conn, sinir)
    print(f"Profili eksik hisse: {len(liste)}", flush=True)
    bulunan = 0
    for i, ticker in enumerate(liste, 1):
        if profil(ticker):
            bulunan += 1
        if i % 25 == 0:
            print(f"  {i}/{len(liste)}  bulunan: {bulunan}", flush=True)
        time.sleep(0.5)
    print(f"Bitti. Profil: {bulunan}/{len(liste)}")


if __name__ == "__main__":
    main()
