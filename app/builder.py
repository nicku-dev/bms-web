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
from .odoo_api import OdooAPI

router = APIRouter(prefix="/api/builder", tags=["builder"])

@router.get("/tags")
def get_tags(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    tags = []
    try:
        engine = ReportEngine(company.target_db_name, pg_kwargs=company.get_pg_kwargs())
        tags = engine.get_all_tags()
        engine.close()
    except Exception as e:
        print(f"ReportEngine get_tags failed for company {company.name}: {e}")
        tags = []

    # Fallback to Odoo API if DuckDB/Postgres did not return tags
    if not tags and company.server_url and company.odoo_user and company.odoo_password:
        try:
            api = OdooAPI(
                db_name=company.target_db_name,
                url=company.server_url,
                username=company.odoo_user,
                password=company.odoo_password
            )
            raw = api.search_read('account.account.tag', [], ['id', 'name'])
            if raw:
                tags = list(set([t['name'] for t in raw if t.get('name')]))
        except Exception as e:
            print(f"OdooAPI get_tags fallback failed for company {company.name}: {e}")
    
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
        },
        {
            "code": "TPJ_TERPILIH",
            "name": "Pendapatan Jasa Kapal Terpilih",
            "description": "Total akumulasi pendapatan khusus kapal-kapal yang dipilih dalam laporan untuk perhitungan proporsional.",
            "default_label": "Total Pendapatan Kapal Terpilih"
        }
    ]

