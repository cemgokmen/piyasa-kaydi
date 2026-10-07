"""
ABD Senatosu üyelerinin hisse işlemlerini (STOCK Act "Periodic Transaction
Report" bildirimleri) çekip veritabanına yazar.

Kaynak: Senato elektronik bildirim sistemi — https://efdsearch.senate.gov
  - Site sıradan program isteklerini engelliyor (Akamai, 403); bu yüzden
    görünmez (headless) bir Chrome açılır, kullanım şartları onaylanır ve
    istekler sayfanın içinden yapılır.
  - Rapor listesi: /search/report/data/ (rapor türü 11 = periyodik işlem raporu)
  - Her rapor bir HTML sayfası: /search/view/ptr/<kimlik>/ ; tabloda tarih,
    sahip, borsa kodu, varlık adı, türü, işlem ve tutar aralığı var.
  - Elle doldurulup taranmış raporlar (/search/view/paper/) resimdir; atlanır.

Senatörler congress-legislators veri setinden soyad (gerekirse ad) ile
eşleştirilir; parti, eyalet ve resmi tam ad oradan gelir.

Çalıştırmak için:  python -m piyasa senato [yıl ...]
  Yıl verilmezse son 60 günde yayımlanan raporlar taranır. Tekrar çalıştırılabilir:
  işlenmiş raporlar atlanır.
"""

import html
import re
import sys
import time
from datetime import UTC, date, datetime, timedelta

from piyasa.slug import slugify
from piyasa.toplama.form4 import kaydet
from piyasa.toplama.kongre import PARTI_KISA, islenmis_bildirimler, json_al_uyeler, sade, tutar_coz
from piyasa.veritabani import get_connection, init_db

KAYNAK = "senate_ptr"
SITE = "https://efdsearch.senate.gov"
SAYFA_BOYU = 100
BEKLEME = 0.4
VARSAYILAN_GUN = 60

ISLEMLER = {"purchase": "buy", "sale (full)": "sell", "sale (partial)": "sell", "sale": "sell"}
KABUL_EDILEN_TURLER = {"stock"}

SATIR = re.compile(r"<tr>(.*?)</tr>", re.S)
HUCRE = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
ETIKET = re.compile(r"<[^>]+>")
RAPOR_BAGI = re.compile(r'href="(/search/view/(ptr|paper)/([^/"]+)/)"')


# ---------------------------------------------------------------------------
# TARAYICI
# ---------------------------------------------------------------------------

class Senato:
    """Kullanım şartları onaylanmış görünmez bir tarayıcı oturumu."""

    def __init__(self):
        from selenium import webdriver
        from selenium.webdriver.common.by import By

        secenek = webdriver.ChromeOptions()
        secenek.add_argument("--headless=new")
        secenek.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36")
        self.tarayici = webdriver.Chrome(options=secenek)
        self.tarayici.set_script_timeout(90)
        self.tarayici.get(f"{SITE}/search/home/")
        time.sleep(2)
        self.tarayici.find_element(By.ID, "agree_statement").click()
        time.sleep(2)

    def kapat(self):
        self.tarayici.quit()

    def _getir(self, adres, form=None):
        betik = """
            const [adres, form, bitti] = arguments;
            const secenek = {};
            if (form) {
              const csrf = (document.cookie.split('; ').find(c => c.startsWith('csrftoken=')) || '').split('=')[1];
              secenek.method = 'POST';
              secenek.body = new URLSearchParams(form);
              secenek.headers = {'X-CSRFToken': csrf, 'Content-Type': 'application/x-www-form-urlencoded'};
            }
            fetch(adres, secenek).then(r => r.ok ? r.text() : 'HATA ' + r.status)
              .then(bitti).catch(e => bitti('HATA ' + e));
        """
        sonuc = self.tarayici.execute_async_script(betik, adres, form)
        if sonuc.startswith("HATA"):
            raise RuntimeError(f"{adres}: {sonuc}")
        return sonuc

    def raporlar(self, baslangic, bitis=None):
        """[{kimlik, tur ('ptr'/'paper'), adres, ad, soyad, tarih}] — yayın tarihi aralığındaki raporlar."""
        import json
        liste, bas = [], 0
        while True:
            veri = json.loads(self._getir("/search/report/data/", {
                "start": str(bas), "length": str(SAYFA_BOYU), "report_types": "[11]", "filer_types": "[]",
                "submitted_start_date": baslangic.strftime("%m/%d/%Y 00:00:00"),
                "submitted_end_date": bitis.strftime("%m/%d/%Y 23:59:59") if bitis else "",
                "candidate_state": "", "senator_state": "", "office_id": "", "first_name": "", "last_name": "",
            }))
            for ad, soyad, _, bag, tarih in veri["data"]:
                m = RAPOR_BAGI.search(bag)
                if not m:
                    continue
                ay, gun, yil = tarih.split("/")
                liste.append({"adres": m.group(1), "tur": m.group(2), "kimlik": m.group(3),
                              "ad": ad.strip(), "soyad": soyad.strip(), "tarih": f"{yil}-{ay}-{gun}"})
            bas += SAYFA_BOYU
            if bas >= veri["recordsTotal"]:
                return liste
            time.sleep(BEKLEME)

    def rapor(self, adres):
        return self._getir(adres)


