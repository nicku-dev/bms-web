import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db import SessionLocal
from app.builder import preview_template, PreviewRequest

def test_builder_title_and_style_features():
    db = SessionLocal()
    try:
        payload = PreviewRequest(
            company_id=2,
            year="2026",
            vessels=[{"id": 75, "name": "TB.BMS 004/TK.BMS 004A"}],
            rows=[
                {
                    "id": 1,
                    "code": "T1",
                    "type": "title",
                    "label": "OPERASIONAL KAPAL",
                    "is_bold": True,
                    "bg_color": "#F8FAFC"
                },
                {
                    "id": 2,
                    "code": "H1",
                    "type": "query",
                    "label": "Kapasitas Tersembunyi (DWT)",
                    "expression": "KAPASITAS",
                    "is_hidden": True
                },
                {
                    "id": 3,
                    "code": "R1",
                    "type": "data",
                    "label": "PENDAPATAN JASA",
                    "expression": "TW_PENDAPATAN JASA",
                    "indent_level": 1,
                    "bg_color": "#FEF3C7"
                },
                {
                    "id": 4,
                    "code": "F1",
                    "type": "formula",
                    "label": "Pendapatan per DWT (Memakai Row Hidden H1)",
                    "expression": "R1 / H1",
                    "is_bold": True,
                    "indent_level": 2,
                    "bg_color": "#E2EFDA"
                }
            ]
        )

        res = preview_template(payload, db=db)
        assert res["status"] == "success"
        body = res["data"]["body"]
        row_map = {r["name"]: r for r in body}

        # 1. Title Row Verification
        t1 = row_map["T1"]
        assert t1["row_type"] == "title"
        assert "font-weight: bold" in t1["style"]
        assert t1["cells"][0]["val"] in (None, "") # No numeric calculations for titles
        assert t1["cells"][0]["val_r"] == ""

        # 2. Hidden Row Verification (Evaluated for formulas, but marked hidden)
        h1 = row_map["H1"]
        assert h1["is_hidden"] is True
        assert "display: none" in h1["style"]
        assert h1["cells"][2]["val"] == 5500.0 # Evaluated successfully!

        # 3. Indent and Background Color Verification on R1
        r1 = row_map["R1"]
        assert "text-indent: 1.5em" in r1["style"]
        assert "background-color: #FEF3C7" in r1["style"]
        assert r1["cells"][2]["val"] == 7651793200.0

        # 4. Formula using Hidden Row H1 and Style Verification
        f1 = row_map["F1"]
        assert "font-weight: bold" in f1["style"]
        assert "text-indent: 3.0em" in f1["style"]
        assert "background-color: #E2EFDA" in f1["style"]
        expected_ratio = round(7651793200.0 / 5500.0, 2)
        assert round(f1["cells"][2]["val"], 2) == expected_ratio
    finally:
        db.close()


def test_builder_percentage_formula():
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
                    "code": "H1",
                    "type": "query",
                    "label": "Kapasitas Kapal",
                    "expression": "KAPASITAS"
                },
                {
                    "id": 3,
                    "code": "F_PCT1",
                    "type": "formula",
                    "label": "Rasio Margin Pendapatan",
                    "expression": "(R1 * 0.25) / R1",
                    "is_percentage": True
                },
                {
                    "id": 4,
                    "code": "F_PCT2",
                    "type": "formula",
                    "label": "Rasio Margin dengan Pre-Multiplied 100",
                    "expression": "((R1 * 0.25) / R1) * 100",
                    "is_percentage": True
                }
            ]
        )

        res = preview_template(payload, db=db)
        assert res["status"] == "success"
        body = res["data"]["body"]
        row_map = {r["name"]: r for r in body}

        # Check F_PCT1 (raw ratio, compiler multiplies by 100 for display)
        f_pct1 = row_map["F_PCT1"]
        assert f_pct1.get("is_percentage") is True
        cell_pct1 = f_pct1["cells"][2] # Ship 1 TW1/Q1
        assert " %" in cell_pct1["val_r"]

        # Check F_PCT2 (formula has * 100, compiler smart-detects and avoids double scaling)
        f_pct2 = row_map["F_PCT2"]
        assert f_pct2.get("is_percentage") is True
        cell_pct2 = f_pct2["cells"][2]
        assert " %" in cell_pct2["val_r"]
        assert cell_pct1["val_r"] == cell_pct2["val_r"] # Both display the identical formatted percentage!

        # Check Total Kapal column is not a naive linear sum of percentages
        header_rows = res["data"].get("header", [])
        if header_rows:
            vessel_row = header_rows[0]
            total_cols = [i for i, c in enumerate(vessel_row) if "TOTAL" in str(c.get("label", "")).upper()]
            if total_cols:
                t_idx = total_cols[0]
                total_cell = f_pct1["cells"][t_idx]
                assert " %" in total_cell["val_r"]
    finally:
        db.close()

