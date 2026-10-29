"""Nöbetçinin yeniden başlatma kararı."""

from piyasa import nobet


def test_her_sey_yolundaysa_sayaclar_sifirlanir():
    assert nobet.karar({"yerel": 1, "dis": 1}, True, True) == ({"yerel": 0, "dis": 0}, None)


def test_yerel_art_arda_yanit_vermezse_site_yeniden_baslar():
    durum, yeniden = nobet.karar({}, False, False)
    assert (durum, yeniden) == ({"yerel": 1, "dis": 0}, None)
    assert nobet.karar(durum, False, False) == ({"yerel": 0, "dis": 0}, nobet.SITE_ETIKET)


def test_yalnizca_dis_adres_kapaliysa_tunel_yeniden_baslar():
    durum, yeniden = nobet.karar({}, True, False)
    assert yeniden is None
    assert nobet.karar(durum, True, False) == ({"yerel": 0, "dis": 0}, nobet.TUNEL_ETIKET)
