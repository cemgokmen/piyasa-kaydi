"""Kaynak kuralları, sınama, tezin deneyi; yeni göstergeler, formasyonlar ve Dow okuması (internetsiz)."""

import numpy as np
import pandas as pd
import pytest

from piyasa.analiz import teknik
from piyasa.analiz.ajan import KURALLAR, Baglam, deney, kanit, okuma, sinama
from piyasa.analiz.destek_direnc import bolgeleri_hesapla
from piyasa.analiz.teknik import cizgiler, egilim
from piyasa.analiz.teknik.gostergeler import gostergeler
from tests.test_analiz_raporu import sahte_ohlcv


def _kapanistan(kapanis, hacim=None):
    k = np.asarray(kapanis, dtype=float)
    tarih = pd.bdate_range(end="2026-11-03", periods=len(k))
    return pd.DataFrame({"Open": k, "High": k * 1.002, "Low": k * 0.998, "Close": k,
                         "Volume": np.full(len(k), 1e6) if hacim is None else hacim}, index=tarih)


def _parcali(*duraklar, adim=12):
    return np.concatenate([np.linspace(a, b, adim, endpoint=False) for a, b in zip(duraklar, duraklar[1:], strict=False)] + [[duraklar[-1]]])


# ---------------------------------------------------------------------------
# Göstergeler
# ---------------------------------------------------------------------------

def test_yeni_gostergeler_elle_hesaba_uyar():
    df = _kapanistan(np.arange(100, 140, dtype=float))
    assert teknik.momentum_orani(df["Close"], 10).iloc[-1] == pytest.approx(139 / 129 * 100)
    # Düz yükselişte bütün yol net harekettir: 28 kapanış arası 27 adım, toplam yol 28 adım
    assert teknik.vhf(df["Close"], 28).iloc[-1] == pytest.approx(27 / 28)
    # Kapanış en yüksek değere çok yakın: %R sıfıra yakın, aşırı alım
    assert teknik.williams_r(df).iloc[-1] > -20
    assert teknik.cci(df, 20).iloc[-1] > 100
    testere = _kapanistan([100, 101] * 30)
    assert teknik.vhf(testere["Close"], 28).iloc[-1] < 0.1


# ---------------------------------------------------------------------------
# Kurallar: bu testler sonradan eklenen her kaynağı da kapsar
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kimlik", sorted(KURALLAR))
def test_kural_gelecegi_gormez(kimlik):
    """Seri kesilse de geçmiş sinyaller değişmemeli; değişiyorsa kural geleceği görüyordur."""
    df = sahte_ohlcv(gun=500, tohum=11)
    tam = KURALLAR[kimlik].fonksiyon(Baglam(df, gostergeler(df)))
    for kes in (300, 400):
        parca = df.iloc[:kes]
        kisa = KURALLAR[kimlik].fonksiyon(Baglam(parca, gostergeler(parca)))
        ilk = 260    # uzun pencereli göstergelerin başlangıcı aynı hesaplanır
        fark = (kisa.iloc[ilk:kes - 1] != 0) & (kisa.iloc[ilk:kes - 1] != tam.iloc[ilk:kes - 1])
        assert not fark.any(), f"{kimlik}: {list(fark[fark].index[:3])}"


@pytest.mark.parametrize("kimlik", sorted(KURALLAR))
def test_kural_bicimi(kimlik):
    r = KURALLAR[kimlik]
    df = sahte_ohlcv(gun=400)
    s = r.fonksiyon(Baglam(df, gostergeler(df)))
    assert len(s) == len(df) and set(np.unique(s.to_numpy())) <= {-1.0, 0.0, 1.0}
    assert r.kaynak.atif and r.sayfa and r.al and r.sat


def test_kural_kaynak_notu_depoda():
    from pathlib import Path
    kok = Path(__file__).resolve().parent.parent
    for r in KURALLAR.values():
        assert (kok / r.kaynak.notlar).exists(), r.kaynak.notlar


# ---------------------------------------------------------------------------
# Sınama
# ---------------------------------------------------------------------------

def _evren(adet=40, gun=700):
    return {f"H{i}": sahte_ohlcv(gun=gun, egim=0.0003, tohum=100 + i) for i in range(adet)}


