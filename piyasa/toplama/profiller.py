"""
Son bir yılda işlem görmüş, profili olmayan hisselerin "Şirket hakkında"
bilgisini önceden doldurur; hisse sayfası ilk açılışta beklemez.
Profili olmayan hisse sayfası açıldığında da profil o an alınır.

Çalıştırmak için:  python -m piyasa profiller [en çok kaç hisse, varsayılan 150]
                   python -m piyasa profiller --yenile   kayıtlı bütün profilleri yeniden alır
                   (ör. faaliyet alanı sözlüğü güncellenince)
"""

import sys
import time
from contextlib import closing

from piyasa.sirket_profili import elle_yazilmis_tanimlar, profil, yeniden_al
from piyasa.veritabani import get_connection, init_db


def eksikler(conn, sinir):
    """Son bir yılda işlem görmüş ve elle tanımı yazılmış, profili olmayan hisseler."""
    kayitli = {s[0] for s in conn.execute("SELECT ticker FROM sirket_profili WHERE ozet IS NOT NULL")}
    elle = [t for t in elle_yazilmis_tanimlar() if t not in kayitli]
    return elle + [s[0] for s in conn.execute(
        """SELECT ticker FROM transactions
           WHERE transaction_date >= date('now', '-365 day') AND ticker != ''
             AND ticker NOT IN (SELECT ticker FROM sirket_profili WHERE ozet IS NOT NULL)
           GROUP BY ticker ORDER BY COUNT(*) DESC LIMIT ?""",
        (sinir,),
    ) if s[0] not in elle]


def yenile():
    with closing(get_connection()) as conn:
        hepsi = [s[0] for s in conn.execute("SELECT ticker FROM sirket_profili ORDER BY ticker")]
    print(f"Yenilenecek profil: {len(hepsi)}", flush=True)
    for i, ticker in enumerate(hepsi, 1):
        yeniden_al(ticker)
        if i % 25 == 0:
            print(f"  {i}/{len(hepsi)}", flush=True)
        time.sleep(0.5)


def main():
    init_db()
    if "--yenile" in sys.argv[1:]:
        yenile()
        return
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
