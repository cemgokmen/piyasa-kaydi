"""
Siteyi yayına uygun şekilde çalıştırır (gunicorn: aynı anda birden çok ziyaretçi).

    python -m piyasa yayin            sitenin üretim sürümünü başlatır (http://127.0.0.1:5001)
    python -m piyasa yayin --kur      Mac açılınca kendiliğinden başlasın, çökerse yeniden açılsın
    python -m piyasa yayin --kaldir   otomatik başlatmayı kapatır

Site yalnızca bu bilgisayardan (127.0.0.1) dinler; dışarıya Cloudflare Tunnel
açar. Tünel, vekil sunucu başlıklarını (gerçek adres, https) iletir; uygulama
bu yüzden vekil_arkasinda=True ile kurulur. Çıktı data/site.log dosyasına yazılır.

İşçi düzeni: 2 süreç × 8 iş parçacığı. Sayfaların çoğu veritabanı ve Yahoo'yu
beklediği için iş parçacığı verimli; bellek (süreç başına ~350 MB) 2 süreçle
sınırlı kalır.
"""

import os
import plistlib
import sys
from pathlib import Path

from piyasa.ayarlar import KOK, VERI_DIZINI
from piyasa.zamanlama import _launchctl

ETIKET = "com.piyasakaydi.site"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{ETIKET}.plist"
GUNLUK = VERI_DIZINI / "site.log"
ADRES = "127.0.0.1:5001"
UYGULAMA = "piyasa.web:create_app(vekil_arkasinda=True)"


def gunicorn_argumanlari():
    return [
        "--bind", ADRES,
        "--workers", "2",
        "--worker-class", "gthread",
        "--threads", "8",
        "--timeout", "60",
        "--graceful-timeout", "20",
        "--max-requests", "2000",          # bellek şişmesine karşı süreçler arada yenilenir
        "--max-requests-jitter", "200",
        "--access-logfile", "-",
        UYGULAMA,
    ]


def calistir():
    gunicorn = Path(sys.executable).with_name("gunicorn")
    print(f"Site başlıyor: http://{ADRES}", flush=True)
    os.chdir(KOK)
    if sys.platform == "darwin":
        # macOS, iş parçacığı olan bir süreçten fork edilen işçileri Objective-C
        # başlatma denetiminde öldürüyor (gunicorn işçileri sürekli çöküp yeniden
        # açılıyordu). Bilinen çözüm bu denetimi kapatmak; Linux'ta gerekmez.
        os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
    os.execv(str(gunicorn), [str(gunicorn), *gunicorn_argumanlari()])


def kur():
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    ayar = {
        "Label": ETIKET,
        "ProgramArguments": [sys.executable, "-m", "piyasa", "yayin"],
        "WorkingDirectory": str(KOK),
        "RunAtLoad": True,
        "KeepAlive": True,                 # çökerse launchd yeniden başlatır
        "ThrottleInterval": 10,
        "StandardOutPath": str(GUNLUK),
        "StandardErrorPath": str(GUNLUK),
        "EnvironmentVariables": {"PYTHONUNBUFFERED": "1"},
        "SoftResourceLimits": {"NumberOfFiles": 4096},
    }
    with open(PLIST, "wb") as f:
        plistlib.dump(ayar, f)
    hedef = f"gui/{os.getuid()}"
    _launchctl("bootout", hedef, str(PLIST))
    sonuc = _launchctl("bootstrap", hedef, str(PLIST))
    if sonuc.returncode != 0:
        print(f"launchd'ye yüklenemedi: {sonuc.stderr.strip()}")
        return False
    print(f"Site artık Mac açılınca kendiliğinden başlar: http://{ADRES}")
    print(f"Çıktı: {GUNLUK}")
    return True


def kaldir():
    _launchctl("bootout", f"gui/{os.getuid()}", str(PLIST))
    if PLIST.exists():
        PLIST.unlink()
    print("Sitenin otomatik başlatılması kapatıldı.")


def main():
    argumanlar = sys.argv[1:]
    if "--kur" in argumanlar:
        kur()
    elif "--kaldir" in argumanlar:
        kaldir()
    else:
        calistir()


if __name__ == "__main__":
    main()