def test_sinama_gelecegi_bilen_kurali_bulur_rastgeleyi_bulmaz():
    from piyasa.analiz.ajan.kural import Kaynak, Kural
    k = Kaynak("t", "T", "T", "analiz_ajani/README.md")

    def kahin(b):
        ileri = b.df["Close"].shift(-11) / b.df["Close"].shift(-1) - 1
        return ((ileri > 0.03).astype(float) - (ileri < -0.03).astype(float)).fillna(0.0)

    def rastgele(b):
        rng = np.random.default_rng(int(b.df["Close"].iloc[0] * 1000) % 2**32)
        return pd.Series(rng.choice([0.0, 1.0, -1.0], len(b.df), p=[0.9, 0.05, 0.05]), index=b.df.index)

    kurallar = {"kahin": Kural("kahin", "K", k, "1", "trend", 10, "a", "s", kahin),
                "rastgele": Kural("rastgele", "R", k, "1", "trend", 10, "a", "s", rastgele)}
    s = sinama.sina(_evren(), kurallar)
    assert s["kahin"]["al"]["kanit"] == "calisiyor" and s["kahin"]["sat"]["kanit"] == "calisiyor"
    assert s["kahin"]["al"]["ortalama"] > 0.02
    assert s["rastgele"]["al"]["kanit"] in ("sans", "zayif") and s["rastgele"]["sat"]["kanit"] in ("sans", "zayif")
    assert abs(s["rastgele"]["al"]["ortalama"]) < 0.01


def test_okuma_yalnizca_kanitli_kurala_oy_verir():
    df = sahte_ohlcv(gun=600, tohum=21)
    g = gostergeler(df)
    b = Baglam(df, g)
    aktif = {k: r.fonksiyon(b).iloc[-r.gecerlilik:] for k, r in KURALLAR.items()}
    aktif = {k: s[s != 0] for k, s in aktif.items() if (s != 0).any()}
    assert aktif, "sahte veride en az bir güncel sinyal bekleniyor"
    hepsi_sans = {k: {"al": {"kanit": "sans"}, "sat": {"kanit": "sans"}} for k in KURALLAR}
    sonuc = okuma.oku(df, g, hepsi_sans)
    assert sonuc["oy"] == 0 and sonuc["kanitli"] == 0 and len(sonuc["sinyaller"]) == len(aktif)
    hepsi_iyi = {k: {"al": {"kanit": "calisiyor"}, "sat": {"kanit": "calisiyor"}} for k in KURALLAR}
    sonuc = okuma.oku(df, g, hepsi_iyi)
    assert sonuc["kanitli"] == len(aktif)
    assert sonuc["oy"] == sum(int(s.iloc[-1]) for s in aktif.values())
    assert okuma.oku(df, g, {})["kanitli"] == 0     # sınanmamış kural oy veremez


# ---------------------------------------------------------------------------
# Deney
# ---------------------------------------------------------------------------

def test_deney_komisyon_ve_faiz_elle_hesaba_uyar(monkeypatch):
    df = _kapanistan(np.full(100, 100.0))
    bas, bit = df.index[10], df.index[-1]
    # Sinyal yok: para baştan sona faizde
    monkeypatch.setattr(deney, "_sinyaller", lambda f: {"A": pd.Series(0, index=df.index)})
    p = deney.portfoy({"A": df}, bas, bit, komisyon=0.01)
    assert p["islem"] == 0 and p["hissede_kalma"] == 0
    assert p["getiri"] == pytest.approx((1 + deney.gunluk_faiz(pd.DatetimeIndex(df.loc[bas:bit].index))).prod() - 1)
    # Bir AL, bir SAT, düz fiyat, faizsiz: yalnızca iki komisyon kaybı
    s = pd.Series(0, index=df.index)
    s.iloc[20], s.iloc[50] = 1, -1
    monkeypatch.setattr(deney, "_sinyaller", lambda f: {"A": s})
    p = deney.portfoy({"A": df}, bas, bit, komisyon=0.01, faizli=False)
    assert p["islem"] == 2 and p["getiri"] == pytest.approx(0.99 ** 2 - 1)


def test_deney_sinyalden_sonraki_gun_islem_yapar(monkeypatch):
    k = np.full(60, 100.0)
    k[31:] = 200.0                      # Sinyal 30. gün kapanışında; sıçrama ertesi gün açılışa kadar yansımaz
    df = _kapanistan(k)
    df["Open"] = df["Close"]
    s = pd.Series(0, index=df.index)
    s.iloc[30] = 1
    monkeypatch.setattr(deney, "_sinyaller", lambda f: {"A": s})
    p = deney.portfoy({"A": df}, df.index[5], df.index[-1], komisyon=0, faizli=False)
    assert p["getiri"] == pytest.approx(0.0)    # 200'den alındı, 200'de bitti: sıçramayı yakalamak geleceği görmek olurdu


