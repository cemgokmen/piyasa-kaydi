"""
Paylaşım kuralları ve komut: python -m piyasa paylas [--gercek] [--hepsi]

  - Gece 00:00–08:00 (Türkiye) paylaşım yok; o saatlerde gelenler sabah sırayla paylaşılır.
  - Günde en çok GUNLUK_SINIR gönderi; iki gönderi arası en az ARALIK dakika.
  - Her çalıştırmada en çok bir gönderi (15 dakikalık canlı güncellemeyle doğal aralık).
  - Paylaşılan her bildirim 'paylasim' tablosuna yazılır, ikinci kez paylaşılmaz.
  - Deneme (varsayılan): hiçbir şey göndermez ve kaydetmez; sıradakileri listeler.
"""

import sys
from datetime import datetime, timedelta

from piyasa import fiyat
from piyasa.paylasim import secim, x
from piyasa.veritabani import get_connection, init_db

GUNLUK_SINIR = 8
ARALIK = 40                 # dakika
SESSIZ = (0, 8)             # saat aralığı: paylaşım yok
X_SINIRI = 280              # karakter (bağlantı 23 sayılır)


def uzunluk(metin):
    """X'in saydığı uzunluk: bağlantılar 23 karakter."""
    import re
    return len(re.sub(r"\S+\.(com|org|net)\S*", "x" * 23, metin))


def _kur():
    try:
        return (fiyat.anlik_fiyat("TRY=X", ham=True) or {}).get("fiyat") or 45.0
    except Exception:
        return 45.0


def bekleyenler(conn, simdi=None):
    """Daha önce paylaşılmamış adaylar, önem sırasıyla."""
    paylasilan = {r[0] for r in conn.execute("SELECT anahtar FROM paylasim")}
    return [a for a in secim.adaylar(conn, simdi, kur=_kur()) if a["anahtar"] not in paylasilan]


def paylasabilir_mi(conn, simdi):
    """(evet/hayır, neden)."""
    if SESSIZ[0] <= simdi.hour < SESSIZ[1]:
        return False, "gece saatleri"
    bugun = simdi.date().isoformat()
    sayi = conn.execute("SELECT COUNT(*) FROM paylasim WHERE durum = 'gonderildi' AND substr(zaman, 1, 10) = ?",
                        (bugun,)).fetchone()[0]
    if sayi >= GUNLUK_SINIR:
        return False, f"günlük sınır doldu ({sayi})"
    son = conn.execute("SELECT MAX(zaman) FROM paylasim WHERE durum = 'gonderildi'").fetchone()[0]
    if son and simdi - datetime.fromisoformat(son) < timedelta(minutes=ARALIK):
        return False, "son gönderiden bu yana yeterli süre geçmedi"
    return True, ""


def main():
    argumanlar = sys.argv[1:]
    gercek = "--gercek" in argumanlar
    init_db()
    conn = get_connection()
    try:
        simdi = datetime.now()
        liste = bekleyenler(conn, simdi)
        if not gercek:
            print(f"Deneme: {len(liste)} paylaşılabilir bildirim (önem sırasıyla)\n")
            for a in liste[: None if "--hepsi" in argumanlar else 10]:
                print(f"── {a['tur']} · önem {a['onem']:,.0f} $ · {uzunluk(a['metin'])} karakter".replace(",", "."))
                print(a["metin"], "\n")
            return
        if not x.anahtarlar():
            print(f"X anahtarları yok ({x.ANAHTAR_DOSYASI}); paylaşım atlandı.")
            return
        evet, neden = paylasabilir_mi(conn, simdi)
        if not evet or not liste:
            print(f"Paylaşım yok: {neden or 'paylaşılacak yeni bildirim yok'}")
            return
        aday = next((a for a in liste if uzunluk(a["metin"]) <= X_SINIRI), None)
        if aday is None:
            return
        try:
            numara = x.gonder(aday["metin"])
            durum = "gonderildi"
        except Exception as hata:
            numara, durum = None, f"hata: {hata}"[:300]
        conn.execute("INSERT OR REPLACE INTO paylasim (anahtar, platform, metin, durum, gonderi_id, zaman) "
                     "VALUES (?, 'x', ?, ?, ?, ?)",
                     (aday["anahtar"], aday["metin"], durum, numara, simdi.isoformat(timespec="seconds")))
        conn.commit()
        print(f"{durum}: {aday['anahtar']}" + (f" → https://x.com/i/web/status/{numara}" if numara else ""))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
