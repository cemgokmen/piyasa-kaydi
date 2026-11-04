"""Mali oranlar: TSPAKB 2011'deki formüller."""

import pandas as pd
import pytest

from piyasa.analiz.temel_analiz import Tablolar, mali_oranlar


def test_mali_oranlar_kaynaktaki_formuller():
    yil = [pd.Timestamp("2024-12-31"), pd.Timestamp("2025-12-31")]
    bilanco = pd.DataFrame({
        yil[0]: {"Inventory": 20.0, "Accounts Receivable": 30.0, "Stockholders Equity": 80.0},
        yil[1]: {"Current Assets": 100.0, "Current Liabilities": 50.0, "Inventory": 40.0, "Other Current Assets": 10.0,
                 "Cash And Cash Equivalents": 15.0, "Total Non Current Assets": 120.0, "Stockholders Equity": 100.0,
                 "Total Non Current Liabilities Net Minority Interest": 60.0, "Total Liabilities Net Minority Interest": 110.0,
                 "Goodwill And Other Intangible Assets": 10.0, "Accounts Receivable": 50.0, "Total Assets": 220.0},
    })
    gelir = pd.DataFrame({
        yil[0]: {"Total Revenue": 300.0},
        yil[1]: {"Total Revenue": 400.0, "Cost Of Revenue": 180.0, "Pretax Income": 20.0, "Interest Expense": 24.0},
    })
    t = Tablolar(gelir, bilanco, pd.DataFrame({y: {} for y in yil}))
    o = mali_oranlar(t, lambda satirlar: t.b(satirlar))
    assert o["asit"] == pytest.approx((100 - 40 - 10) / 50)
    assert o["nakit_orani"] == pytest.approx(15 / 50)
    assert o["duran_devamli"] == pytest.approx(120 / 160)
    assert o["borc_maddi_ozk"] == pytest.approx(110 / 90)
    assert o["stok_gun"] == pytest.approx(360 * 30 / 180)      # ortalama stok 30
    assert o["alacak_gun"] == pytest.approx(360 * 40 / 400)    # ortalama alacak 40
    assert o["ekonomik_rant"] == pytest.approx(44 / 220)       # borcun maliyeti özkaynak getirisini aşıyor
    assert o["ozk_vergi_oncesi"] == pytest.approx(20 / 100)
