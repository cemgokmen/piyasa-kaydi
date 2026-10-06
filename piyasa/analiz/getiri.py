"""
İşlem sonrası getiriler.

Her siyasetçi işlemi ve her yönetici alımı için, hissenin belirli bir süre
sonraki getirisini aynı dönemde S&P 500'ün (SPY) getirisiyle karşılaştırır.
İki başlangıç noktası vardır:

  islem     işlemin yapıldığı gün — kişinin kendi zamanlaması
  bildirim  işlemin kamuya açıklandığı gün — onu izleyen birinin
            gerçekte yakalayabileceği getiri

Sonuçlar islem_getirisi tablosuna yazılır; site oradan okur.

Çalıştırmak için:  python -m piyasa analiz
"""

from datetime import timedelta

import numpy as np
import pandas as pd

from piyasa.toplama.fiyat_gecmisi import ENDEKS
from piyasa.veritabani import get_connection, init_db

UFUKLAR = {"30": 30, "90": 90, "180": 180}
BUGUN = "bugun"
GIRIS_TOLERANSI = 7   # işlem günü fiyat yoksa en fazla kaç gün sonraki kapanış alınsın


class FiyatDeposu:
    """Hisse başına (tarihler, kapanışlar) dizileri; hızlı tarih araması için."""

    def __init__(self, conn, hisseler=None):
        """hisseler verilirse yalnızca onların fiyatları yüklenir (hızlı)."""
        if hisseler is not None:
            hisseler = sorted(set(hisseler) | {ENDEKS})
            yer = ",".join("?" * len(hisseler))
            tablo = pd.read_sql_query(
                f"SELECT ticker, tarih, kapanis FROM fiyat_gecmisi WHERE ticker IN ({yer}) ORDER BY ticker, tarih",
                conn, params=hisseler)
        else:
            tablo = pd.read_sql_query("SELECT ticker, tarih, kapanis FROM fiyat_gecmisi ORDER BY ticker, tarih", conn)
        self.seriler = {
            # Gün hassasiyetinde tarih dizisi: aradaki fark doğrudan gün sayısı olsun
            t: (np.array(g["tarih"].tolist(), dtype="datetime64[D]"), g["kapanis"].to_numpy())
            for t, g in tablo.groupby("ticker", sort=False)
        }

    def kapanis(self, ticker, gun, tolerans=GIRIS_TOLERANSI):
        """gun ya da sonraki ilk işlem gününün kapanışı (tolerans içinde)."""
        seri = self.seriler.get(ticker)
        if seri is None:
            return None
        tarihler, degerler = seri
        hedef = np.datetime64(gun, "D")
        i = np.searchsorted(tarihler, hedef)
        if i >= len(tarihler) or (tarihler[i] - hedef) / np.timedelta64(1, "D") > tolerans:
            return None
        return float(degerler[i])

    def son(self, ticker):
        seri = self.seriler.get(ticker)
        return (seri[0][-1], float(seri[1][-1])) if seri is not None else (None, None)


def getiri_hesapla(depo, ticker, baslangic, ufuk_gun):
    """
    (hisse getirisi, endeks getirisi) ya da veri yetersizse None.
    ufuk_gun None ise bugüne kadar.
    """
    giris = depo.kapanis(ticker, baslangic)
    endeks_giris = depo.kapanis(ENDEKS, baslangic)
    if not giris or not endeks_giris:
        return None

    if ufuk_gun is None:
        son_tarih, cikis = depo.son(ticker)
        if son_tarih is None or son_tarih <= np.datetime64(baslangic, "D"):
            return None
        endeks_cikis = depo.kapanis(ENDEKS, pd.Timestamp(son_tarih).date(), tolerans=5)
    else:
        bitis = baslangic + timedelta(days=ufuk_gun)
        endeks_son, _ = depo.son(ENDEKS)
        if endeks_son is None or np.datetime64(bitis, "D") > endeks_son:
            return None     # bu süre henüz dolmadı
        cikis = depo.kapanis(ticker, bitis)
        endeks_cikis = depo.kapanis(ENDEKS, bitis)
    if not cikis or not endeks_cikis:
        return None
    return cikis / giris - 1, endeks_cikis / endeks_giris - 1


def main():
    init_db()
    conn = get_connection()
    depo = FiyatDeposu(conn)
    if ENDEKS not in depo.seriler:
        print("Önce fiyatları indirin: python -m piyasa fiyatlar")
        return

    islemler = conn.execute(
        """SELECT id, ticker, transaction_date, disclosed_date FROM transactions
           WHERE (chamber IS NOT NULL OR action = 'buy')
             AND (suspect IS NULL OR suspect = 0)"""
    ).fetchall()

    satirlar = []
    for s in islemler:
        for baz, tarih in (("islem", s["transaction_date"]), ("bildirim", s["disclosed_date"])):
            try:
                gun = pd.Timestamp(tarih[:10]).date()
            except (TypeError, ValueError):
                continue
            for ufuk, sure in [*UFUKLAR.items(), (BUGUN, None)]:
                sonuc = getiri_hesapla(depo, s["ticker"], gun, sure)
                if sonuc:
                    satirlar.append((s["id"], baz, ufuk, round(sonuc[0], 6), round(sonuc[1], 6)))

    conn.execute("DELETE FROM islem_getirisi")
    conn.executemany(
        "INSERT INTO islem_getirisi (islem_id, baz, ufuk, getiri, endeks) VALUES (?, ?, ?, ?, ?)",
        satirlar,
    )
    conn.commit()
    hesaplanan = conn.execute("SELECT COUNT(DISTINCT islem_id) FROM islem_getirisi").fetchone()[0]
    conn.close()
    print(f"{len(islemler)} işlemden {hesaplanan} tanesinin getirisi hesaplandı ({len(satirlar)} satır).")


if __name__ == "__main__":
    main()
