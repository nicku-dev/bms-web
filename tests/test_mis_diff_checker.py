import os
import json
import io
import asyncio
import pytest
from fastapi import UploadFile, Request
from app.main import reconcile_mis_builder
from app.db import SessionLocal
from app.models import Company, CustomBuilderTemplate
from app.builder import build_and_compile_matrix
from app.diff_checker import parse_mis_builder_excel, compare_matrices, export_diff_matrix_excel

def test_parse_mis_builder_excel_fps():
    excel_path = "tests/reference/fps/fps 2026 - Kapal FPS.xlsx"
    assert os.path.exists(excel_path), f"File {excel_path} should exist"
    
    with open(excel_path, "rb") as f:
        file_bytes = f.read()
        
    parsed = parse_mis_builder_excel(file_bytes)
    assert parsed["company_name"] == "PT. FANGIONOPERKASA SEJATI"
    assert "Triwulan" in parsed["report_title"] or "Laporan" in parsed["report_title"]
    assert len(parsed["columns"]) >= 120
    assert len(parsed["rows"]) >= 80
    
    # Check first column
    first_col = parsed["columns"][0]
    assert "TB. FPS 01" in first_col["raw_vessel"]
    assert first_col["period"] == "Q1"
    
    # Check that rows have parsed data
    row_keterangan = [r for r in parsed["rows"] if "PENDAPATAN JASA" in r["clean_label"]]
    assert len(row_keterangan) > 0
    assert row_keterangan[0]["cells"][0] > 0

def test_compare_and_export_diff():
    excel_path = "tests/reference/fps/fps 2026 - Kapal FPS.xlsx"
    with open(excel_path, "rb") as f:
        file_bytes = f.read()
    mis_data = parse_mis_builder_excel(file_bytes)
    
    db = SessionLocal()
    comp = db.query(Company).filter(Company.id == 1).first()
    t = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.id == 9).first()
    cfg = json.loads(t.config_json)
    
    bms_matrix = build_and_compile_matrix(comp, "2026", cfg.get("vessels", []), cfg.get("rows", []), db)
    db.close()
    
    diff_result = compare_matrices(bms_matrix, mis_data, tolerance=1.0)
    kpi = diff_result["kpi"]
    assert kpi["total_cells"] > 0
    assert kpi["match_cells"] > 0
    assert "accuracy_pct" in kpi
    assert len(diff_result["rows"]) == len(bms_matrix["body"])
    
    # Test export diff excel
    excel_bytes = export_diff_matrix_excel(diff_result, comp.name, t.name, 2026)
    assert len(excel_bytes) > 1000

def test_api_reconcile_function():
    excel_path = "tests/reference/fps/fps 2026 - Kapal FPS.xlsx"
    with open(excel_path, "rb") as f:
        content = f.read()
        
    upload_file = UploadFile(
        filename="fps_sample.xlsx",
        file=io.BytesIO(content),
        headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    )
    
    # Create dummy request
    scope = {"type": "http", "method": "POST", "headers": []}
    request = Request(scope)
    
    res = asyncio.run(reconcile_mis_builder(
        request=request,
        company_id=1,
        template_id=9,
        year=2026,
        tolerance=1.0,
        file=upload_file
    ))
    
    assert res.get("status") == "success"
    assert "kpi" in res
    assert res["kpi"]["accuracy_pct"] > 0
    assert "excel_url" in res
    assert os.path.exists(f"app{res['excel_url']}")

def test_checker_ui_render():
    from app.main import checker_ui
    scope = {
        "type": "http",
        "method": "GET",
        "headers": [(b"cookie", b"session_token=admin_dev")]
    }
    request = Request(scope)
    res = asyncio.run(checker_ui(request))
    assert res.status_code == 200
    assert "Rekonsiliasi MIS" in res.body.decode("utf-8")

