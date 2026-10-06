"""
Destek/direnç modelini gerçek hisselerde çalıştırır.
Kullanım:  python sr_dene.py THYAO.IS AAPL
"""

import sys

import yfinance as yf

from destek_direnc import bolgeleri_hesapla

ESIK = 0  # bu puanın altındaki bölgeler gösterilmez


def goster(kod):
    df = yf.Ticker(kod).history(period="5y", auto_adjust=True)
    if df.empty:
        print(f"{kod}: veri gelmedi\n")
        return

    s = bolgeleri_hesapla(df)
    print(f"=== {kod} ===")
    print(f"Fiyat {s['fiyat']:.2f}   ATR {s['atr']:.2f}   "
          f"şans oranı %{s['sans_orani'] * 100:.0f}   "
          f"yarılanma {s['yarilanma_mum']:g} mum   ({s['tarih']})\n")
    print(f"{'bölge':>17} {'tür':7} {'puan':>5} {'uzak%':>7} {'tutunan':>8} {'z':>5}  kaynak")

    for b in s["bolgeler"]:
        if b["puan"] < ESIK:
            continue
        bolge = f"{b['alt']:.2f}-{b['ust']:.2f}"
        print(f"{bolge:>17} {b['tur']:7} {b['puan']:5.1f} {b['uzaklik_yuzde']:7.2f} "
              f"{b['tutunan']:>3}/{b['test']:<4} {b['z']:5.1f}  {b['kaynaklar']}")
    print()


if __name__ == "__main__":
    kodlar = sys.argv[1:] or ["THYAO.IS", "ASELS.IS", "AAPL", "NVDA"]
    for kod in kodlar:
        goster(kod)