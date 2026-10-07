"""
Devlet sözleşmeleri ile siyasetçi işlemlerinin kesişimi.

  hisse_ihaleleri(ticker)   hisse sayfası: şirkete bağlanan en büyük federal paralar
  islem_sonrasi()           siyasetçinin hisseyi aldıktan sonraki 90 günde şirkete
                            olağandan fazla devlet sözleşmesi gelen durumlar

"Olağandan fazla": büyük savunma şirketleri her ay sözleşme alır; bu yüzden
alımdan sonraki 90 günde gelen tutar, şirketin 2024'ten bu yana 90 günlük
ortalamasıyla karşılaştırılır. En az OLAGANDISI_KAT katıysa listeye girer.
Bu bir suçlama değildir: sözleşmeler çoğu zaman aylar önce planlanır.
"""

from collections import defaultdict
from contextlib import closing
from datetime import date, timedelta

from piyasa.analiz import cakisma
from piyasa.bicim import kisa_aralik, kisa_tutar
from piyasa.kurallar import GECERLI_KOD, TEMIZ, parti_bilgisi
from piyasa.kurallar import IHALE_BASLANGIC as BASLANGIC
from piyasa.onbellek import sureli
from piyasa.veritabani import get_connection

PENCERE = 90                   # alımdan sonra bakılan gün
ASGARI_TOPLAM = 10_000_000     # pencerede en az bu kadar sözleşme
OLAGANDISI_KAT = 2.0

KURUMLAR = {
    "Department of Defense": "Savunma Bakanlığı", "Department of Energy": "Enerji Bakanlığı",
    "Department of Health and Human Services": "Sağlık Bakanlığı", "Department of Veterans Affairs": "Gaziler Bakanlığı",
    "Department of Homeland Security": "İç Güvenlik Bakanlığı", "National Aeronautics and Space Administration": "NASA",
    "General Services Administration": "Genel Hizmetler İdaresi (GSA)", "Department of State": "Dışişleri Bakanlığı",
    "Department of Transportation": "Ulaştırma Bakanlığı", "Department of the Treasury": "Hazine Bakanlığı",
    "Department of Justice": "Adalet Bakanlığı", "Department of Agriculture": "Tarım Bakanlığı",
    "Department of Commerce": "Ticaret Bakanlığı", "Department of the Interior": "İçişleri Bakanlığı",
    "Department of Education": "Eğitim Bakanlığı", "Department of Labor": "Çalışma Bakanlığı",
    "Department of Housing and Urban Development": "Konut ve Kentsel Gelişim Bakanlığı",
    "Social Security Administration": "Sosyal Güvenlik İdaresi",
    "Environmental Protection Agency": "Çevre Koruma Ajansı (EPA)",
}
ALT_KURUMLAR = {
    "Department of the Navy": "Deniz Kuvvetleri", "Department of the Army": "Kara Kuvvetleri",
    "Department of the Air Force": "Hava Kuvvetleri", "Defense Logistics Agency": "Savunma Lojistik Ajansı",
    "Defense Health Agency": "Savunma Sağlık Ajansı", "Missile Defense Agency": "Füze Savunma Ajansı",
    "Defense Information Systems Agency": "Savunma Bilgi Sistemleri Ajansı",
    "Centers for Medicare and Medicaid Services": "Medicare ve Medicaid Merkezleri",
    "National Institutes of Health": "Ulusal Sağlık Enstitüleri (NIH)",
    "Centers for Disease Control and Prevention": "Hastalık Kontrol Merkezleri (CDC)",
    "Food and Drug Administration": "İlaç Dairesi (FDA)",
    "U.S. Immigration and Customs Enforcement": "Göçmenlik ve Gümrük (ICE)",
    "U.S. Customs and Border Protection": "Gümrük ve Sınır Koruma",
}


def kurum_adi(kurum, alt=None):
    """'Department of Defense' / 'Department of the Navy' -> 'Savunma Bakanlığı · Deniz Kuvvetleri'"""
    ana = KURUMLAR.get(kurum, kurum)
    if alt and alt != kurum:
        return f"{ana} · {ALT_KURUMLAR.get(alt, alt)}"
    return ana


def _hazirla(s):
    k = dict(s)
    k["kurum_adi"] = kurum_adi(s["kurum"], s["alt_kurum"])
    k["tutar_kisa"] = kisa_tutar(s["tutar"])
    k["aciklama"] = (s["aciklama"] or "").capitalize() or None
    return k


