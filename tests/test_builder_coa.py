import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db import SessionLocal
from app.builder import get_accounts, preview_template, PreviewRequest

def test_builder_accounts_endpoint():
    db = SessionLocal()
    try:
        # 1. Fetch all accounts for Company 2 (BMS)
        all_accounts = get_accounts(company_id=2, tag_name=None, db=db)
        assert len(all_accounts) > 0
        codes = [a["code"] for a in all_accounts]
        assert "4000011000" in codes

        # 2. Fetch accounts filtered by tag TW_PENDAPATAN JASA
        tag_accounts = get_accounts(company_id=2, tag_name="TW_PENDAPATAN JASA", db=db)
        assert len(tag_accounts) > 0
        tag_codes = [a["code"] for a in tag_accounts]
        assert "4000011000" in tag_codes
        assert "5000092000" in tag_codes
    finally:
        db.close()

def test_builder_preview_with_coa_hierarchy():
    db = SessionLocal()
    try:
        payload = PreviewRequest(
            company_id=2,
            year="2026",
            vessels=[{"id": 75, "name": "TB.BMS 004/TK.BMS 004A"}],
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
                    "code": "R1_1",
                    "type": "account",
                    "label": "4000011000 Pendapatan Usaha Freight Charter Kapal",
                    "expression": "4000011000",
                    "style": "font-style: italic; text-indent: 2em;"
                },
                {
                    "id": 3,
                    "code": "R1_2",
                    "type": "account",
                    "label": "4000012000 Pendapatan Usaha - Time Charter Kapal",
                    "expression": "4000012000",
                    "style": "font-style: italic; text-indent: 2em;"
                },
                {
                    "id": 4,
                    "code": "R1_3",
                    "type": "account",
                    "label": "5000092000 Biaya Klaim Susut",
                    "expression": "5000092000",
                    "style": "font-style: italic; text-indent: 2em;"
                },
                {
                    "id": 5,
                    "code": "R2",
                    "type": "formula",
                    "label": "Rasio Child terhadap Parent",
                    "expression": "R1_1 / R1"
                }
            ]
        )

        res = preview_template(payload, db=db)
        assert res["status"] == "success"
        body = res["data"]["body"]
        row_map = {r["name"]: r for r in body}

        # 1. Verify parent row (PENDAPATAN JASA)
        r1 = row_map["R1"]
        q3_parent = r1["cells"][2]["val"]
        assert q3_parent == 7651793200.0
        assert r1["cells"][4]["val"] == 9279266900.0 # YTD

        # 2. Verify child account row (4000011000)
        r1_1 = row_map["R1_1"]
        assert r1_1["cells"][2]["val"] == 7651793200.0
        assert r1_1["cells"][4]["val"] == 9279266900.0 # YTD
        assert "font-style: italic" in r1_1["style"]

        # 3. Verify empty child accounts
        r1_2 = row_map["R1_2"]
        assert r1_2["cells"][2]["val"] == 0.0 or r1_2["cells"][2]["val_r"] == "-"

        # 4. Verify formula referencing child and parent
        r2 = row_map["R2"]
        # Since R1_1 == R1 in Q3, ratio is 1.0 (or 100%)
        assert r2["cells"][2]["val"] == 1.0
    finally:
        db.close()
