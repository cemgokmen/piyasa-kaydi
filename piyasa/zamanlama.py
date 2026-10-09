"""
Günlük otomatik güncelleme (macOS launchd).

    python -m piyasa zamanla            iki görevi kurar (aşağıda)
    python -m piyasa zamanla --saat 6:15
    python -m piyasa zamanla --kaldir   otomatik güncellemeyi kapatır

İki görev kurulur:

  1. Tam güncelleme (her gün 07:00): bütün veriler, fiyatlar, analizler ve
     günlük özet. Görev Mac açıldığında, uyandığında ve saat başı
     'guncelle --gerekirse' çalıştırır; günün güncellemesi henüz yapılmadıysa
     (ve saat 07:00'ı geçtiyse) başlatır, yapıldıysa hemen çıkar. Hata veren
     güncelleme bir saat sonra yeniden denenir, günde en çok DENEME_SINIRI kez.
  2. Hızlı güncelleme (her gün 12:00, 18:00, 21:00 ve 00:00): yeni Meclis,
     Senato ve fon bildirimleri ve bakımları (Form 4 ve KAP canlı güncellemede).
  3. Canlı güncelleme (15 dakikada bir): SEC'e gün içinde düşen Form 4
     bildirimleri ve KAP'ın o günkü bildirimleri. Kendi kilidi vardır; uzun
     süren tam güncelleme sırasında da çalışır. İnternet kotasını korumak için
     bildirimlerin gelmediği saatlerde (gece, hafta sonu) saatte bire düşer.

İkisi de başlamadan internetin gelmesini bekler (uykudan uyanan Mac'te ağ
birkaç saniye geç geliyor); internet gelmezse bu çalıştırma deneme sayılmaz.

Son güncellemenin durumu data/son_guncelleme.json, çıktı data/guncelleme.log
dosyasındadır.
"""

import fcntl
import json
import os
import plistlib
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, time, timedelta
from pathlib import Path

from piyasa.ayarlar import KOK, VERI_DIZINI

ETIKET = "com.piyasakaydi.guncelle"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{ETIKET}.plist"
HIZLI_ETIKET = "com.piyasakaydi.hizli"
HIZLI_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{HIZLI_ETIKET}.plist"
HIZLI_SAATLER = (0, 12, 18, 21)
CANLI_ETIKET = "com.piyasakaydi.canli"
CANLI_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{CANLI_ETIKET}.plist"
CANLI_ARALIK = 900              # saniye: 15 dakika
SAKIN_ARALIK = 55 * 60          # yoğun olmayan saatlerde canlı güncelleme en çok saatte bir
INTERNET_BEKLEME = 300          # saniye
DENETIM_ADRESI = "www.sec.gov"
GUNLUK = VERI_DIZINI / "guncelleme.log"
DURUM = VERI_DIZINI / "son_guncelleme.json"
HIZLI_DURUM = VERI_DIZINI / "son_hizli_guncelleme.json"
CANLI_DURUM = VERI_DIZINI / "son_canli_guncelleme.json"
KILIT = VERI_DIZINI / "guncelleme.kilit"
CANLI_KILIT = VERI_DIZINI / "canli.kilit"
DENEME_SINIRI = 3
KONTROL_ARALIGI = 3600          # saniye: saat başı


# ---------------------------------------------------------------------------
# Günün güncellemesi yapıldı mı?
# ---------------------------------------------------------------------------

def internet_bekle(sure=INTERNET_BEKLEME, aralik=15):
    """İnternet (DNS) gelene kadar en çok 'sure' saniye bekler; geldiyse True."""
    import socket
    import time as zaman
    son = zaman.monotonic() + sure
    while True:
        try:
            socket.getaddrinfo(DENETIM_ADRESI, 443)
            return True
        except OSError:
            if zaman.monotonic() >= son:
                return False
            zaman.sleep(aralik)


def gun_baslangici(simdi, saat=7, dakika=0):
    """Şu an hangi 'güncelleme gününün' içindeyiz: en son geçilen saat:dakika anı."""
    bugun = datetime.combine(simdi.date(), time(saat, dakika))
    return bugun if simdi >= bugun else bugun - timedelta(days=1)


def durum_oku():
    try:
        return json.loads(DURUM.read_text())
    except (OSError, ValueError):
        return {}


def gerekli_mi(simdi, durum, saat=7, dakika=0):
    """
    Bu güncelleme gününde başarılı güncelleme yoksa ve deneme sınırı
    dolmadıysa True. Gün, saat:dakika anında başlar (gece yarısı değil):
    Mac gece 03:00'te açılırsa önceki günün güncellemesi yapılmışsa beklenir.
    """
    baslangic = gun_baslangici(simdi, saat, dakika)
    son = durum.get("zaman")
    if not son or datetime.fromisoformat(son) < baslangic:
        return True                                   # bu gün hiç denenmedi
    if durum.get("basarili"):
        return False
    return durum.get("deneme", 0) < DENEME_SINIRI


def durum_yaz(simdi, basarili, hatalar, saat=7, dakika=0):
    onceki = durum_oku()
    ayni_gun = onceki.get("zaman") and \
        datetime.fromisoformat(onceki["zaman"]) >= gun_baslangici(simdi, saat, dakika)
    DURUM.write_text(json.dumps({
        "zaman": simdi.isoformat(timespec="seconds"),
        "basarili": basarili,
        "hatalar": hatalar,
        "deneme": (onceki.get("deneme", 0) if ayni_gun else 0) + 1,
    }, ensure_ascii=False, indent=2))


def hizli_durum_yaz(simdi, basarili, dosya=HIZLI_DURUM):
    dosya.write_text(json.dumps({"zaman": simdi.isoformat(timespec="seconds"), "basarili": basarili}))


