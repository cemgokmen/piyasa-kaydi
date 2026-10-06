"""
İki küçük başvuru tablosunu doldurur:

  sirket            hisse kodu → SEC sanayi kodu (SIC) ve sektör
  uye, komite_uyeligi   Temsilciler Meclisi üyeleri ve komite üyelikleri
                    (congress-legislators açık veri seti)

Çıkar çatışması analizi ikisini birleştirir: bir üye, komitesinin
denetlediği sektörden hisse aldı ya da sattı mı?

Çalıştırmak için:  python -m piyasa sirketler
"""

import time
from concurrent.futures import ThreadPoolExecutor

import requests

from piyasa.analiz.sektorler import KOMITE_ADLARI, sic_sektoru
from piyasa.ayarlar import USER_AGENT
from piyasa.kurallar import GECERLI_KOD
from piyasa.slug import slugify
from piyasa.veritabani import get_connection, init_db

SEC_KODLAR = "https://www.sec.gov/files/company_tickers.json"
SEC_SIRKET = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
UYELER = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
UYELIKLER = "https://unitedstates.github.io/congress-legislators/committee-membership-current.json"

SANIYEDE_ISTEK = 8   # SEC sınırı 10


def json_al(adres, deneme=3):
    """JSON indirir; geçici ağ hatalarında birkaç kez dener."""
    for sira in range(deneme):
        try:
            cevap = requests.get(adres, headers={"User-Agent": USER_AGENT}, timeout=60)
            cevap.raise_for_status()
            return cevap.json()
        except (requests.ConnectionError, requests.Timeout):
            if sira == deneme - 1:
                raise
            time.sleep(5 * (sira + 1))


def sektorleri_doldur(conn):
    hisseler = [s[0] for s in conn.execute(
        f"""SELECT DISTINCT ticker FROM transactions
           WHERE {GECERLI_KOD} AND ticker NOT IN (SELECT ticker FROM sirket)"""
    )]
    if not hisseler:
        print("  Yeni hisse yok.")
        return

    ciks = {}
    for k in json_al(SEC_KODLAR).values():
        ciks.setdefault(k["ticker"].upper(), k["cik_str"])

    def bul(hisse):
        cik = ciks.get(hisse) or ciks.get(hisse.replace(".", "-")) or ciks.get(hisse.replace("-", "."))
        if not cik:
            return hisse, None, None, None
        time.sleep(1 / SANIYEDE_ISTEK * 4)   # 4 iş parçacığı × bu bekleme ≈ saniyede 8 istek
        try:
            veri = json_al(SEC_SIRKET.format(cik=cik))
        except Exception:
            return hisse, cik, None, None
        sic = int(veri["sic"]) if str(veri.get("sic") or "").isdigit() else None
        return hisse, cik, sic, veri.get("sicDescription")

    with ThreadPoolExecutor(4) as havuz:
        for n, (hisse, cik, sic, aciklama) in enumerate(havuz.map(bul, hisseler), start=1):
            conn.execute(
                "INSERT OR REPLACE INTO sirket (ticker, cik, sic, sic_aciklama, sektor) VALUES (?, ?, ?, ?, ?)",
                (hisse, cik, sic, aciklama, sic_sektoru(sic)),
            )
            # Her kayıttan sonra yaz: ağ beklerken veritabanı kilitli kalmasın
            conn.commit()
            if n % 200 == 0:
                print(f"  {n}/{len(hisseler)} hisse", flush=True)
    conn.commit()
    bulunan = conn.execute("SELECT COUNT(*) FROM sirket WHERE sektor IS NOT NULL").fetchone()[0]
    print(f"  Sektörü bilinen hisse: {bulunan}")


def komiteleri_doldur(conn):
    uyeler = [u for u in json_al(UYELER) if u["terms"][-1]["type"] == "rep"]
    conn.execute("DELETE FROM uye")
    conn.execute("DELETE FROM komite_uyeligi")
    for u in uyeler:
        t = u["terms"][-1]
        ad = u["name"].get("official_full") or f'{u["name"]["first"]} {u["name"]["last"]}'
        gorevler = [r["title"] for r in u.get("leadership_roles", []) if not r.get("end")]
        conn.execute(
            "INSERT INTO uye (bioguide, ad, slug, parti, bolge, gorev) VALUES (?, ?, ?, ?, ?, ?)",
            (u["id"]["bioguide"], ad, slugify(ad), (t.get("party") or "")[:1],
             f"{t['state']}-{int(t.get('district') or 0):02d}", gorevler[0] if gorevler else None),
        )

    sayi = 0
    for kod, uyelikler in json_al(UYELIKLER).items():
        ana = kod[:4]          # alt komiteler ana komiteye bağlanır (HSAS02 → HSAS)
        if ana not in KOMITE_ADLARI:
            continue
        for m in uyelikler:
            conn.execute(
                "INSERT OR IGNORE INTO komite_uyeligi (bioguide, komite, unvan) VALUES (?, ?, ?)",
                (m["bioguide"], ana, m.get("title")),
            )
            sayi += 1
    conn.commit()
    print(f"  {len(uyeler)} üye, {sayi} komite üyeliği")


def main():
    init_db()
    conn = get_connection()
    print("Komite üyelikleri")
    komiteleri_doldur(conn)
    print("Şirket sektörleri (SEC)")
    sektorleri_doldur(conn)
    conn.close()


if __name__ == "__main__":
    main()