@router.get("/vessels")
def get_vessels(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    vessels = []
    # 1. Try DuckDB / PostgreSQL ReportEngine
    try:
        engine = ReportEngine(company.target_db_name, pg_kwargs=company.get_pg_kwargs())
        vessels = engine.get_all_vessels()
        engine.close()
    except Exception as e:
        print(f"ReportEngine get_vessels failed for company {company.name}: {e}")
        vessels = []

    # 2. Fallback to Odoo API if DuckDB/Postgres fails or returns empty
    if not vessels and company.server_url and company.odoo_user and company.odoo_password:
        try:
            api = OdooAPI(
                db_name=company.target_db_name,
                url=company.server_url,
                username=company.odoo_user,
                password=company.odoo_password
            )
            raw = api.search_read('fleet.combination', [], ['id', 'name', 'is_third_party'])
            if raw:
                vessels = sorted(raw, key=lambda x: str(x.get('name', '')))
        except Exception as e:
            print(f"OdooAPI get_vessels fallback failed for company {company.name}: {e}")

    return vessels

@router.get("/accounts")
def get_accounts(company_id: int, tag_name: Optional[str] = None, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    accounts = []
    try:
        engine = ReportEngine(company.target_db_name, pg_kwargs=company.get_pg_kwargs())
        accounts = engine.get_all_accounts(tag_name=tag_name)
        engine.close()
    except Exception as e:
        print(f"ReportEngine get_accounts failed for company {company.name}: {e}")
        accounts = []

    # Fallback to Odoo API
    if not accounts and company.server_url and company.odoo_user and company.odoo_password:
        try:
            api = OdooAPI(
                db_name=company.target_db_name,
                url=company.server_url,
                username=company.odoo_user,
                password=company.odoo_password
            )
            domain = [('tag_ids.name', '=', tag_name)] if tag_name else []
            raw = api.search_read('account.account', domain, ['id', 'code', 'name', 'tag_ids'])
            if raw:
                for a in raw:
                    accounts.append({
                        'id': a.get('id'),
                        'code': str(a.get('code') or ''),
                        'name': str(a.get('name') or ''),
                        'tag_name': tag_name or ''
                    })
        except Exception as e:
            print(f"OdooAPI get_accounts fallback failed for company {company.name}: {e}")

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

@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(t)
    db.commit()
    return {"status": "success", "message": f"Template {template_id} deleted successfully"}

@router.post("/templates/{template_id}/duplicate")
def duplicate_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    now = datetime.now().isoformat()
    dup = CustomBuilderTemplate(
        company_id=t.company_id,
        name=f"{t.name} (Salinan)",
        config_json=t.config_json,
        created_at=now,
        updated_at=now
    )
    db.add(dup)
    db.commit()
    db.refresh(dup)
    return {"status": "success", "id": dup.id, "name": dup.name}

class PreviewRequest(BaseModel):
    company_id: int
    year: str = "2026"
    vessels: List[Dict[str, Any]]
    rows: List[Dict[str, Any]]

def build_raw_matrix(company: Company, year: str, vessels: list, rows: list, db: Session = None) -> dict:
    """Constructs the base matrix structure (header and body rows with val_c expressions) from builder config."""
    if not vessels:
        vessels = [{'id': 0, 'name': 'HEAD OFFICE (HO)', 'is_ho': True}]

    year_str = str(year)
    quarters = [
        ('q1', f'{year_str}-01-01', f'{year_str}-03-31'),
        ('q2', f'{year_str}-04-01', f'{year_str}-06-30'),
        ('q3', f'{year_str}-07-01', f'{year_str}-09-30'),
        ('q4', f'{year_str}-10-01', f'{year_str}-12-31'),
        ('ytd', f'{year_str}-01-01', f'{year_str}-12-31')
    ]

    h0 = []
    h1 = []
    for v in vessels:
        v_name = v.get("name", "").strip()
        label = v_name if (v.get('is_ho') or 'HEAD OFFICE' in v_name.upper()) else f'Kapal - {v_name}'
        h0.append({'label': label, 'colspan': len(quarters)})
        for q, _, _ in quarters:
            h1.append({'label': q.upper() if q != 'ytd' else 'YTD'})

    has_auto_expand = any(r.get('auto_expand_coa') or r.get('auto_expand') for r in rows)
    body = []
    engine = None
    if has_auto_expand:
        try:
            engine = ReportEngine(company.target_db_name, pg_kwargs=company.get_pg_kwargs())
        except Exception as e:
            print(f"ReportEngine preview init failed for company {company.name}: {e}")
            engine = None

    try:
        existing_acc_codes = {str(row.get('expression', '')).strip() for row in rows if row.get('type') == 'account'}

        for r in rows:
            var_name = r.get('code', '').strip()
            label = r.get('label', '').strip() or var_name
            row_type = r.get('type', 'data')
            expr = r.get('expression', '').strip()
            auto_expand = bool(r.get('auto_expand_coa') or r.get('auto_expand'))
            is_hidden = bool(r.get('is_hidden') or r.get('hidden'))
            
            custom_style = r.get('style', '').strip()
            style = custom_style
            if not style:
                parts = []
                if r.get('is_bold') or row_type in ['title', 'formula']:
                    parts.append('font-weight: bold;')
                if r.get('is_italic'):
                    parts.append('font-style: italic;')
                
                indent = r.get('indent_level', 0)
                if indent and int(indent) > 0:
                    parts.append(f'text-indent: {int(indent) * 1.5}em;')
                elif r.get('is_child'):
                    parts.append('text-indent: 2em;')
                    
                bg = r.get('bg_color')
                if bg and bg not in ['transparent', '#ffffff', '']:
                    parts.append(f'background-color: {bg};')
                elif any(term in label.lower() for term in ['laba', 'margin', 'net']):
                    parts.append('background-color: #E2EFDA;')
                    
                if is_hidden:
                    parts.append('display: none;')
                    
                style = ' '.join(parts)
            else:
                if is_hidden and 'display: none' not in style:
                    style += ' display: none;'
                
            cells = []
            for v in vessels:
                for q, sd, ed in quarters:
                    if row_type == 'title':
                        cells.append({'val': None, 'val_r': '', 'val_c': ''})
                    elif row_type == 'query':
                        val_c = f'{var_name}.{q} = kpi_{expr.lower()}'
                        cells.append({'val': 0.0, 'val_r': '-', 'val_c': val_c})
                    elif row_type == 'formula':
                        formula_rhs = expr
                        if formula_rhs.startswith(f'{var_name} ='):
                            formula_rhs = formula_rhs.split('=', 1)[1].strip()
                        val_c = f'{var_name}.{q} = {formula_rhs}'
                        cells.append({'val': 0.0, 'val_r': '-', 'val_c': val_c})
                    else:
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
                'is_hidden': is_hidden,
                'is_percentage': bool(r.get('is_percentage')),
                'auto_expand_coa': auto_expand,
                'cells': cells
            })

            # Otomatis Urai COA: Dynamically query and expand all active accounts belonging to this tag
            if auto_expand and expr and row_type == 'data':
                accounts = []
                if engine:
                    try:
                        accounts = engine.get_all_accounts(tag_name=expr)
                    except Exception:
                        accounts = []
                if not accounts and company.server_url and company.odoo_user and company.odoo_password:
                    try:
                        api = OdooAPI(
                            db_name=company.target_db_name,
                            url=company.server_url,
                            username=company.odoo_user,
                            password=company.odoo_password
                        )
                        raw = api.search_read('account.account', [('tag_ids.name', '=', expr)], ['id', 'code', 'name'])
                        if raw:
                            accounts = [{'id': a.get('id'), 'code': str(a.get('code') or ''), 'name': str(a.get('name') or ''), 'tag_name': expr} for a in raw]
                    except Exception as e:
                        print(f"OdooAPI preview get_all_accounts failed: {e}")

                child_idx = 1
                for acc in accounts:
                    acc_code = str(acc['code']).strip()
                    if not acc_code or acc_code in existing_acc_codes:
                        continue
                    acc_name = acc.get('name', '').strip()
                    child_code = f"{var_name}_{child_idx}"
                    child_idx += 1
                    child_cells = []
                    for v in vessels:
                        for q, sd, ed in quarters:
                            val_c = f'{child_code}.{q} = balp[(\"account_id.code\",\"=\",\"{acc_code}\")][(\"date\", \">=\", \"{sd}\"),(\"date\", \"<=\", \"{ed}\")]'
                            child_cells.append({'val': 0.0, 'val_r': '-', 'val_c': val_c})
                    
                    body.append({
                        'label': f"{acc_code} {acc_name}".strip(),
                        'name': child_code,
                        'row_type': 'account',
                        'is_child': True,
                        'parent_code': var_name,
                        'style': 'font-style: italic; text-indent: 2em;',
                        'cells': child_cells
                    })
    finally:
        if engine:
            try:
                engine.close()
            except Exception:
                pass

    return {'header': [h0, h1], 'body': body}