def bildirim_saati_mi(simdi):
    """
    Bildirimlerin yoğun geldiği saatler (Türkiye saati). KAP: hafta içi 08:00–24:00.
    SEC: hafta içi ABD'de 08:00–22:00, yani Türkiye'de 13:00'ten ertesi gün 05:00'e.
    """
    gun, saat = simdi.weekday(), simdi.hour
    kap = gun < 5 and saat >= 8
    sec = (gun < 5 and saat >= 13) or (1 <= gun <= 5 and saat < 5)
    return kap or sec


def canli_zamani_mi(simdi):
    """Yoğun saatlerde her tetiklemede; diğer saatlerde son çalışmadan en az SAKIN_ARALIK sonra."""
    if bildirim_saati_mi(simdi):
        return True
    try:
        son = datetime.fromisoformat(json.loads(CANLI_DURUM.read_text())["zaman"])
    except (OSError, ValueError, KeyError):
        return True
    return (simdi - son).total_seconds() >= SAKIN_ARALIK


def son_kontrol():
    """En son başarılı güncellemenin (tam, hızlı ya da canlı) zamanı; yoksa None."""
    zamanlar = []
    for dosya in (DURUM, HIZLI_DURUM, CANLI_DURUM):
        try:
            veri = json.loads(dosya.read_text())
        except (OSError, ValueError):
            continue
        if veri.get("basarili") and veri.get("zaman"):
            zamanlar.append(datetime.fromisoformat(veri["zaman"]))
    return max(zamanlar) if zamanlar else None


@contextmanager
def tek_guncelleme(kilit=KILIT):
    """Aynı anda yalnızca bir güncelleme: kilit alınamazsa False verir."""
    kilit.parent.mkdir(parents=True, exist_ok=True)
    with open(kilit, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _launchctl(*argumanlar):
    return subprocess.run(["launchctl", *argumanlar], capture_output=True, text=True)


def _gorev_yaz(etiket, plist, argumanlar, ek):
    plist.parent.mkdir(parents=True, exist_ok=True)
    ayar = {
        "Label": etiket,
        "ProgramArguments": [sys.executable, "-m", "piyasa", *argumanlar],
        "WorkingDirectory": str(KOK),
        "StandardOutPath": str(GUNLUK),
        "StandardErrorPath": str(GUNLUK),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1",
                                 **({"SEC_USER_AGENT": os.environ["SEC_USER_AGENT"]}
                                    if "SEC_USER_AGENT" in os.environ else {})},
        "ProcessType": "Background",
        # Arka plan görevlerinde açık dosya sınırı varsayılan olarak 256'dır;
        # paralel fiyat indirme buna takılıyordu
        "SoftResourceLimits": {"NumberOfFiles": 4096},
        **ek,
    }
    with open(plist, "wb") as f:
        plistlib.dump(ayar, f)
    hedef = f"gui/{os.getuid()}"
    _launchctl("bootout", hedef, str(plist))          # eskisi varsa kaldır
    sonuc = _launchctl("bootstrap", hedef, str(plist))
    if sonuc.returncode != 0:
        print(f"{etiket} launchd'ye yüklenemedi: {sonuc.stderr.strip()}")
        return False
    return True


def kur(saat=7, dakika=0):
    tam = _gorev_yaz(ETIKET, PLIST, ["guncelle", "--gerekirse", f"{saat}:{dakika:02d}"], {
        # Açılışta, saat başı ve tam güncelleme saatinde kontrol eder; uykuda
        # kaçırılan kontrol uyanınca yapılır
        "RunAtLoad": True,
        "StartInterval": KONTROL_ARALIGI,
        "StartCalendarInterval": {"Hour": saat, "Minute": dakika},
    })
    hizli = _gorev_yaz(HIZLI_ETIKET, HIZLI_PLIST, ["guncelle", "--hizli"], {
        "StartCalendarInterval": [{"Hour": h, "Minute": 0} for h in HIZLI_SAATLER],
    })
    canli = _gorev_yaz(CANLI_ETIKET, CANLI_PLIST, ["guncelle", "--canli"], {
        "StartInterval": CANLI_ARALIK,
    })
    if tam:
        print(f"Tam güncelleme her gün {saat:02d}:{dakika:02d}'de; Mac o saatte kapalıysa açılınca yapılır.")
    if hizli:
        saatler = [f"{h:02d}:00" for h in sorted(HIZLI_SAATLER)]
        print("Hızlı güncelleme (Kongre ve fon bildirimleri) her gün "
              + ", ".join(saatler[:-1]) + " ve " + saatler[-1] + "'de.")
    if canli:
        print(f"Canlı güncelleme (gün içi Form 4 ve KAP bildirimleri) {CANLI_ARALIK // 60} dakikada bir.")
    print(f"Çıktı: {GUNLUK}")
    return tam and hizli and canli


def kaldir():
    for plist in (PLIST, HIZLI_PLIST, CANLI_PLIST):
        _launchctl("bootout", f"gui/{os.getuid()}", str(plist))
        if plist.exists():
            plist.unlink()
    print("Otomatik güncelleme kapatıldı.")


def durum():
    sonuc = _launchctl("print", f"gui/{os.getuid()}/{ETIKET}")
    return sonuc.returncode == 0


def main():
    argumanlar = sys.argv[1:]
    if "--kaldir" in argumanlar:
        kaldir()
        return
    saat, dakika = 7, 0
    if "--saat" in argumanlar:
        deger = argumanlar[argumanlar.index("--saat") + 1]
        saat, dakika = (int(x) for x in deger.split(":"))
    kur(saat, dakika)


if __name__ == "__main__":
    main()
