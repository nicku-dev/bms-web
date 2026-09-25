from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime
import json
from .db import get_db
from .models import Company, CustomBuilderTemplate
from .engine import ReportEngine

router = APIRouter(prefix="/api/builder", tags=["builder"])

@router.get("/tags")
def get_tags(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    engine = ReportEngine(company.target_db_name)
    tags = engine.get_all_tags()
    engine.close()
    return tags

@router.get("/vessels")
def get_vessels(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    engine = ReportEngine(company.target_db_name)
    vessels = engine.get_all_vessels()
    engine.close()
    return vessels

@router.get("/templates")
def list_templates(company_id: int, db: Session = Depends(get_db)):
    templates = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.company_id == company_id).all()
    return [{"id": t.id, "name": t.name, "created_at": t.created_at, "updated_at": t.updated_at} for t in templates]

@router.get("/templates/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return {
        "id": t.id,
        "company_id": t.company_id,
        "name": t.name,
        "config": json.loads(t.config_json),
        "created_at": t.created_at,
        "updated_at": t.updated_at
    }

@router.post("/templates")
def save_template(
    company_id: int = Body(...),
    name: str = Body(...),
    config: dict = Body(...),
    template_id: int = Body(None),
    db: Session = Depends(get_db)
):
    now = datetime.now().isoformat()
    if template_id:
        t = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.id == template_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")
        t.name = name
        t.config_json = json.dumps(config)
        t.updated_at = now
    else:
        t = CustomBuilderTemplate(
            company_id=company_id,
            name=name,
            config_json=json.dumps(config),
            created_at=now,
            updated_at=now
        )
        db.add(t)
    
    db.commit()
    db.refresh(t)
    return {"status": "success", "id": t.id}