def hisse_ihaleleri(ticker, adet=8):
    """Şirkete 2024'ten bu yana bağlanan en büyük federal paralar; hiç yoksa None."""
    with closing(get_connection()) as conn:
        ozet = conn.execute(
            """SELECT COUNT(*) AS adet, SUM(tutar) AS toplam,
                      SUM(CASE WHEN tarih >= ? THEN tutar END) AS son_yil
               FROM ihale WHERE ticker = ?""",
            ((date.today() - timedelta(days=365)).isoformat(), ticker),
        ).fetchone()
        if not ozet["adet"]:
            return None
        kurumlar = conn.execute(
            "SELECT kurum, SUM(tutar) AS toplam FROM ihale WHERE ticker = ? GROUP BY kurum ORDER BY toplam DESC LIMIT 3",
            (ticker,),
        ).fetchall()
        en_buyuk = [_hazirla(s) for s in conn.execute(
            "SELECT * FROM ihale WHERE ticker = ? ORDER BY tutar DESC LIMIT ?", (ticker, adet))]
    return {
        "adet": ozet["adet"], "toplam": kisa_tutar(ozet["toplam"]), "son_yil": kisa_tutar(ozet["son_yil"] or 0),
        "kurumlar": [{"ad": kurum_adi(k["kurum"]), "toplam": kisa_tutar(k["toplam"])} for k in kurumlar],
        "liste": en_buyuk, "baslangic": BASLANGIC,
    }


@sureli(30 * 60)
def islem_sonrasi(pencere=PENCERE):
    """Siyasetçinin aldığı hisseye, alımdan sonraki 90 günde olağandan fazla devlet sözleşmesi gelenler."""
    bugun = date.today()
    with closing(get_connection()) as conn:
        alimlar = conn.execute(
            f"""SELECT id, person, person_slug, party, chamber, state, ticker, asset_name,
                       transaction_date, amount_min, amount_max
                FROM transactions
                WHERE chamber IS NOT NULL AND action = 'buy' AND transaction_date >= ?
                  AND ticker IN (SELECT DISTINCT ticker FROM ihale) AND {TEMIZ} AND {GECERLI_KOD}
                ORDER BY transaction_date""",
            (BASLANGIC,),
        ).fetchall()
        ihaleler = defaultdict(list)
        for s in conn.execute("SELECT * FROM ihale ORDER BY tarih"):
            ihaleler[s["ticker"]].append(s)

    gun_sayisi = max((bugun - date.fromisoformat(BASLANGIC)).days, pencere)
    olagan = {t: sum(i["tutar"] for i in liste) / gun_sayisi * pencere for t, liste in ihaleler.items()}
    cakisanlar = cakisma.cakisan_islemler()

    # Aynı kişinin aynı hisseyi pencere içinde tekrar tekrar alması tek olaydır:
    # ilk alımdan itibaren 90 gün içindeki alımlar aynı olaya eklenir
    kisi_hisse = defaultdict(list)
    for a in alimlar:
        kisi_hisse[(a["person_slug"], a["ticker"])].append(a)
    olaylar = []
    for liste in kisi_hisse.values():
        for a in liste:
            tarih = date.fromisoformat(a["transaction_date"])
            if olaylar and olaylar[-1]["alimlar"][0]["person_slug"] == a["person_slug"] \
                    and olaylar[-1]["alimlar"][0]["ticker"] == a["ticker"] and tarih <= olaylar[-1]["bitis"]:
                olaylar[-1]["alimlar"].append(a)
            else:
                olaylar.append({"ilk": tarih, "bitis": tarih + timedelta(days=pencere), "alimlar": [a]})

    sonuc = []
    for olay in olaylar:
        a = olay["alimlar"][0]
        sonraki = [i for i in ihaleler[a["ticker"]]
                   if olay["ilk"] < date.fromisoformat(i["tarih"]) <= olay["bitis"]]
        toplam = sum(i["tutar"] for i in sonraki)
        kat = toplam / olagan[a["ticker"]] if olagan.get(a["ticker"]) else 0
        if toplam < ASGARI_TOPLAM or kat < OLAGANDISI_KAT:
            continue
        en_buyuk = max(sonraki, key=lambda i: i["tutar"])
        komite = next((cakisanlar[x["id"]] for x in olay["alimlar"] if x["id"] in cakisanlar), None)
        sonuc.append({
            "kisi": a["person"], "slug": a["person_slug"], "parti": parti_bilgisi(a["party"]),
            "meclis": a["chamber"], "bolge": a["state"], "ticker": a["ticker"], "sirket": a["asset_name"],
            "ilk_alim": olay["ilk"].isoformat(), "alim_sayisi": len(olay["alimlar"]),
            "alim_tutari": kisa_aralik(sum(x["amount_min"] or 0 for x in olay["alimlar"]),
                                       sum(x["amount_max"] or 0 for x in olay["alimlar"])),
            "ihale_sayisi": len(sonraki), "ihale_toplam": toplam, "ihale_toplam_kisa": kisa_tutar(toplam),
            "kat": kat, "en_buyuk": _hazirla(en_buyuk),
            "gun_sonra": (date.fromisoformat(en_buyuk["tarih"]) - olay["ilk"]).days,
            "komite": komite,
        })
    sonuc.sort(key=lambda x: (x["komite"] is not None, x["kat"] * min(x["ihale_toplam"], 1e9)), reverse=True)
    return sonuc
