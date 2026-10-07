"""
Toplanan verideki bilinen sorunları düzeltir. Her güncellemede çalışır, tekrar
çalıştırılması zararsızdır.

  1. Borsa kodları tek biçime getirilir ('vicr' -> 'VICR', 'LEN, LEN.B' -> 'LEN').
     Küçük harfli kodlu işlemler hisse sayfasında görünmüyordu.
  2. Düzeltilmiş raporların (amendment) kopyaları silinir: aynı kişi, hisse, gün,
     işlem ve tutar farklı raporlarda tekrar ediyorsa yalnızca ilk bildirilen
     kalır (geç bildirim hesabı da ilk bildirim tarihine göre yapılmalı).
     Aynı rapordaki tekrarlar ayrı hesaplardaki ayrı işlemler olabilir; silinmez.
  3. Görevden ayrılmış Kongre üyelerinin boş kalan partisi ve eyaleti, üyelerin
     geçmiş kaydından tamamlanır (congress-legislators, legislators-historical).

Tarih hataları (bildirimden sonraki ya da yıllar önceki işlem tarihleri) burada
değil, her seferinde işaretleri baştan hesaplayan supheli adımında işaretlenir.

Çalıştırmak için:  python -m piyasa duzelt
"""

from contextlib import closing

from piyasa.kurallar import kod_duzelt
from piyasa.slug import slugify
from piyasa.toplama.kongre_ortak import json_al_uyeler, parti_kodu
from piyasa.veritabani import get_connection


def kodlari_duzelt(conn):
    degisen = 0
    for (kod,) in conn.execute("SELECT DISTINCT ticker FROM transactions").fetchall():
        yeni = kod_duzelt(kod)
        if yeni != kod:
            degisen += conn.execute("UPDATE transactions SET ticker = ? WHERE ticker = ?", (yeni, kod)).rowcount
    print(f"  Borsa kodu düzeltilen işlem: {degisen}")


def tekrarlari_sil(conn):
    silinen = conn.execute(
        """DELETE FROM transactions WHERE id IN (
               SELECT t.id FROM transactions t
               JOIN (SELECT person_slug, ticker, transaction_date, action, amount_min, amount_max,
                            MIN(disclosed_date) AS ilk
                     FROM transactions WHERE source IN ('house_ptr', 'senate_ptr')
                     GROUP BY 1, 2, 3, 4, 5, 6 HAVING COUNT(DISTINCT source_url) > 1) g
                 ON g.person_slug = t.person_slug AND g.ticker = t.ticker
                AND g.transaction_date = t.transaction_date AND g.action = t.action
                AND g.amount_min IS t.amount_min AND g.amount_max IS t.amount_max
               WHERE t.source IN ('house_ptr', 'senate_ptr') AND t.disclosed_date > g.ilk)"""
    ).rowcount
    print(f"  Düzeltilmiş rapor kopyası silinen işlem: {silinen}")


def partileri_tamamla(conn):
    eksik = conn.execute(
        "SELECT DISTINCT person, person_slug, chamber FROM transactions WHERE chamber IS NOT NULL AND party IS NULL"
    ).fetchall()
    if not eksik:
        return
    try:
        gecmis = json_al_uyeler(gecmis=True)
    except Exception as hata:
        print(f"  Geçmiş üye kaydı alınamadı ({hata})")
        return
    adaylar = {}
    for u in gecmis:
        t = u["terms"][-1]
        if t.get("end", "") < "2023-01-01":
            continue
        bilgi = {"parti": parti_kodu(t.get("party")),
                 "bolge": t["state"] if t["type"] == "sen" else f"{t['state']}-{int(t.get('district') or 0):02d}"}
        for ad in (u["name"].get("official_full"), f'{u["name"].get("first", "")} {u["name"].get("last", "")}'):
            if ad:
                adaylar[slugify(ad)] = bilgi
    tamamlanan = 0
    for k in eksik:
        bilgi = adaylar.get(k["person_slug"])
        if bilgi:
            tamamlanan += conn.execute(
                "UPDATE transactions SET party = ?, state = COALESCE(state, ?) WHERE person_slug = ? AND party IS NULL",
                (bilgi["parti"], bilgi["bolge"], k["person_slug"]),
            ).rowcount
    print(f"  Partisi tamamlanan işlem: {tamamlanan} ({len(eksik)} kişi eksikti)")


def main():
    with closing(get_connection()) as conn:
        kodlari_duzelt(conn)
        tekrarlari_sil(conn)
        partileri_tamamla(conn)
        conn.commit()


if __name__ == "__main__":
    main()
