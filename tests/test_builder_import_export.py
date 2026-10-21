import json
import pytest
import subprocess
import os
from app.db import SessionLocal, Company, CustomBuilderTemplate
from app.builder import export_template, export_all_templates, import_templates, ImportTemplateRequest

def test_export_template_endpoint():
    db = SessionLocal()
    # Find a template
    tpl = db.query(CustomBuilderTemplate).first()
    assert tpl is not None, "At least one template should exist"
    
    res = export_template(tpl.id, db=db)
    assert res.status_code == 200
    assert "content-disposition" in res.headers
    assert "attachment;" in res.headers["content-disposition"]
    
    data = json.loads(res.body.decode())
    assert data["version"] == "1.0"
    assert data["system"] == "bms-report-builder"
    assert data["count"] == 1
    assert len(data["templates"]) == 1
    assert data["templates"][0]["name"] == tpl.name
    assert "config" in data["templates"][0]
    db.close()

def test_export_all_templates_endpoint():
    db = SessionLocal()
    res = export_all_templates(company_id=None, db=db)
    assert res.status_code == 200
    data = json.loads(res.body.decode())
    assert data["version"] == "1.0"
    assert data["count"] >= 1
    assert len(data["templates"]) == data["count"]
    db.close()

def test_import_templates_endpoint_overwrite_and_copy():
    db = SessionLocal()
    comp = db.query(Company).filter(Company.is_active == True).first()
    assert comp is not None
    
    test_tpl_name = "Automated Test Template Import"
    
    # 1. Clean up prior run if any
    db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.name.like(f"{test_tpl_name}%")).delete()
    db.commit()
    
    # 2. Import initial template
    payload1 = ImportTemplateRequest(
        data={
            "name": test_tpl_name,
            "company_initial": comp.initial_pt,
            "config": {"year": "2026", "vessels": [], "rows": [{"id": "r1", "label": "Row Initial"}]}
        },
        overwrite=True
    )
    res1 = import_templates(payload1, db=db)
    assert res1["status"] == "success"
    assert len(res1["imported"]) == 1
    assert res1["imported"][0]["action"] == "created"
    
    # Verify in DB
    tpl_db = db.query(CustomBuilderTemplate).filter(
        CustomBuilderTemplate.company_id == comp.id,
        CustomBuilderTemplate.name == test_tpl_name
    ).first()
    assert tpl_db is not None
    assert json.loads(tpl_db.config_json)["rows"][0]["label"] == "Row Initial"
    
    # 3. Import updated version with overwrite=True
    payload2 = ImportTemplateRequest(
        data={
            "name": test_tpl_name,
            "company_initial": comp.initial_pt,
            "config": {"year": "2026", "vessels": [], "rows": [{"id": "r1", "label": "Row Updated"}]}
        },
        overwrite=True
    )
    res2 = import_templates(payload2, db=db)
    assert res2["status"] == "success"
    assert res2["imported"][0]["action"] == "updated"
    
    db.refresh(tpl_db)
    assert json.loads(tpl_db.config_json)["rows"][0]["label"] == "Row Updated"
    
    # 4. Import with overwrite=False (should create copy)
    payload3 = ImportTemplateRequest(
        data={
            "name": test_tpl_name,
            "company_initial": comp.initial_pt,
            "config": {"year": "2026", "vessels": [], "rows": [{"id": "r1", "label": "Row Copied"}]}
        },
        overwrite=False
    )
    res3 = import_templates(payload3, db=db)
    assert res3["status"] == "success"
    assert res3["imported"][0]["action"] == "created"
    assert "Imported" in res3["imported"][0]["name"]
    
    # 5. Clean up
    db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.name.like(f"{test_tpl_name}%")).delete()
    db.commit()
    db.close()

def test_cli_export_import_scripts():
    tmp_export_file = "/tmp/test_cli_export_templates.json"
    if os.path.exists(tmp_export_file):
        os.remove(tmp_export_file)
        
    # Run export script
    res_exp = subprocess.run([
        "python3", "scripts/export_templates.py", "--all", "--output", tmp_export_file
    ], capture_output=True, text=True)
    assert res_exp.returncode == 0
    assert os.path.exists(tmp_export_file)
    
    with open(tmp_export_file, "r") as f:
        data = json.load(f)
    assert data["version"] == "1.0"
    assert data["count"] >= 1
    
    # Run import script with overwrite
    res_imp = subprocess.run([
        "python3", "scripts/import_templates.py", "--file", tmp_export_file, "--overwrite"
    ], capture_output=True, text=True)
    assert res_imp.returncode == 0
    assert "Selesai:" in res_imp.stdout
    
    os.remove(tmp_export_file)
