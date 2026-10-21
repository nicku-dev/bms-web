import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db import SessionLocal
from app.models import Company
from app.engine import ReportEngine
from app.builder import preview_template, PreviewRequest

def test_engine_tpj_kapal_terpilih():
    db = SessionLocal()
    try:
        comp = db.query(Company).filter(Company.id == 2).first()
        engine = ReportEngine(comp.target_db_name)
        
        # 1. Test single vessel by name
        df_single = engine.get_kpi_tpj_kapal_terpilih(2026, vessel_names=['TB.BMS 004/TK.BMS 004A'])
        assert not df_single.empty
        assert 'quarter' in df_single.columns
        assert 'value' in df_single.columns
        q3_single = df_single[df_single['quarter'] == 3]['value'].iloc[0]
        assert round(q3_single, 2) == 7651793200.0

        # 2. Test multiple vessels
        df_multi = engine.get_kpi_tpj_kapal_terpilih(2026, vessel_names=['TB.BMS 004/TK.BMS 004A', 'TB.BMS 005/TK.BMS 005A'])
        assert not df_multi.empty
        q3_multi = df_multi[df_multi['quarter'] == 3]['value'].iloc[0]
        assert q3_multi >= q3_single

        # 3. Test empty vessel list (safe empty return)
        df_empty = engine.get_kpi_tpj_kapal_terpilih(2026, vessel_names=[])
        assert df_empty.empty
        assert list(df_empty.columns) == ['quarter', 'value']

        # 4. Test with 'Kapal - ' prefix auto-cleaning
        df_prefix = engine.get_kpi_tpj_kapal_terpilih(2026, vessel_names=['Kapal - TB.BMS 004/TK.BMS 004A'])
        assert not df_prefix.empty
        q3_prefix = df_prefix[df_prefix['quarter'] == 3]['value'].iloc[0]
        assert round(q3_prefix, 2) == round(q3_single, 2)

        engine.close()
    finally:
        db.close()


def test_builder_preview_with_tpj_terpilih_and_proportional():
    db = SessionLocal()
    try:
        payload = PreviewRequest(
            company_id=2,
            year="2026",
            vessels=[
                {"id": 75, "name": "TB.BMS 004/TK.BMS 004A"},
                {"id": 76, "name": "TB.BMS 005/TK.BMS 005A"}
            ],
            rows=[
                {
                    "id": 1,
                    "code": "R1",
                    "type": "data",
                    "label": "PENDAPATAN JASA",
                    "expression": "TW_PENDAPATAN JASA"
                },
                {
                    "id": 2,
                    "code": "Q_TPJT",
                    "type": "query",
                    "label": "Total Pendapatan Kapal Terpilih",
                    "expression": "TPJ_TERPILIH"
                },
                {
                    "id": 3,
                    "code": "F_PROP",
                    "type": "formula",
                    "label": "Proporsional Pendapatan Armada",
                    "expression": "R1 / Q_TPJT",
                    "is_percentage": True
                }
            ]
        )

        res = preview_template(payload, db=db)
        assert res["status"] == "success"
        body = res["data"]["body"]
        row_map = {r["name"]: r for r in body}

        # 1. Verify R1 (Pendapatan Jasa)
        r1 = row_map["R1"]
        q3_v1_rev = r1["cells"][2]["val"]
        assert q3_v1_rev == 7651793200.0

        # 2. Verify Q_TPJT (Total Pendapatan Kapal Terpilih)
        q_tpjt = row_map["Q_TPJT"]
        q3_tpjt_val = q_tpjt["cells"][2]["val"]
        assert q3_tpjt_val >= q3_v1_rev # Total is >= single vessel revenue

        # 3. Verify F_PROP (Proporsional formula)
        f_prop = row_map["F_PROP"]
        expected_prop = (q3_v1_rev / q3_tpjt_val) * 100.0
        assert " %" in f_prop["cells"][2]["val_r"]
        assert round(f_prop["cells"][2]["val"] * 100.0, 2) == round(expected_prop, 2)
    finally:
        db.close()


def test_builder_preview_with_gaji_tag_and_child_coa():
    db = SessionLocal()
    try:
        payload = PreviewRequest(
            company_id=2,
            year="2026",
            vessels=[
                {"id": 75, "name": "TB.BMS 004/TK.BMS 004A"},
                {"id": 76, "name": "TB.BMS 005/TK.BMS 005A"}
            ],
            rows=[
                {
                    "id": 1,
                    "code": "R1",
                    "type": "data",
                    "label": "PENDAPATAN JASA",
                    "expression": "TW_PENDAPATAN JASA"
                },
                {
                    "id": 2,
                    "code": "K32",
                    "type": "query",
                    "label": "Total Pendapatan Kapal Terpilih",
                    "expression": "TPJ_TERPILIH"
                },
                {
                    "id": 3,
                    "code": "R36",
                    "type": "formula",
                    "label": "Proportional TPJ",
                    "expression": "R1 / K32",
                    "is_percentage": True
                },
                {
                    "id": 4,
                    "code": "R39",
                    "type": "data",
                    "label": "Biaya Gaji, jamsostek, THR dan Bonus",
                    "expression": "TW_Biaya Gaji, jamsostek, THR dan Bonus"
                },
                {
                    "id": 5,
                    "code": "R39_1",
                    "type": "account",
                    "label": "7000011100 Biaya Gaji Karyawan",
                    "expression": "7000011100"
                },
                {
                    "id": 6,
                    "code": "R41",
                    "type": "formula",
                    "label": "Biaya Gaji Proporsional Kapal",
                    "expression": "R39 * R36"
                }
            ]
        )

        res = preview_template(payload, db=db)
        assert res["status"] == "success"
        body = res["data"]["body"]
        row_map = {r["name"]: r for r in body}

        # Verify R39 has company-wide salary for Q3
        r39 = row_map["R39"]
        q3_r39 = r39["cells"][2]["val"]
        assert round(q3_r39, 2) == 581866428.49

        # Verify child account R39_1 has specific account balance for Q3
        r39_1 = row_map["R39_1"]
        q3_child = r39_1["cells"][2]["val"]
        assert round(q3_child, 2) == 522133296.0

        # Verify R41 calculates proportional salary
        r41 = row_map["R41"]
        q3_r41 = r41["cells"][2]["val"]
        r36_val = row_map["R36"]["cells"][2]["val"]
        expected_r41 = q3_r39 * r36_val
        assert round(q3_r41, 2) == round(expected_r41, 2)
        assert q3_r41 > 0
    finally:
        db.close()

