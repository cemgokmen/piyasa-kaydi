"""
Günlük otomatik güncelleme (macOS launchd).

    python -m piyasa zamanla            günün güncellemesi 07:30'dan itibaren yapılır
    python -m piyasa zamanla --saat 6:15
    python -m piyasa zamanla --kaldir   otomatik güncellemeyi kapatır

Görev Mac açıldığında, uyandığında ve saat başı 'guncelle --gerekirse'
çalıştırır. Bu, günün güncellemesi henüz yapılmadıysa (ve saat 07:30'u
geçtiyse) güncellemeyi başlatır, yapıldıysa hemen çıkar. Böylece Mac sabah
kapalı olsa bile açıldığında o günün verisi gelir. Hata veren güncelleme bir
saat sonra yeniden denenir, günde en çok DENEME_SINIRI kez.

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
GUNLUK = VERI_DIZINI / "guncelleme.log"
DURUM = VERI_DIZINI / "son_guncelleme.json"
KILIT = VERI_DIZINI / "guncelleme.kilit"
DENEME_SINIRI = 3
KONTROL_ARALIGI = 3600          # saniye: saat başı


# ---------------------------------------------------------------------------
# Günün güncellemesi yapıldı mı?
# ---------------------------------------------------------------------------

def gun_baslangici(simdi, saat=7, dakika=30):
    """Şu an hangi 'güncelleme gününün' içindeyiz: en son geçilen saat:dakika anı."""
    bugun = datetime.combine(simdi.date(), time(saat, dakika))
    return bugun if simdi >= bugun else bugun - timedelta(days=1)


def durum_oku():
    try:
        return json.loads(DURUM.read_text())
    except (OSError, ValueError):
        return {}


def gerekli_mi(simdi, durum, saat=7, dakika=30):
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


def durum_yaz(simdi, basarili, hatalar, saat=7, dakika=30):
    onceki = durum_oku()
    ayni_gun = onceki.get("zaman") and \
        datetime.fromisoformat(onceki["zaman"]) >= gun_baslangici(simdi, saat, dakika)
    DURUM.write_text(json.dumps({
        "zaman": simdi.isoformat(timespec="seconds"),
        "basarili": basarili,
        "hatalar": hatalar,
        "deneme": (onceki.get("deneme", 0) if ayni_gun else 0) + 1,
    }, ensure_ascii=False, indent=2))


@contextmanager
def tek_guncelleme():
    """Aynı anda yalnızca bir güncelleme: kilit alınamazsa False verir."""
    KILIT.parent.mkdir(parents=True, exist_ok=True)
    with open(KILIT, "w") as f:
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


def kur(saat=7, dakika=30):
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    ayar = {
        "Label": ETIKET,
        "ProgramArguments": [sys.executable, "-m", "piyasa", "guncelle", "--gerekirse",
                             f"{saat}:{dakika:02d}"],
        "WorkingDirectory": str(KOK),
        # Açılışta, saat başı ve tam güncelleme saatinde kontrol eder; uykuda
        # kaçırılan kontrol uyanınca yapılır
        "RunAtLoad": True,
        "StartInterval": KONTROL_ARALIGI,
        "StartCalendarInterval": {"Hour": saat, "Minute": dakika},
        "StandardOutPath": str(GUNLUK),
        "StandardErrorPath": str(GUNLUK),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1",
                                 **({"SEC_USER_AGENT": os.environ["SEC_USER_AGENT"]}
                                    if "SEC_USER_AGENT" in os.environ else {})},
        "ProcessType": "Background",
        # Arka plan görevlerinde açık dosya sınırı varsayılan olarak 256'dır;
        # paralel fiyat indirme buna takılıyordu
        "SoftResourceLimits": {"NumberOfFiles": 4096},
    }
    with open(PLIST, "wb") as f:
        plistlib.dump(ayar, f)

    hedef = f"gui/{os.getuid()}"
    _launchctl("bootout", hedef, str(PLIST))          # eskisi varsa kaldır
    sonuc = _launchctl("bootstrap", hedef, str(PLIST))
    if sonuc.returncode != 0:
        print(f"launchd'ye yüklenemedi: {sonuc.stderr.strip()}")
        return False
    print(f"Günün güncellemesi her gün saat {saat:02d}:{dakika:02d} itibarıyla yapılır; Mac o saatte "
          "kapalıysa açılınca yapılır.")
    print(f"Ayar dosyası: {PLIST}")
    print(f"Çıktı: {GUNLUK}")
    return True


def kaldir():
    _launchctl("bootout", f"gui/{os.getuid()}", str(PLIST))
    if PLIST.exists():
        PLIST.unlink()
    print("Otomatik güncelleme kapatıldı.")


def durum():
    sonuc = _launchctl("print", f"gui/{os.getuid()}/{ETIKET}")
    return sonuc.returncode == 0


def main():
    argumanlar = sys.argv[1:]
    if "--kaldir" in argumanlar:
        kaldir()
        return
    saat, dakika = 7, 30
    if "--saat" in argumanlar:
        deger = argumanlar[argumanlar.index("--saat") + 1]
        saat, dakika = (int(x) for x in deger.split(":"))
    kur(saat, dakika)


if __name__ == "__main__":
    main()
