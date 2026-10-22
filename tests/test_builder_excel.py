import json
import pytest
from app.db import SessionLocal, Company, CustomBuilderTemplate
from app.builder_excel import (
    export_single_template_excel,
    export_all_templates_bundle_excel,
    parse_template_excel
)

def test_excel_export_import_roundtrip():
    db = SessionLocal()
    # Ambil template BMS ID 4
    t = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.id == 4).first()
    assert t is not None, "Template 4 should exist in DB"
    
    comp = db.query(Company).filter(Company.id == t.company_id).first()
    comp_init = comp.initial_pt if comp else "BMS"
    comp_name = comp.name if comp else "PT Bahtera Mulia Sari"
    cfg = json.loads(t.config_json)
    db.close()
    
    # 1. Export ke Excel bytes
    excel_bytes = export_single_template_excel(t.name, comp_init, comp_name, cfg)
    assert len(excel_bytes) > 0, "Excel output should not be empty"
    
    # 2. Parse kembali dari Excel bytes
    parsed = parse_template_excel(excel_bytes)
    assert parsed["is_bundle"] is False
    assert parsed["template_name"] == t.name
    assert parsed["company_initial"] == comp_init
    assert len(parsed["rows"]) == len(cfg["rows"]), f"Expected {len(cfg['rows'])} rows, got {len(parsed['rows'])}"
    assert len(parsed["vessels"]) == len(cfg["vessels"]), f"Expected {len(cfg['vessels'])} vessels, got {len(parsed['vessels'])}"
    
    # Verifikasi baris 0
    orig_r0 = cfg["rows"][0]
    parsed_r0 = parsed["rows"][0]
    assert parsed_r0["code"] == orig_r0["code"]
    assert parsed_r0["label"] == orig_r0["label"]
    assert parsed_r0["type"] == orig_r0["type"]
    assert parsed_r0["is_bold"] == orig_r0.get("is_bold", False)

def test_excel_api_endpoints():
    from app.builder import export_template_excel, export_all_templates_excel, import_template_excel
    import io
    from fastapi import UploadFile
    import asyncio
    
    db = SessionLocal()
    # 1. Test export single template excel endpoint
    res = export_template_excel(4, db=db)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment; filename=" in res.headers["content-disposition"]
    excel_content = res.body
    assert len(excel_content) > 1000
    
    # 2. Test export all templates excel endpoint
    res_all = export_all_templates_excel(company_id=None, db=db)
    assert res_all.status_code == 200
    assert len(res_all.body) > 1000
    
    # 3. Test import excel via router
    upload_file = UploadFile(
        file=io.BytesIO(excel_content),
        filename="template_bms_test.xlsx",
        headers={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    )
    
    import_res = asyncio.run(import_template_excel(
        file=upload_file,
        target_company_id="2",
        overwrite="true",
        template_name_override="Triwulan - Kapal BMS (Excel Test Route)",
        db=db
    ))
    assert import_res["status"] == "success"
    assert len(import_res["imported"]) >= 1
    assert import_res["imported"][0]["name"] == "Triwulan - Kapal BMS (Excel Test Route)"
    
    # Clean up test template
    del_t = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.name == "Triwulan - Kapal BMS (Excel Test Route)").first()
    if del_t:
        db.delete(del_t)
        db.commit()
    db.close()
