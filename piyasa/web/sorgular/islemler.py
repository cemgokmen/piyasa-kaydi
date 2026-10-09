"""İşlem listesi sayfası: filtreler, sıralama, sayfalama."""

from piyasa.analiz import cakisma
from piyasa.kayitlar import islem_hazirla
from piyasa.kurallar import TEMIZ
from piyasa.web.sorgular.ortak import (
    DONEMLER,
    KAYNAKLAR,
    OZET_SUTUNLARI,
    ROLLER,
    SAYFA_BOYUTU,
    SIRALAMALAR,
    baglanti,
    gun_once,
)


def _filtre(arama, islem, donem, kaynak, rol="hepsi"):
    kosullar = [TEMIZ]
    parametreler = []

    if ROLLER.get(rol, ROLLER["hepsi"])[1]:
        kosullar.append(ROLLER[rol][1])

    if islem in ("buy", "sell"):
        kosullar.append("action = ?")
        parametreler.append(islem)

    kaynak_kosulu = KAYNAKLAR[kaynak][1]
    if kaynak_kosulu:
        kosullar.append(kaynak_kosulu)

    kosullar.append("disclosed_date >= ?")
    parametreler.append(gun_once(DONEMLER[donem][1]))

    if arama:
        kosullar.append(
            "(ticker LIKE ? OR person LIKE ? OR company LIKE ? OR asset_name LIKE ?)"
        )
        parametreler.extend([f"%{arama}%"] * 4)

    return " WHERE " + " AND ".join(kosullar), parametreler


def islem_listesi(arama, islem, donem, kaynak, sira, sayfa, rol="hepsi"):
    """Filtreli, sayfalı işlem listesi ve filtrenin özeti."""
    where, parametreler = _filtre(arama, islem, donem, kaynak, rol)
    with baglanti() as conn:
        ozet = dict(conn.execute(
            f"SELECT {OZET_SUTUNLARI} FROM transactions{where}", parametreler
        ).fetchone())
        satirlar = conn.execute(
            f"SELECT * FROM transactions{where} ORDER BY {SIRALAMALAR[sira][1]} "
            "LIMIT ? OFFSET ?",
            parametreler + [SAYFA_BOYUTU, (sayfa - 1) * SAYFA_BOYUTU],
        ).fetchall()
    return cakisma.isaretle([islem_hazirla(s) for s in satirlar]), ozet