def test_kanit_hesabi_ve_gerekli(monkeypatch, tmp_path):
    monkeypatch.setattr(kanit, "DOSYA", tmp_path / "k.json")
    monkeypatch.setattr(kanit, "_bellek", {"veri": {}, "dosya": 0.0})
    assert kanit.gerekli()
    f = _evren(adet=25, gun=800)
    e = sahte_ohlcv(gun=800, egim=0, tohum=5)["Close"]
    v = kanit.hesapla(f, e)
    assert set(v["kurallar"]) == set(KURALLAR) and v["deney"][0]["tez"]["hisse"] == 25
    kanit._yaz(v)
    assert kanit.oku()["hisse"] == 25 and not kanit.gerekli()
    # Yeni kural eklenince hemen yeniden sınanır
    monkeypatch.setitem(KURALLAR, "yeni.kural", KURALLAR["altay.stokastik"])
    assert kanit.gerekli()


# ---------------------------------------------------------------------------
# Trend çizgisi, formasyon, Dow, eğilim, destek/direnç
# ---------------------------------------------------------------------------

def test_trend_cizgisi_kucuk_delmede_bozulmaz_buyuk_delmede_kirilir():
    from piyasa.analiz.teknik.yapi import zigzag_teyitli
    tepki = _parcali(100, 120, 105, 130, 115, 140, 125)
    # Çizginin yaklaşık %1 altında tek kapanış, sonra yukarı: çizgi bozulmaz
    df = _kapanistan(np.concatenate([tepki, np.linspace(126, 135, 10), [128.0], np.linspace(135, 145, 6)]))
    n, _ = zigzag_teyitli(df, pd.Series(2.0, index=df.index))
    cz = [c for c in cizgiler.trend_cizgileri(df, n) if c["tur"] == "destek"]
    assert cz and all(c["kirilis"] is None for c in cz)
    # Çizgi altına %5 düşüş: kırılır
    df2 = _kapanistan(np.concatenate([tepki, np.linspace(125, 90, 12)]))
    n, _ = zigzag_teyitli(df2, pd.Series(2.0, index=df2.index))
    assert any(c["kirilis"] is not None and c["yon"] == -1 for c in cizgiler.trend_cizgileri(df2, n))


def test_obo_teyit_ve_hedef():
    from piyasa.analiz.teknik.yapi import zigzag_teyitli
    # Sol omuz 120, baş 140, sağ omuz 120, boyun 100; ardından %5'in ötesine kırılış
    k = np.concatenate([_parcali(90, 120, 100, 140, 100, 120, 110, 100), np.linspace(100, 92, 6)])
    df = _kapanistan(k)
    a = pd.Series(2.0, index=df.index)
    n, _ = zigzag_teyitli(df, a)
    f = [x for x in cizgiler.klasik_formasyonlar(df, n, a) if x["kod"] == "obo"]
    assert f and f[-1]["durum"] == "teyitli" and f[-1]["kirilis_yon"] == -1
    assert f[-1]["hedef"] < f[-1]["kirilis_fiyat"]
    assert f[-1]["yukseklik"] <= 50 * 1.01       # baş-boyun ve önceki hareketin küçüğü


def test_ters_obo_hacimsizse_teyitsiz_hacimliyse_teyitli():
    from piyasa.analiz.teknik.yapi import zigzag_teyitli
    k = np.concatenate([_parcali(130, 100, 120, 80, 120, 100, 110, 120), np.linspace(120, 130, 6)])

    def sonuc(kat):
        h = np.full(len(k), 1e6)
        h[-6:] = 1e6 * kat
        df = _kapanistan(k, h)
        a = pd.Series(2.0, index=df.index)
        n, _ = zigzag_teyitli(df, a)
        return [x for x in cizgiler.klasik_formasyonlar(df, n, a) if x["kod"] == "tobo"][-1]

    assert sonuc(1.0)["durum"] == "hacimsiz"
    assert sonuc(2.0)["durum"] == "teyitli" and sonuc(2.0)["kirilis_yon"] == 1


