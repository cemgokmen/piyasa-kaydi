"""
İşlem yapılan hisselerin günlük kapanış fiyatlarını ve karşılaştırma endeksini
(S&P 500 fonu SPY) indirir. Getiri ve sinyal analizleri bu tabloyu kullanır.

Yalnızca siyasetçi işlemleri ve yönetici alımları olan hisseler indirilir.
Her çalıştırmada son 10 günün fiyatları yenilenir; yeni hisselerin tüm
geçmişi alınır.

Çalıştırmak için:  python -m piyasa fiyatlar
"""

import time
import warnings
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

from piyasa.fiyat import yahoo_kodu
from piyasa.kurallar import GECERLI_KOD, TEMIZ
from piyasa.veritabani import get_connection, init_db

ENDEKS = "SPY"
PARCA = 150            # tek istekte indirilen hisse sayısı
YENILEME_GUN = 10      # son kaç günün fiyatı her seferinde yeniden yazılsın


def gereken_hisseler(conn):
    return sorted({
        s["ticker"] for s in conn.execute(
            f"""SELECT DISTINCT ticker FROM transactions
               WHERE (chamber IS NOT NULL OR action = 'buy') AND {TEMIZ} AND {GECERLI_KOD}"""
        )
    } | {ENDEKS})


def baslangic_tarihi(conn):
    """En eski işlemden bir ay önce."""
    ilk = conn.execute(
        "SELECT MIN(transaction_date) FROM transactions WHERE chamber IS NOT NULL OR action = 'buy'"
    ).fetchone()[0]
    ilk = date.fromisoformat(ilk[:10]) if ilk else date.today() - timedelta(days=730)
    # Tarihi hatalı yazılmış eski bildirimler yüzünden çok geriye gitme
    return max(ilk, date.today() - timedelta(days=3 * 365)) - timedelta(days=30)


def parca_indir(hisseler, baslangic):
    """Bir grup hissenin kapanışları: {bildirimdeki kod: Series}"""
    yahoo = {yahoo_kodu(h): h for h in hisseler}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tablo = yf.download(list(yahoo), start=baslangic.isoformat(), auto_adjust=True,
                            progress=False, threads=True)
    if tablo.empty:
        return {}
    kapanis = tablo["Close"] if isinstance(tablo.columns, pd.MultiIndex) else tablo[["Close"]].rename(
        columns={"Close": list(yahoo)[0]})
    return {yahoo[k]: kapanis[k].dropna() for k in kapanis.columns if k in yahoo and kapanis[k].notna().any()}


def main():
    init_db()
    conn = get_connection()
    hisseler = gereken_hisseler(conn)
    baslangic = baslangic_tarihi(conn)

    mevcut = {s[0] for s in conn.execute("SELECT DISTINCT ticker FROM fiyat_gecmisi")}
    yeniler = [h for h in hisseler if h not in mevcut]
    eskiler = [h for h in hisseler if h in mevcut]
    print(f"{len(hisseler)} hisse: {len(yeniler)} yeni (tüm geçmiş), {len(eskiler)} güncellenecek")

    yenileme = date.today() - timedelta(days=YENILEME_GUN)
    isler = [(yeniler, baslangic), (eskiler, yenileme)]
    bulunamayan = 0

    for liste, bas in isler:
        for i in range(0, len(liste), PARCA):
            parca = liste[i:i + PARCA]
            seriler = parca_indir(parca, bas)
            # Yahoo hız sınırına takılınca bütün parça boş döner: bekleyip bir kez daha dene
            for bekleme in (60, 180):
                if seriler or not parca:
                    break
                print(f"  Yahoo hız sınırı, {bekleme} sn bekleniyor...", flush=True)
                time.sleep(bekleme)
                seriler = parca_indir(parca, bas)
            bulunamayan += len(parca) - len(seriler)
            for hisse, seri in seriler.items():
                conn.executemany(
                    "INSERT OR REPLACE INTO fiyat_gecmisi (ticker, tarih, kapanis) VALUES (?, ?, ?)",
                    [(hisse, t.strftime("%Y-%m-%d"), round(float(v), 4)) for t, v in seri.items()],
                )
            conn.commit()
            print(f"  {min(i + PARCA, len(liste))}/{len(liste)} (başlangıç {bas})", flush=True)

    toplam = conn.execute("SELECT COUNT(DISTINCT ticker) FROM fiyat_gecmisi").fetchone()[0]
    conn.close()
    print(f"\nFiyatı olan hisse: {toplam}. Yahoo'da bulunamayan (borsadan çıkmış vb.): {bulunamayan}")


if __name__ == "__main__":
    main()
