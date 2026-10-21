from app.db import SessionLocal
from app.models import Company
from app.builder import build_and_compile_matrix, PreviewRequest, preview_template
import pytest

def test_autotag_proportional_allocation():
    db = SessionLocal()
    try:
        # Company 2 (BMS)
        bms = db.query(Company).filter(Company.id == 2).first()
        assert bms is not None

        # Build payload with:
        # R1: Pendapatan (TW_PENDAPATAN JASA)
        # K32: Total Pendapatan Kapal Terpilih (TPJ_TERPILIH)
        # R36: Proportional TPJ (R1 / K32)
        # R39: Biaya Gaji (Auto TAG) with is_proportional=True and multiplier_row='R36'
        # R50: Formula summing R39 (R50 = R39)
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
                    "expression": "TW_Biaya Gaji, jamsostek, THR dan Bonus",
                    "auto_expand_coa": True,
                    "is_proportional": True,
                    "multiplier_row": "R36"
                },
                {
                    "id": 5,
                    "code": "R50",
                    "type": "formula",
                    "label": "Total Biaya Gaji Terhitung",
                    "expression": "R50 = R39"
                }
            ]
        )

        res = preview_template(payload, db=db)
        assert res["status"] == "success"
        body = res["data"]["body"]
        row_map = {r["name"]: r for r in body}

        # Verify R1 and R36
        r1 = row_map["R1"]
        r36 = row_map["R36"]
        r39 = row_map["R39"]
        r50 = row_map["R50"]

        # Check Q3 values for vessel 1 (cell index 2)
        v1_prop = r36["cells"][2]["val"]
        assert v1_prop > 0 and v1_prop <= 1.0

        # R39 parent should be multiplied by v1_prop
        raw_r39 = r39["cells"][2]["raw_val"]
        assert raw_r39 > 0
        expected_allocated_v1 = raw_r39 * v1_prop
        assert round(r39["cells"][2]["val"], 2) == round(expected_allocated_v1, 2)

        # Child COA rows (e.g. 7000011100) should also be multiplied by v1_prop
        child_7000 = next(r for r in body if r.get("parent_code") == "R39" and "7000011100" in r.get("label", ""))
        assert child_7000 is not None
        raw_child = child_7000["cells"][2]["raw_val"]
        assert raw_child > 0
        expected_child = raw_child * v1_prop
        assert round(child_7000["cells"][2]["val"], 2) == round(expected_child, 2)

        # Formula R50 referencing R39 should equal allocated R39
        assert round(r50["cells"][2]["val"], 2) == round(expected_allocated_v1, 2)

        # Total Kapal column for Q3 (index 12: 5 cols for V1, 5 cols for V2, total is index 10,11,12...)
        # Find index of Total Kapal Q3 in headers
        header1 = res["data"]["header"][1]
        total_q3_idx = None
        for idx, col in enumerate(header1):
            if col.get("period") == "q3" and "total" in col.get("vessel_name", "").lower():
                total_q3_idx = idx
                break

        if total_q3_idx is not None:
            v1_q3_val = r39["cells"][2]["val"]
            v2_q3_val = r39["cells"][7]["val"]
            tot_q3_val = r39["cells"][total_q3_idx]["val"]
            assert round(tot_q3_val, 2) == round(v1_q3_val + v2_q3_val, 2)
    finally:
        db.close()