def test_olusan_formasyon_olay_uretmez():
    from piyasa.analiz.teknik.yapi import zigzag_teyitli
    df = _kapanistan(np.concatenate([_parcali(90, 120, 100, 140, 100, 120, 110), np.full(2, 110.0)]))
    a = pd.Series(2.0, index=df.index)
    n, _ = zigzag_teyitli(df, a)
    f = [x for x in cizgiler.klasik_formasyonlar(df, n, a) if x["kod"] == "obo"]
    assert f and f[-1]["durum"] == "olusuyor"
    assert not cizgiler.formasyon_olaylari(f, len(df)).any()


def test_dow_okumasi():
    yuk = _kapanistan(_parcali(100, 150, 125, 190, 160, 240, 205, 300))
    d = teknik.dow_okumasi(yuk, pd.Series(2.0, index=yuk.index))
    assert d["birincil"] == "yukselis" and d["yon"] == 1
    dus = _kapanistan(_parcali(300, 205, 240, 160, 190, 125, 150, 100))
    assert teknik.dow_okumasi(dus, pd.Series(2.0, index=dus.index))["birincil"] == "dusus"
    # %50 geri alış: olağan ikincil hareket
    duzeltme = _kapanistan(np.concatenate([_parcali(100, 150, 125, 190, 160, 240), np.linspace(240, 200, 12)]))
    d = teknik.dow_okumasi(duzeltme, pd.Series(2.0, index=duzeltme.index))
    assert d["birincil"] == "yukselis" and 1 / 3 <= d["ikincil"] <= 2 / 3
    assert "olağan ikincil" in teknik.dow_metni(d)
    yatay = _kapanistan(100 + np.sin(np.arange(60)))
    assert teknik.dow_okumasi(yatay, pd.Series(0.5, index=yatay.index))["cizgi_gun"] >= 15


def test_run_testi_ve_seri_korelasyon():
    rng = np.random.default_rng(1)
    assert abs(egilim.run_testi(rng.normal(0, 1, 2000))["z"]) < 2.5
    assert egilim.run_testi(np.r_[np.ones(50), -np.ones(50)] * 1.0)["z"] < -5       # uzun tek yönlü dizi
    assert egilim.run_testi(np.tile([1.0, -1.0], 50))["z"] > 5                      # sürekli yön değiştiren
    # k günlük getiriler kapanıştan doğru türetiliyor
    k = np.exp(np.cumsum(np.tile([0.01] * 5 + [-0.01] * 5, 30)))
    assert egilim.seri_korelasyon(k, 5)["r"] < -0.9
    assert egilim.trend_egilimi(sahte_ohlcv(gun=700)["Close"])["kod"] in ("trendli", "rassal", "donuslu")


def test_destek_direnc_rol_degisimi():
    df = sahte_ohlcv(gun=800, tohum=4)
    s = bolgeleri_hesapla(df)
    for b in s["bolgeler"]:
        assert isinstance(b["rol_degisti"], bool) and b["bolgede_gun"] >= 0
    testler = [{"tutundu": False, "yon": "alttan"}]
    from piyasa.analiz.destek_direnc import bolge_ozellikleri
    assert bolge_ozellikleri(df, 100.0, 1.0, testler, "destek")["rol_degisti"] is True
    assert bolge_ozellikleri(df, 100.0, 1.0, testler, "direnç")["rol_degisti"] is False
    # Kırılıştan sonra yeni rolünde sınanmışsa artık "yeni" rol değişimi değildir
    assert bolge_ozellikleri(df, 100.0, 1.0, [*testler, {"tutundu": True, "yon": "ustten"}], "destek")["rol_degisti"] is False


def _formasyon(k, kod, hacim=None):
    from piyasa.analiz.teknik.yapi import zigzag_teyitli
    df = _kapanistan(k, hacim)
    a = pd.Series(2.0, index=df.index)
    n, _ = zigzag_teyitli(df, a)
    return [x for x in cizgiler.klasik_formasyonlar(df, n, a) if x["kod"] == kod]


