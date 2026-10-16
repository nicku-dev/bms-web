from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import json
import re
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
    
    # Sort with TW_ tags prioritized at the top
    tw_tags = sorted([t for t in tags if t.startswith('TW_')])
    other_tags = sorted([t for t in tags if not t.startswith('TW_')])
    return tw_tags + other_tags

@router.get("/queries")
def get_available_queries():
    return [
        {
            "code": "KAPASITAS",
            "name": "Kapasitas Kapal (Cargo Capacity / DWT)",
            "description": "Kapasitas muatan kapal (DWT) dari spesifikasi teknis armada. Bersifat statis pada YTD.",
            "default_label": "Kapasitas Kapal (DWT)"
        },
        {
            "code": "TRIP",
            "name": "Jumlah Trip Kapal (Trip Count)",
            "description": "Jumlah trip pelayaran kapal per kuartal dari Sales Orders.",
            "default_label": "Jumlah Trip"
        },
        {
            "code": "TPJ_SEMUA",
            "name": "Pendapatan Jasa Semua Kapal",
            "description": "Total akumulasi pendapatan seluruh armada untuk perbandingan atau proporsi.",
            "default_label": "Total Pendapatan Seluruh Armada"
        }
    ]

@router.get("/vessels")
def get_vessels(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    engine = ReportEngine(company.target_db_name)
    vessels = engine.get_all_vessels()
    engine.close()
    return vessels

@router.get("/accounts")
def get_accounts(company_id: int, tag_name: Optional[str] = None, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    engine = ReportEngine(company.target_db_name)
    accounts = engine.get_all_accounts(tag_name=tag_name)
    engine.close()
    return accounts

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
        "status": "success",
        "data": {
            "id": t.id,
            "company_id": t.company_id,
            "name": t.name,
            "config": json.loads(t.config_json),
            "created_at": t.created_at,
            "updated_at": t.updated_at
        }
    }

class SaveTemplateRequest(BaseModel):
    company_id: int
    name: str
    config: dict
    id: Optional[int] = None
    template_id: Optional[int] = None

@router.post("/templates")
def save_template(payload: SaveTemplateRequest, db: Session = Depends(get_db)):
    now = datetime.now().isoformat()
    target_id = payload.template_id or payload.id
    if target_id:
        t = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.id == target_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")
        t.name = payload.name
        t.company_id = payload.company_id
        t.config_json = json.dumps(payload.config)
        t.updated_at = now
    else:
        t = CustomBuilderTemplate(
            company_id=payload.company_id,
            name=payload.name,
            config_json=json.dumps(payload.config),
            created_at=now,
            updated_at=now
        )
        db.add(t)
    
    db.commit()
    db.refresh(t)
    return {"status": "success", "id": t.id}

class PreviewRequest(BaseModel):
    company_id: int
    year: str = "2026"
    vessels: List[Dict[str, Any]]
    rows: List[Dict[str, Any]]

@router.post("/preview")
def preview_template(payload: PreviewRequest, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == payload.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    if not payload.vessels:
        raise HTTPException(status_code=400, detail="Pilih minimal 1 kapal untuk kolom laporan.")
        
    if not payload.rows:
        raise HTTPException(status_code=400, detail="Tambahkan minimal 1 baris laporan.")

    year = str(payload.year)
    quarters = [
        ('q1', f'{year}-01-01', f'{year}-03-31'),
        ('q2', f'{year}-04-01', f'{year}-06-30'),
        ('q3', f'{year}-07-01', f'{year}-09-30'),
        ('q4', f'{year}-10-01', f'{year}-12-31'),
        ('ytd', f'{year}-01-01', f'{year}-12-31')
    ]

    h0 = []
    h1 = []
    for v in payload.vessels:
        v_name = v.get("name", "").strip()
        h0.append({'label': f'Kapal - {v_name}', 'colspan': len(quarters)})
        for q, _, _ in quarters:
            h1.append({'label': q.upper() if q != 'ytd' else 'YTD'})

    body = []
    for r in payload.rows:
        var_name = r.get('code', '').strip()
        label = r.get('label', '').strip() or var_name
        row_type = r.get('type', 'data')
        expr = r.get('expression', '').strip()
        
        custom_style = r.get('style', '').strip()
        style = custom_style
        if not style:
            if row_type == 'formula':
                style = 'font-weight: bold;'
            if any(term in label.lower() for term in ['laba', 'margin', 'ebitda', 'total']):
                style += ' font-weight: bold;'
            if any(term in label.lower() for term in ['laba', 'margin', 'net']):
                style += ' background-color: #E2EFDA;'
            
        cells = []
        for v in payload.vessels:
            for q, sd, ed in quarters:
                if row_type == 'query':
                    val_c = f'{var_name}.{q} = kpi_{expr.lower()}'
                elif row_type == 'formula':
                    formula_rhs = expr
                    if formula_rhs.startswith(f'{var_name} ='):
                        formula_rhs = formula_rhs.split('=', 1)[1].strip()
                    val_c = f'{var_name}.{q} = {formula_rhs}'
                else:
                    # Account or Tag row
                    acc_match = re.search(r'^(\d{4,})', expr) or re.search(r'^(\d{4,})', label)
                    if acc_match or row_type == 'account':
                        acc_code = acc_match.group(1) if acc_match else expr
                        val_c = f'{var_name}.{q} = balp[(\"account_id.code\",\"=\",\"{acc_code}\")][(\"date\", \">=\", \"{sd}\"),(\"date\", \"<=\", \"{ed}\")]'
                    else:
                        val_c = f'{var_name}.{q} = balp[(\"tag_ids.name\",\"=\",\"{expr}\")][(\"date\", \">=\", \"{sd}\"),(\"date\", \"<=\", \"{ed}\")]'
                cells.append({'val': 0.0, 'val_r': '-', 'val_c': val_c})
                
        body.append({
            'label': label,
            'name': var_name,
            'row_type': row_type,
            'query_code': expr if row_type == 'query' else '',
            'style': style,
            'cells': cells
        })

    matrix = {'header': [h0, h1], 'body': body}
    try:
        from app.compiler import FastMatrixCompiler
        compiler = FastMatrixCompiler(db_name=company.target_db_name, year=year)
        compiled_matrix = compiler.compile(matrix)
        return {"status": "success", "data": compiled_matrix}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengompilasi matriks: {str(e)}")
