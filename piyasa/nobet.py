"""
Sitenin kesintisiz açık kalması için iki arka plan görevi (macOS launchd).

    python -m piyasa nobet            bir kez denetler (görev bunu 2 dakikada bir çalıştırır)
    python -m piyasa nobet --kur      iki görevi kurar (aşağıda)
    python -m piyasa nobet --kaldir   ikisini de kapatır

  1. Uyanık (com.piyasakaydi.uyanik): 'caffeinate' Mac'in boşta uykuya
     geçmesini engeller. Kapak kapanınca uyumayı engellemez; bunun için
     'sudo pmset -a disablesleep 1' gerekir (yönetici ister).
  2. Nöbetçi (com.piyasakaydi.nobet): siteyi önce bu bilgisayardan, sonra
     piyasakaydi.com üzerinden açar. Yerel adres art arda HATA_SINIRI kez
     yanıt vermezse siteyi, yerel açık ama dış adres kapalıysa tüneli yeniden
     başlatır. launchd'nin KeepAlive'ı yalnızca çöken süreci yeniden açar;
     açık kalıp yanıt vermeyen (takılan) süreci bu görev yakalar.

Olaylar data/nobet.log dosyasına yazılır; her şey yolundayken bir şey yazılmaz.
"""

import json
import os
import plistlib
import sys
from datetime import datetime
from pathlib import Path

from piyasa.ayarlar import KOK, VERI_DIZINI, VERITABANI
from piyasa.zamanlama import _launchctl

NOBET_ETIKET = "com.piyasakaydi.nobet"
UYANIK_ETIKET = "com.piyasakaydi.uyanik"
SITE_ETIKET = "com.piyasakaydi.site"
TUNEL_ETIKET = "com.piyasakaydi.tunel"
AJANLAR = Path.home() / "Library" / "LaunchAgents"
ARALIK = 120                    # saniye
HATA_SINIRI = 2                 # art arda bu kadar hatadan sonra yeniden başlatılır
ZAMAN_ASIMI = 20                # saniye
YEREL = "http://127.0.0.1:5001/api/serit"
DIS = "https://piyasakaydi.com/api/serit"
GUNLUK = VERI_DIZINI / "nobet.log"
# Sayaçlar her çalıştırmada okunup yazıldığı için iCloud'a eşitlenen klasörde durmaz
DURUM = VERITABANI.parent / "nobet.json"


def acik_mi(adres):
    import requests
    try:
        return requests.get(adres, headers={"User-Agent": "piyasakaydi-nobet"},
                            timeout=ZAMAN_ASIMI).status_code == 200
    except requests.RequestException:
        return False


def karar(durum, yerel, dis):
    """Yeni sayaçlar ve yeniden başlatılacak görev (yoksa None)."""
    yerel_hata = 0 if yerel else durum.get("yerel", 0) + 1
    dis_hata = 0 if (dis or not yerel) else durum.get("dis", 0) + 1
    yeniden = None
    if yerel_hata >= HATA_SINIRI:
        yeniden, yerel_hata = SITE_ETIKET, 0
    elif dis_hata >= HATA_SINIRI:
        yeniden, dis_hata = TUNEL_ETIKET, 0
    return {"yerel": yerel_hata, "dis": dis_hata}, yeniden


def _yaz(mesaj):
    with open(GUNLUK, "a") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}  {mesaj}\n")


def denetle():
    try:
        durum = json.loads(DURUM.read_text())
    except (OSError, ValueError):
        durum = {}
    yerel = acik_mi(YEREL)
    dis = acik_mi(DIS) if yerel else False
    yeni, yeniden = karar(durum, yerel, dis)
    if not yerel:
        _yaz(f"yerel adres yanıt vermedi ({yeni['yerel'] or HATA_SINIRI}/{HATA_SINIRI})")
    elif not dis:
        _yaz(f"piyasakaydi.com yanıt vermedi ({yeni['dis'] or HATA_SINIRI}/{HATA_SINIRI})")
    if yeniden:
        sonuc = _launchctl("kickstart", "-k", f"gui/{os.getuid()}/{yeniden}")
        _yaz(f"{yeniden} yeniden başlatıldı" + (f": {sonuc.stderr.strip()}" if sonuc.returncode else ""))
    DURUM.parent.mkdir(parents=True, exist_ok=True)
    DURUM.write_text(json.dumps(yeni))


def _gorev(etiket, ayar):
    plist = AJANLAR / f"{etiket}.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    with open(plist, "wb") as f:
        plistlib.dump({"Label": etiket, **ayar}, f)
    hedef = f"gui/{os.getuid()}"
    _launchctl("bootout", hedef, str(plist))
    sonuc = _launchctl("bootstrap", hedef, str(plist))
    if sonuc.returncode != 0:
        print(f"{etiket} launchd'ye yüklenemedi: {sonuc.stderr.strip()}")
        return False
    return True


def kur():
    tamam = _gorev(UYANIK_ETIKET, {
        # -i: boşta uyku yok, -s: prize takılıyken sistem uykusu yok
        "ProgramArguments": ["/usr/bin/caffeinate", "-i", "-s"],
        "RunAtLoad": True,
        "KeepAlive": True,
    })
    tamam &= _gorev(NOBET_ETIKET, {
        "ProgramArguments": [sys.executable, "-m", "piyasa", "nobet"],
        "WorkingDirectory": str(KOK),
        "StartInterval": ARALIK,
        "RunAtLoad": True,
        "StandardOutPath": str(GUNLUK),
        "StandardErrorPath": str(GUNLUK),
        "ProcessType": "Background",
    })
    if tamam:
        print("Mac boşta uyumayacak; site 2 dakikada bir denetlenip takılırsa yeniden başlatılacak.")
        print(f"Olaylar: {GUNLUK}")
    return tamam


def kaldir():
    for etiket in (NOBET_ETIKET, UYANIK_ETIKET):
        plist = AJANLAR / f"{etiket}.plist"
        _launchctl("bootout", f"gui/{os.getuid()}", str(plist))
        if plist.exists():
            plist.unlink()
    print("Uyanık tutma ve nöbetçi kapatıldı.")


def main():
    argumanlar = sys.argv[1:]
    if "--kur" in argumanlar:
        kur()
    elif "--kaldir" in argumanlar:
        kaldir()
    else:
        denetle()


if __name__ == "__main__":
    main()
