"""
Kripto verileri: büyük fonların Bitcoin ve Ether vadelilerindeki konumu.

Kaynak: CFTC "Traders in Financial Futures" haftalık raporu, resmi veri servisi
(publicreporting.cftc.gov). Kripto vadelileri finansal vadeliler raporunda yer alır;
iki grup ayrı tutulur:
  - kurum: varlık yöneticileri (emeklilik fonları, yatırım fonları) — uzun vadeli yatırımcı
  - hedge: kaldıraçlı fonlar (hedge fonları) — çoğu, spot ETF alıp vadeli satarak fiyat
    farkından kazanmaya çalışır; bu yüzden net satıcı görünmeleri düşüş beklentisi demek değildir.

Çalıştırmak için:
  python -m piyasa kripto                  CFTC verisini günceller
  python -m piyasa kripto --tara 2025 2026 işlenmiş Kongre bildirimlerini kripto işlemleri için
                                           yeniden okur (bir kez yeterli; yeni bildirimler
                                           kongre/senato adımlarında kendiliğinden işlenir)
"""

import sys

import requests

from piyasa.ayarlar import USER_AGENT
from piyasa.kripto.tanimlar import KRIPTOLAR
from piyasa.veritabani import get_connection, init_db

TFF_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"


def cot_indir(conn, hafta=160):
    eklenen = 0
    for k in KRIPTOLAR:
        if not k["cot"]:
            continue
        adet = 0
        cevap = requests.get(TFF_URL, params={
            "cftc_contract_market_code": k["cot"],
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": hafta,
        }, headers={"User-Agent": USER_AGENT}, timeout=60)
        cevap.raise_for_status()
        for s in cevap.json():
            conn.execute(
                """INSERT OR REPLACE INTO kripto_cot
                   (coin, tarih, acik_pozisyon, kurum_uzun, kurum_kisa, hedge_uzun, hedge_kisa)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (k["slug"], s["report_date_as_yyyy_mm_dd"][:10], int(s["open_interest_all"]),
                 int(s["asset_mgr_positions_long"]), int(s["asset_mgr_positions_short"]),
                 int(s["lev_money_positions_long"]), int(s["lev_money_positions_short"])),
            )
            adet += 1
        eklenen += adet
        print(f"  CFTC {k['ad']}: {adet} haftalık kayıt", flush=True)
    conn.commit()
    return eklenen


def main():
    init_db()
    argumanlar = sys.argv[1:]
    if "--tara" in argumanlar:
        from piyasa.toplama import kongre, senato
        yillar = [int(y) for y in argumanlar if y.isdigit()] or [2025, 2026]
        kongre.kripto_tara(yillar)
        senato.kripto_tara(yillar)
        return
    conn = get_connection()
    try:
        cot_indir(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
