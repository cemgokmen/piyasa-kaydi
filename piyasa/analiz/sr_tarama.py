"""
Destek/direnç modelini geniş bir hisse grubunda tek seferde çalıştırır.

Kullanım:
    python -m piyasa sr-tarama              haftalık, tüm geçmiş
    python -m piyasa sr-tarama 1d 5y        günlük, 5 yıl
    python -m piyasa sr-tarama 1mo max      aylık (istatistik gücü yok, yalnızca bilgi)

Kriter önceden belirlendi: z >= 2.
Çoklu karşılaştırma: hiçbir gerçek etki olmasa bile her seviyenin
yaklaşık %2,3 ihtimalle z >= 2 çıkması beklenir. Sonuç, bulunan sayıyı
şansla beklenenle karşılaştırır.
"""

import sys
import warnings

import yfinance as yf
from scipy.stats import norm, binom

from piyasa.analiz.destek_direnc import YARILANMA_GUN, bolgeleri_hesapla

warnings.filterwarnings("ignore")

Z_ESIK = 2.0
MIN_TEST = 5   # 5'ten az testi olan seviye sayılmaz — istatistik anlamsız


HISSELER = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "XOM", "KO", "WMT",
    "BRK-B", "V", "MA", "UNH", "JNJ", "PG", "HD", "CVX", "MRK", "PEP",
    "ABBV", "COST", "AVGO", "ORCL", "BAC", "CSCO", "MCD", "DIS", "INTC", "AMD",
    "NFLX", "ADBE", "CRM", "NKE", "BA", "CAT", "GS", "IBM", "QCOM", "TXN",
]


ARALIK_ADI = {"1d": "günlük", "1wk": "haftalık", "1mo": "aylık"}


def main():
    aralik = sys.argv[1] if len(sys.argv) > 1 else "1wk"
    donem = sys.argv[2] if len(sys.argv) > 2 else "max"

    print(f"Zaman dilimi: {ARALIK_ADI.get(aralik, aralik)}   dönem: {donem}")
    print(f"Yarılanma süresi: {YARILANMA_GUN} işlem günü (mum sayısına otomatik çevrilir)\n")
    if aralik == "1mo":
        print("UYARI: aylık mumlarda bu test istatistik gücüne sahip değil.")
        print("Gerçek seviyeler bile z >= 2'ye ulaşamıyor. Sonuç yalnızca bilgi amaçlı.\n")

    toplam_seviye = 0
    toplam_anlamli = 0
    bulunanlar = []
    hatalar = []

    for kod in HISSELER:
        try:
            df = yf.Ticker(kod).history(period=donem, interval=aralik, auto_adjust=True)
            if df.empty:
                hatalar.append(kod)
                continue
            s = bolgeleri_hesapla(df)
        except Exception as hata:
            hatalar.append(f"{kod} ({hata})")
            continue

        seviyeler = [b for b in s["bolgeler"] if b["test"] >= MIN_TEST]
        anlamli = [b for b in seviyeler if b["z"] >= Z_ESIK]

        toplam_seviye += len(seviyeler)
        toplam_anlamli += len(anlamli)

        en_iyi = max((b["z"] for b in seviyeler), default=0)
        print(f"  {kod:10} mum {len(df):5}   seviye {len(seviyeler):2}   "
              f"z>=2: {len(anlamli)}   en yüksek z: {en_iyi:4.1f}")

        for b in anlamli:
            bulunanlar.append((kod, b))

    p_tek = 1 - norm.cdf(Z_ESIK)
    beklenen = toplam_seviye * p_tek
    if toplam_seviye and toplam_anlamli:
        p_deger = 1 - binom.cdf(toplam_anlamli - 1, toplam_seviye, p_tek)
    else:
        p_deger = 1.0

    print("\n" + "=" * 60)
    print(f"Test edilen seviye          : {toplam_seviye}")
    print(f"z >= {Z_ESIK} çıkan              : {toplam_anlamli}")
    print(f"Şansla beklenen             : {beklenen:.1f}")
    print(f"Bu kadarını şansla bulma    : %{p_deger * 100:.1f}")
    print("=" * 60)

    if p_deger < 0.05:
        print("\nBulunan sayı şanstan anlamlı ölçüde fazla.")
        print("Model bu zaman diliminde gerçek seviyeler yakalıyor olabilir.")
    else:
        print("\nBulunan sayı şansla açıklanabilir.")
        print("Tek tek z >= 2 seviyelere güvenmek için yeterli kanıt yok.")

    if bulunanlar:
        print("\nz >= 2 seviyeler:")
        for kod, b in bulunanlar:
            print(f"  {kod:10} {b['alt']:.2f}-{b['ust']:.2f}  {b['tur']:7} "
                  f"{b['tutunan']}/{b['test']}  z={b['z']}")

    if hatalar:
        print(f"\nVeri alınamayan: {', '.join(hatalar)}")


if __name__ == "__main__":
    main()