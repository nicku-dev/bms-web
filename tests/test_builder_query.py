import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db import SessionLocal
from app.builder import get_available_queries, preview_template, PreviewRequest

def test_builder_queries():
    queries = get_available_queries()
    codes = [q["code"] for q in queries]
    assert "KAPASITAS" in codes
    assert "TRIP" in codes
    assert "TPJ_SEMUA" in codes

def test_builder_preview_with_kpi_queries():
    db = SessionLocal()
    try:
        payload = PreviewRequest(
            company_id=2,
            year="2026",
            vessels=[{"id": 75, "name": "TB.BMS 004/TK.BMS 004A"}],
            rows=[
                {"id": 1, "code": "K1", "type": "query", "label": "Kapasitas Kapal (DWT)", "expression": "KAPASITAS"},
                {"id": 2, "code": "T1", "type": "query", "label": "Jumlah Trip Kapal", "expression": "TRIP"},
                {"id": 3, "code": "R1", "type": "data", "label": "PENDAPATAN JASA", "expression": "TW_PENDAPATAN JASA"},
                {"id": 4, "code": "R2", "type": "formula", "label": "Pendapatan per DWT Kapasitas", "expression": "R1 / K1"},
                {"id": 5, "code": "R3", "type": "formula", "label": "Pendapatan per Trip", "expression": "R1 / T1"},
                {"id": 6, "code": "R4", "type": "formula", "label": "Pendapatan per DWT per Trip", "expression": "R1 / (K1 * T1)"}
            ]
        )
        
        data = preview_template(payload, db=db)
        assert data["status"] == "success"
        
        body = data["data"]["body"]
        row_map = {r["name"]: r for r in body}
        
        # 1. Kapasitas verification: static YTD (5500.0)
        k1 = row_map["K1"]
        assert k1["cells"][0]["val"] == 5500.0 # Q1
        assert k1["cells"][1]["val"] == 5500.0 # Q2
        assert k1["cells"][2]["val"] == 5500.0 # Q3
        assert k1["cells"][3]["val"] == 5500.0 # Q4
        assert k1["cells"][4]["val"] == 5500.0 # YTD MUST BE STATIC (NOT 22000.0)
        
        # 2. Trip verification: Q3=3, Q4=1, YTD=4
        t1 = row_map["T1"]
        assert t1["cells"][2]["val"] == 3.0 # Q3
        assert t1["cells"][3]["val"] == 1.0 # Q4
        assert t1["cells"][4]["val"] == 4.0 # YTD
        
        # 3. Revenue per DWT verification (R1 / K1)
        r2 = row_map["R2"]
        q3_rev = row_map["R1"]["cells"][2]["val"]
        assert q3_rev > 0
        expected_ratio = round(q3_rev / 5500.0, 2)
        assert round(r2["cells"][2]["val"], 2) == expected_ratio
        
        # 4. Zero division handling: Q1 for R1 / T1 should be 0.0 (displayed as '-') without crashing
        r3 = row_map["R3"]
        assert r3["cells"][0]["val"] == 0.0
        assert r3["cells"][0]["val_r"] == "-"
    finally:
        db.close()