def build_and_compile_matrix(company: Company, year: str, vessels: list, rows: list, db: Session = None) -> dict:
    """Builds the raw matrix from builder definition and evaluates all DuckDB accounting queries and formulas."""
    raw_matrix = build_raw_matrix(company, year, vessels, rows, db)
    from app.compiler import FastMatrixCompiler
    compiler = FastMatrixCompiler(db_name=company.target_db_name, year=str(year), pg_kwargs=company.get_pg_kwargs())
    return compiler.compile(raw_matrix)

@router.post("/preview")
def preview_template(payload: PreviewRequest, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == payload.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
        
    vessels = payload.vessels
    if not vessels:
        vessels = [{'id': 0, 'name': 'HEAD OFFICE (HO)', 'is_ho': True}]
        
    if not payload.rows:
        raise HTTPException(status_code=400, detail="Tambahkan minimal 1 baris laporan.")

    year = str(payload.year)
    try:
        compiled_matrix = build_and_compile_matrix(company, year, vessels, payload.rows, db)
        return {"status": "success", "data": compiled_matrix}
    except Exception as e:
        print(f"FastMatrixCompiler preview failed: {e}")
        raw_matrix = build_raw_matrix(company, year, vessels, payload.rows, db)
        return {"status": "success", "data": raw_matrix, "warning": f"Matriks belum dikompilasi nilai DuckDB: {str(e)}"}
