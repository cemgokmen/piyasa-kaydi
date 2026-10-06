"""
Günlük otomatik güncelleme (macOS launchd).

    python -m piyasa zamanla            her sabah 07:30'da 'guncelle' çalışır
    python -m piyasa zamanla --saat 6:15
    python -m piyasa zamanla --kaldir   otomatik güncellemeyi kapatır

Bilgisayar o saatte uykudaysa, uyandığında çalışır; kapalıysa o günü atlar.
Çıktı data/guncelleme.log dosyasına yazılır.
"""

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from piyasa.ayarlar import KOK, VERI_DIZINI

ETIKET = "com.piyasakaydi.guncelle"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{ETIKET}.plist"
GUNLUK = VERI_DIZINI / "guncelleme.log"


def _launchctl(*argumanlar):
    return subprocess.run(["launchctl", *argumanlar], capture_output=True, text=True)


def kur(saat=7, dakika=30):
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    ayar = {
        "Label": ETIKET,
        "ProgramArguments": [sys.executable, "-m", "piyasa", "guncelle"],
        "WorkingDirectory": str(KOK),
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
    print(f"Her gün {saat:02d}:{dakika:02d}'de güncelleme yapılacak.")
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
