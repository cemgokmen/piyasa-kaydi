"""
Emtiaların arz-talep ve karar verilerini indirip veritabanına yazar:

  CFTC   Haftalık "Commitments of Traders" raporu: büyük spekülatif fonların
         (managed money) ve üreticilerin vadeli işlem konumları
  EIA    ABD ham petrol stokları (haftalık)
  FRED   Fed politika faizi, ABD 10 yıllık ve reel faiz (günlük)

Fiyatlar ve haberler burada indirilmez; site onları canlı alır.

Çalıştırmak için:  python -m piyasa emtia
"""

import io
import zipfile
from datetime import UTC, date, datetime

import pandas as pd
import requests

from piyasa.ayarlar import USER_AGENT
from piyasa.emtia.tanimlar import EIA_SERILERI, EMTIALAR, FRED_SERILERI
from piyasa.veritabani import get_connection, init_db

COT_URL = "https://www.cftc.gov/files/dea/history/fut_disagg_txt_{yil}.zip"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={seri}"

COT_SUTUNLARI = {
    "Report_Date_as_YYYY-MM-DD": "tarih",
    "Open_Interest_All": "acik_pozisyon",
    "M_Money_Positions_Long_All": "fon_uzun",
    "M_Money_Positions_Short_All": "fon_kisa",
    "Prod_Merc_Positions_Long_All": "uretici_uzun",
    "Prod_Merc_Positions_Short_All": "uretici_kisa",
}


def indir(url):
    cevap = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120)
    cevap.raise_for_status()
    return cevap.content


def cot_indir(conn, yillar):
    kodlar = {e["cot"]: e["slug"] for e in EMTIALAR if e["cot"]}
    # Takipten çıkarılan emtiaların eski kayıtları kalmasın
    yer = ", ".join("?" for _ in kodlar)
    conn.execute(f"DELETE FROM cot WHERE emtia NOT IN ({yer})", list(kodlar.values()))
    eklenen = 0
    for yil in yillar:
        try:
            zf = zipfile.ZipFile(io.BytesIO(indir(COT_URL.format(yil=yil))))
        except requests.HTTPError as hata:
            print(f"  CFTC {yil}: indirilemedi ({hata})")
            continue
        tablo = pd.read_csv(zf.open(zf.namelist()[0]), low_memory=False)
        kod = tablo["CFTC_Contract_Market_Code"].astype(str).str.strip()
        tablo = tablo.loc[kod.isin(kodlar), list(COT_SUTUNLARI)].copy()
        tablo["kod"] = kod[kod.isin(kodlar)]

        for _, s in tablo.iterrows():
            degerler = {yeni: s[eski] for eski, yeni in COT_SUTUNLARI.items()}
            conn.execute(
                """INSERT OR REPLACE INTO cot
                   (emtia, tarih, acik_pozisyon, fon_uzun, fon_kisa, uretici_uzun, uretici_kisa)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (kodlar[s["kod"]], degerler["tarih"], int(degerler["acik_pozisyon"]),
                 int(degerler["fon_uzun"]), int(degerler["fon_kisa"]),
                 int(degerler["uretici_uzun"]), int(degerler["uretici_kisa"])),
            )
            eklenen += 1
        print(f"  CFTC {yil}: {len(tablo)} haftalık kayıt")
    return eklenen


def eia_indir(conn):
    yer = ", ".join("?" for _ in EIA_SERILERI)
    conn.execute(f"DELETE FROM eia_stok WHERE seri NOT IN ({yer})", list(EIA_SERILERI))
    for anahtar, seri in EIA_SERILERI.items():
        try:
            dosya = pd.ExcelFile(io.BytesIO(indir(seri["url"])))
        except Exception as hata:
            print(f"  EIA {anahtar}: indirilemedi ({hata})")
            continue
        tablo = dosya.parse(dosya.sheet_names[1], header=2).dropna()
        tablo.columns = ["tarih", "deger"]
        conn.executemany(
            "INSERT OR REPLACE INTO eia_stok (seri, tarih, deger) VALUES (?, ?, ?)",
            [(anahtar, t.strftime("%Y-%m-%d"), float(d)) for t, d in tablo.itertuples(index=False)],
        )
        print(f"  EIA {anahtar}: {len(tablo)} hafta, son {tablo['tarih'].max():%Y-%m-%d}")


def fred_indir(conn):
    for anahtar, kod in FRED_SERILERI.items():
        try:
            tablo = pd.read_csv(io.BytesIO(indir(FRED_URL.format(seri=kod))))
        except Exception as hata:
            print(f"  FRED {anahtar}: indirilemedi ({hata})")
            continue
        tablo.columns = ["tarih", "deger"]
        tablo["deger"] = pd.to_numeric(tablo["deger"], errors="coerce")
        tablo = tablo.dropna()
        conn.executemany(
            "INSERT OR REPLACE INTO makro (seri, tarih, deger) VALUES (?, ?, ?)",
            [(anahtar, t, float(d)) for t, d in tablo.itertuples(index=False)],
        )
        print(f"  FRED {anahtar}: {len(tablo)} gün, son {tablo['tarih'].max()}")


def main():
    init_db()
    conn = get_connection()
    yil = date.today().year

    print("CFTC fon konumları")
    cot_indir(conn, [yil - 1, yil])
    print("EIA stokları")
    eia_indir(conn)
    print("FRED faizleri")
    fred_indir(conn)

    conn.execute(
        "INSERT OR REPLACE INTO emtia_guncelleme (anahtar, zaman) VALUES ('son', ?)",
        (datetime.now(UTC).isoformat(),),
    )
    conn.commit()
    conn.close()
    print("Bitti.")


if __name__ == "__main__":
    main()