def test_ucgen_hedefi_karsi_kenarin_paralelidir():
    # Tepeler 120'de yatay, dipler 100'den 110'a yükseliyor: yükselen üçgen
    k = np.concatenate([_parcali(90, 120, 100, 120, 110, 119, adim=12), np.linspace(119, 125, 3)])
    h = np.full(len(k), 1e6)
    h[-3:] = 3e6
    f = _formasyon(k, "yukselen_ucgen", h)[-1]
    assert f["durum"] == "teyitli" and f["kirilis_yon"] == 1
    # Alt kenarın eğimi günde ~10/24; paralel ilk tepeden (12. gün, 120 × 1,002) başlar
    egim = (f["alt"](100) - f["alt"](0)) / 100
    assert f["hedef"] == pytest.approx(f["ust"](12) + egim * (f["kirilis"] - 12), rel=0.02)
    # Yükseklik yöntemi (kırılış + yükseklik) başka sonuç verir
    assert abs(f["hedef"] - (f["kirilis_fiyat"] + f["yukseklik"])) > 1


def test_kama_yonu_ve_hedefi_sap_boyu():
    k = np.concatenate([_parcali(70, 60, 140, 110, 128, 104, 115, adim=12), np.linspace(115, 130, 4)])
    h = np.full(len(k), 1e6)
    h[-4:] = 3e6
    f = _formasyon(k, "alcalan_kama", h)
    assert f, "alçalan kama bulunmalı"
    assert f[-1]["kirilis_yon"] == 1 and f[-1]["durum"] == "teyitli"
    assert f[-1]["yukseklik"] > 60          # 60'tan 140'a giden sap


def test_bayrakta_hacim_dusmezse_formasyon_bozulur():
    k = np.concatenate([np.linspace(110, 100, 6), np.linspace(100, 140, 8), np.linspace(140, 132, 4), np.full(3, 133.0), np.linspace(134, 150, 3)])

    def durum(bayrak_kat):
        h = np.full(len(k), 1e6)
        h[6:14] = 3e6
        h[14:-3] = 3e6 * bayrak_kat
        h[-3:] = 5e6
        return _formasyon(k, "bayrak", h)[-1]["durum"]

    assert durum(0.3) == "teyitli"
    assert durum(1.5) == "bozuldu"


def test_kanal_paraleli_karsi_uctan_gecer():
    from piyasa.analiz.teknik.yapi import zigzag_teyitli
    df = _kapanistan(_parcali(100, 130, 110, 140, 120, 150, 130))
    n, _ = zigzag_teyitli(df, pd.Series(2.0, index=df.index))
    c = [z for z in cizgiler.trend_cizgileri(df, n) if z["tur"] == "destek" and z["kanal"]]
    assert c
    arada = [p for p in n if p[2] == "tepe" and c[0]["n1"][0] < p[0] < c[0]["n2"][0]][0]
    assert c[0]["cizgi"](arada[0]) + c[0]["kanal"] == pytest.approx(arada[1])


def test_kaynaklarin_ikisi_de_yuklu():
    assert {r.kaynak.kod for r in KURALLAR.values()} >= {"altay1997", "gedik2021"}


# ---------------------------------------------------------------------------
# Dönemler, çakışan getiriler, maliyet
# ---------------------------------------------------------------------------

def test_donem_izleme_suresi_tasan_sinyali_saymaz():
    from piyasa.analiz.ajan.donemler import ESKI, OLAGAN, SOK
    assert OLAGAN.icerir(pd.Timestamp("2025-01-06"), pd.Timestamp("2025-02-06"))
    assert not OLAGAN.icerir(pd.Timestamp("2026-02-20"), pd.Timestamp("2026-03-20"))     # çıkışı savaşa taşıyor
    assert not OLAGAN.icerir(pd.Timestamp("2020-10-01"), pd.Timestamp("2020-11-20"))
    assert SOK.icerir(pd.Timestamp("2026-10-01"), pd.Timestamp("2026-10-20"))
    assert ESKI.icerir(pd.Timestamp("2015-01-05"), pd.Timestamp("2015-03-05"))


def test_donemli_sinama_yalnizca_o_donemin_sinyalini_sayar():
    from piyasa.analiz.ajan.donemler import Donem
    f = _evren(adet=20, gun=500)
    tarihler = next(iter(f.values())).index
    orta = tarihler[250]
    ilk = Donem("a", "A", str(tarihler[0].date()), str(orta.date()), "")
    son = Donem("b", "B", str(tarihler[251].date()), None, "")
    kurallar = {"altay.stokastik": KURALLAR["altay.stokastik"]}
    hepsi = sinama.sina(f, kurallar)["altay.stokastik"]["al"]["sinyal"]
    a = sinama.sina(f, kurallar, donem=ilk)["altay.stokastik"]["al"]["sinyal"]
    b = sinama.sina(f, kurallar, donem=son)["altay.stokastik"]["al"]["sinyal"]
    assert a + b <= hepsi and a > 0 and b > 0
    assert a + b >= hepsi - 40      # yalnızca sınıra taşanlar düşer