# ---------------------------------------------------------------------------
# AYRIŞTIRMA
# ---------------------------------------------------------------------------

def _metin(hucre):
    return html.unescape(ETIKET.sub("", hucre)).strip()


def rapor_ayristir(sayfa):
    """Rapor sayfasındaki işlem tablosunun satırları."""
    govde = sayfa[sayfa.find("<tbody>"):sayfa.find("</tbody>")]
    satirlar = []
    for satir in SATIR.findall(govde):
        h = [_metin(x) for x in HUCRE.findall(satir)]
        if len(h) < 8:
            continue
        satirlar.append({"sira": h[0], "tarih": h[1], "sahip": h[2], "ticker": h[3], "varlik": h[4],
                         "tur": h[5], "islem": h[6], "tutar": h[7]})
    return satirlar


# Güncel listede olmayan, işlem bildirmiş eski senatörler (görevden ayrılanlar)
ESKI_SENATORLER = [
    {"ad": "Marco Rubio", "soyad": "rubio", "ilk": "marco", "eyalet": "FL", "parti": "R"},
    {"ad": "Thomas R. Carper", "soyad": "carper", "ilk": "thomas", "eyalet": "DE", "parti": "D"},
    {"ad": "Markwayne Mullin", "soyad": "mullin", "ilk": "markwayne", "eyalet": "OK", "parti": "R"},
]


def senatorler():
    """{sade soyad: [senatör]} — congress-legislators verisinden, eski senatörlerle birlikte."""
    sonuc = {}
    for e in ESKI_SENATORLER:
        sonuc.setdefault(e["soyad"], []).append({k: v for k, v in e.items() if k != "soyad"})
    for u in json_al_uyeler():
        t = u["terms"][-1]
        if t["type"] != "sen":
            continue
        soyad = sade(u["name"].get("last", ""))
        sonuc[soyad] = [x for x in sonuc.get(soyad, []) if x["ilk"] != sade(u["name"].get("first", ""))]
        sonuc[soyad].append({
            "ad": u["name"].get("official_full") or f'{u["name"]["first"]} {u["name"]["last"]}',
            "ilk": sade(u["name"].get("first", "")),
            "eyalet": t["state"],
            "parti": PARTI_KISA.get(t.get("party"), (t.get("party") or "")[:1]),
        })
    return sonuc


def senator_bul(rapor, liste):
    """Rapordaki 'McConnell, Jr.' / 'A. Mitchell' adını senatör listesiyle eşler."""
    soyad = sade(re.split(r",|\s+(jr|sr|ii|iii|iv)\b", rapor["soyad"], flags=re.I)[0]).strip()
    adaylar = liste.get(soyad) or [u for k, v in liste.items() if soyad and (soyad in k or k in soyad) for u in v]
    if len(adaylar) == 1:
        return adaylar[0]
    ilk = sade(rapor["ad"]).split()
    for u in adaylar:
        if any(parca.strip(".") and (u["ilk"].startswith(parca.strip(".")) or parca.strip(".") in u["ilk"])
               for parca in ilk):
            return u
    return None


