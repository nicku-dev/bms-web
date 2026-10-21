import json
import pytest
from app.db import SessionLocal, Company, CustomBuilderTemplate
from app.builder import build_and_compile_matrix

def test_builder_generation_fps():
    db = SessionLocal()
    fps_company = db.query(Company).filter(Company.id == 1).first()
    assert fps_company is not None, "FPS company should exist"
    
    template = db.query(CustomBuilderTemplate).filter(
        CustomBuilderTemplate.company_id == 1,
        CustomBuilderTemplate.id == 9
    ).first()
    assert template is not None, "FPS template ID 9 should exist"
    
    cfg = json.loads(template.config_json)
    matrix = build_and_compile_matrix(fps_company, str(cfg.get('year', 2026)), cfg.get('vessels', []), cfg.get('rows', []), db)
    db.close()
    
    assert "header" in matrix
    assert "body" in matrix
    assert len(matrix["body"]) >= 40

def test_builder_generation_bms():
    db = SessionLocal()
    bms_company = db.query(Company).filter(Company.id == 2).first()
    assert bms_company is not None, "BMS company should exist"
    
    template = db.query(CustomBuilderTemplate).filter(
        CustomBuilderTemplate.company_id == 2,
        CustomBuilderTemplate.id == 4
    ).first()
    assert template is not None, "BMS template ID 4 should exist"
    
    cfg = json.loads(template.config_json)
    matrix = build_and_compile_matrix(bms_company, str(cfg.get('year', 2026)), cfg.get('vessels', []), cfg.get('rows', []), db)
    db.close()
    
    assert "header" in matrix
    assert "body" in matrix
    assert len(matrix["body"]) == 87

def test_builder_generation_alj():
    db = SessionLocal()
    alj_company = db.query(Company).filter(Company.id == 3).first()
    assert alj_company is not None, "ALJ company should exist"
    
    template = db.query(CustomBuilderTemplate).filter(
        CustomBuilderTemplate.company_id == 3,
        CustomBuilderTemplate.id == 6
    ).first()
    assert template is not None, "ALJ template ID 6 should exist"
    
    cfg = json.loads(template.config_json)
    matrix = build_and_compile_matrix(alj_company, str(cfg.get('year', 2026)), cfg.get('vessels', []), cfg.get('rows', []), db)
    db.close()
    
    assert "header" in matrix
    assert "body" in matrix
    assert len(matrix["body"]) == 87