def test_cakisan_getiride_p_degeri_buyur():
    rng = np.random.default_rng(3)
    # 12 haftalık hareketli toplam: ardışık gözlemler güçlü bağlı, sıradan t testi fazla iyimser
    x = pd.Series(rng.normal(0.002, 0.02, 400)).rolling(12).mean().dropna().to_numpy()
    assert sinama._cakisma_p(x, 12) > sinama._cakisma_p(x, 0)
    assert sinama._cakisma_p(np.zeros(30), 4) == 1.0


def test_maliyeti_karsilamayan_sonuc_kanit_sayilmaz():
    s = {"n": 100, "p": 0.001, "p_duzeltilmis": 0.01, "ortalama": 0.002, "ilk_yari": 0.002, "ikinci_yari": 0.002}
    assert sinama._karar(s) == "maliyet"
    assert sinama._karar({**s, "ortalama": 0.02}) == "calisiyor"


def test_onceki_yillarda_ters_cikan_kural_oy_vermez():
    from piyasa.analiz.ajan import kanit, okuma
    olagan = {"x": {"al": {"ortalama": 0.02, "kanit": "zayif"}, "sat": {"ortalama": 0.01}}}
    eski = {"x": {"al": {"ortalama": -0.01, "n": 50, "p": 0.3}, "sat": {"ortalama": 0.02, "n": 50, "p": 0.01}}}
    kanit._tekrar_isle(olagan, eski)
    assert olagan["x"]["al"]["tekrar"] == "tekrarlamadi" and olagan["x"]["sat"]["tekrar"] == "tekrarladi"
    df = sahte_ohlcv(gun=600, tohum=21)
    g = gostergeler(df)
    b = Baglam(df, g)
    aktif = {k: r.fonksiyon(b).iloc[-r.gecerlilik:] for k, r in KURALLAR.items()}
    k, s = next((k, s[s != 0]) for k, s in aktif.items() if (s != 0).any())
    taraf = "al" if s.iloc[-1] > 0 else "sat"
    tutan = okuma.oku(df, g, {k: {taraf: {"kanit": "calisiyor", "tekrar": "tekrarladi"}}})
    tutmayan = okuma.oku(df, g, {k: {taraf: {"kanit": "calisiyor", "tekrar": "tekrarlamadi"}}})
    assert tutan["kanitli"] == 1 and tutmayan["kanitli"] == 0


def test_seans_acikken_bugunku_sinyal_gecici_ve_oysuz():
    from piyasa.analiz.ajan import okuma
    df = sahte_ohlcv(gun=600, tohum=21)
    df.index = pd.date_range(end=pd.Timestamp.today().normalize(), periods=len(df), freq="D")
    g = gostergeler(df)
    b = Baglam(df, g)
    k = next((k for k, r in KURALLAR.items() if r.fonksiyon(b).iloc[-1] != 0), None)
    if k is None:
        pytest.skip("bu veride bugün sinyal yok")
    taraf = "al" if KURALLAR[k].fonksiyon(b).iloc[-1] > 0 else "sat"
    s = okuma.oku(df, g, {k: {taraf: {"kanit": "calisiyor"}}}, seans_acik=True)
    satir = next(x for x in s["sinyaller"] if x["kimlik"] == k)
    assert satir["gecici"] and s["kanitli"] == 0


def test_bes_gosterge_ilk_gun_sinyal_verir_ve_matriks_yuklu():
    assert {r.kaynak.kod for r in KURALLAR.values()} >= {"matriks2020"}
    df = sahte_ohlcv(gun=800, tohum=9)
    s = KURALLAR["matriks.bes_gosterge"].fonksiyon(Baglam(df, gostergeler(df)))
    assert (s != 0).any()
    assert not ((s != 0) & (s.shift(1) != 0)).any()     # durum değil, başlangıç anı


def test_gecikmeli_kesisim_iki_gun_sonra_gelir():
    df = sahte_ohlcv(gun=500, tohum=4)
    b = Baglam(df, gostergeler(df))
    hemen = KURALLAR["matriks.ema_5_14"].fonksiyon(b)
    gecik = KURALLAR["matriks.ema_5_14_gecikmeli"].fonksiyon(b)
    assert hemen.shift(2).fillna(0.0).equals(gecik)