def kayitlara_cevir(rapor, satirlar, senator):
    ad = senator["ad"] if senator else f'{rapor["ad"]} {rapor["soyad"]}'.strip()
    kayitlar = []
    for s in satirlar:
        islem = ISLEMLER.get(s["islem"].lower())
        kod = s["ticker"].strip()
        if s["tur"].lower() not in KABUL_EDILEN_TURLER or not islem or not kod or kod == "--":
            continue
        alt, ust = tutar_coz(s["tutar"])
        ay, gun, yil = s["tarih"].split("/")
        kayitlar.append({
            "source_id": f"senate-{rapor['kimlik']}-{s['sira']}",
            "source": KAYNAK,
            "person": ad,
            "person_slug": slugify(ad),
            "chamber": "Senato",
            "state": senator and senator["eyalet"],
            "party": senator and senator["parti"],
            "job_title": "Senatör",
            "ticker": kod.replace(".", "-").upper(),
            "asset_name": s["varlik"],
            "company": s["varlik"],
            "action": islem,
            "amount_min": alt,
            "amount_max": ust,
            "currency": "USD",
            "transaction_date": f"{yil}-{ay}-{gun}",
            "disclosed_date": rapor["tarih"],
            "source_url": SITE + rapor["adres"],
            "security_name": "Hisse senedi" + (f" ({s['sahip']})" if s["sahip"] and s["sahip"] != "Self" else ""),
        })
    return kayitlar


# ---------------------------------------------------------------------------
# ANA AKIŞ
# ---------------------------------------------------------------------------

def main():
    yillar = [int(y) for y in sys.argv[1:] if y.isdigit()]
    if yillar:
        araliklar = [(date(y, 1, 1), date(y, 12, 31)) for y in yillar]
    else:
        araliklar = [(date.today() - timedelta(days=VARSAYILAN_GUN), None)]

    init_db()
    conn = get_connection()
    islenmis = islenmis_bildirimler(conn)
    liste = senatorler()
    oturum = Senato()
    toplam = 0
    try:
        for bas, bit in araliklar:
            raporlar = oturum.raporlar(bas, bit)
            yeni = [r for r in raporlar if f"senate-{r['kimlik']}" not in islenmis]
            print(f"{bas}: {len(raporlar)} rapor, {len(yeni)} tanesi yeni.", flush=True)
            for n, r in enumerate(yeni, 1):
                simdi = datetime.now(UTC).isoformat()
                if r["tur"] == "paper":
                    durum, eklenen = "taranmis", 0
                else:
                    try:
                        senator = senator_bul(r, liste)
                        eklenen = 0
                        for k in kayitlara_cevir(r, rapor_ayristir(oturum.rapor(r["adres"])), senator):
                            k["fetched_at"] = simdi
                            eklenen += kaydet(conn, k)
                        durum = "tamam"
                    except Exception as hata:
                        print(f"  {r['kimlik']} ayrıştırılamadı: {hata}", flush=True)
                        continue
                    time.sleep(BEKLEME)
                conn.execute("INSERT OR REPLACE INTO kongre_bildirimleri VALUES (?, ?, ?, ?)",
                             (f"senate-{r['kimlik']}", eklenen, durum, simdi))
                conn.commit()
                toplam += eklenen
                if eklenen:
                    print(f"  [{n}/{len(yeni)}] {r['tarih']}  {r['ad']} {r['soyad']:20} {eklenen} işlem", flush=True)
    finally:
        oturum.kapat()
    sayi = conn.execute("SELECT COUNT(*) FROM transactions WHERE source = ?", (KAYNAK,)).fetchone()[0]
    conn.close()
    print(f"\nBu turda eklenen: {toplam}\nVeritabanındaki Senato işlemi: {sayi}")


if __name__ == "__main__":
    main()
