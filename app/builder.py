from fastapi import APIRouter, Depends, HTTPException, Body, Response, UploadFile, File, Form
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
from .builder_excel import (
    export_single_template_excel,
    export_all_templates_bundle_excel,
    parse_template_excel
)

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
            # Mutlak JOIN antara account.account (CoA) dan account.account.tag
            accounts = api.search_read('account.account', [('tag_ids', '!=', False)], ['tag_ids'])
            if accounts:
                tag_ids = set()
                for a in accounts:
                    for tid in (a.get('tag_ids') or []):
                        tag_ids.add(tid)
                if tag_ids:
                    raw = api.search_read('account.account.tag', [('id', 'in', list(tag_ids))], ['id', 'name'])
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
def list_templates(company_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(CustomBuilderTemplate)
    if company_id and company_id != "all":
        try:
            cid = int(company_id)
            query = query.filter(CustomBuilderTemplate.company_id == cid)
        except ValueError:
            pass
    templates = query.order_by(CustomBuilderTemplate.company_id, CustomBuilderTemplate.id).all()
    companies_map = {c.id: c for c in db.query(Company).all()}
    res = []
    for t in templates:
        comp = companies_map.get(t.company_id)
        try:
            cfg = json.loads(t.config_json)
        except Exception:
            cfg = {}
        res.append({
            "id": t.id,
            "company_id": t.company_id,
            "company_initial": comp.initial_pt if comp else "UNKNOWN",
            "company_name": comp.name if comp else "Unknown Company",
            "name": t.name,
            "vessels_count": len(cfg.get("vessels", [])),
            "rows_count": len(cfg.get("rows", [])),
            "year": cfg.get("year", "2026"),
            "created_at": t.created_at,
            "updated_at": t.updated_at
        })
    return res

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

@router.get("/templates/{template_id}/export")
def export_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    
    comp = db.query(Company).filter(Company.id == t.company_id).first()
    comp_init = comp.initial_pt if comp else "UNKNOWN"
    comp_name = comp.name if comp else "Unknown Company"
    
    export_data = {
        "version": "1.0",
        "system": "bms-report-builder",
        "exported_at": datetime.now().isoformat(),
        "count": 1,
        "templates": [
            {
                "name": t.name,
                "company_initial": comp_init,
                "company_name": comp_name,
                "config": json.loads(t.config_json)
            }
        ]
    }
    
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', f"{comp_init}_{t.name}")
    filename = f"template_{clean_name}.json"
    json_bytes = json.dumps(export_data, indent=2, ensure_ascii=False)
    
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@router.get("/templates/export-all")
def export_all_templates(company_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(CustomBuilderTemplate)
    comp_init = "ALL"
    if company_id and company_id != "all":
        try:
            cid = int(company_id)
            query = query.filter(CustomBuilderTemplate.company_id == cid)
            comp = db.query(Company).filter(Company.id == cid).first()
            if comp:
                comp_init = comp.initial_pt or f"COMP_{cid}"
        except ValueError:
            pass
            
    templates_records = query.order_by(CustomBuilderTemplate.company_id, CustomBuilderTemplate.id).all()
    companies_map = {c.id: c for c in db.query(Company).all()}
    
    templates_list = []
    for t in templates_records:
        comp = companies_map.get(t.company_id)
        templates_list.append({
            "name": t.name,
            "company_initial": comp.initial_pt if comp else "UNKNOWN",
            "company_name": comp.name if comp else "Unknown Company",
            "config": json.loads(t.config_json)
        })
        
    export_data = {
        "version": "1.0",
        "system": "bms-report-builder",
        "exported_at": datetime.now().isoformat(),
        "count": len(templates_list),
        "templates": templates_list
    }
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"templates_backup_{comp_init}_{timestamp}.json"
    json_bytes = json.dumps(export_data, indent=2, ensure_ascii=False)
    
    return Response(
        content=json_bytes,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@router.get("/templates/{template_id}/export-excel")
def export_template_excel(template_id: int, db: Session = Depends(get_db)):
    t = db.query(CustomBuilderTemplate).filter(CustomBuilderTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    
    comp = db.query(Company).filter(Company.id == t.company_id).first()
    comp_init = comp.initial_pt if comp else "UNKNOWN"
    comp_name = comp.name if comp else "Unknown Company"
    
    try:
        cfg = json.loads(t.config_json)
    except Exception:
        cfg = {}
        
    excel_bytes = export_single_template_excel(t.name, comp_init, comp_name, cfg)
    clean_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', f"{comp_init}_{t.name}")
    filename = f"template_{clean_name}.xlsx"
    
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@router.get("/templates/export-all-excel")
def export_all_templates_excel(company_id: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(CustomBuilderTemplate)
    comp_init = "ALL"
    if company_id and company_id != "all":
        try:
            cid = int(company_id)
            query = query.filter(CustomBuilderTemplate.company_id == cid)
            comp = db.query(Company).filter(Company.id == cid).first()
            if comp:
                comp_init = comp.initial_pt or f"COMP_{cid}"
        except ValueError:
            pass
            
    templates_records = query.order_by(CustomBuilderTemplate.company_id, CustomBuilderTemplate.id).all()
    companies_map = {c.id: c for c in db.query(Company).all()}
    
    templates_list = []
    for t in templates_records:
        comp = companies_map.get(t.company_id)
        try:
            cfg = json.loads(t.config_json)
        except Exception:
            cfg = {}
        templates_list.append({
            "name": t.name,
            "company_initial": comp.initial_pt if comp else "UNKNOWN",
            "company_name": comp.name if comp else "Unknown Company",
            "config": cfg
        })
        
    excel_bytes = export_all_templates_bundle_excel(templates_list, title_suffix=comp_init)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"templates_backup_{comp_init}_{timestamp}.xlsx"
    
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

def save_imported_templates_core(items_to_import: list, target_company_id: Optional[int], overwrite: bool, db: Session) -> dict:
    if not items_to_import:
        raise HTTPException(status_code=400, detail="Tidak ada template yang ditemukan untuk diimpor")

    companies = db.query(Company).all()
    comp_by_id = {c.id: c for c in companies}
    comp_by_initial = {c.initial_pt.strip().upper(): c for c in companies if c.initial_pt}
    comp_by_name = {c.name.strip().upper(): c for c in companies if c.name}

    results = []
    now = datetime.now().isoformat()

    for item in items_to_import:
        if not isinstance(item, dict):
            continue
            
        tpl_name = str(item.get("name") or "Unnamed Template").strip()
        config_data = item.get("config")
        if not config_data and "config_json" in item:
            try:
                config_data = json.loads(item["config_json"]) if isinstance(item["config_json"], str) else item["config_json"]
            except Exception:
                config_data = {}
        if not isinstance(config_data, dict):
            config_data = {}

        resolved_comp = None
        if target_company_id and target_company_id in comp_by_id:
            resolved_comp = comp_by_id[target_company_id]
        elif item.get("company_initial") and str(item["company_initial"]).strip().upper() in comp_by_initial:
            resolved_comp = comp_by_initial[str(item["company_initial"]).strip().upper()]
        elif item.get("company_name") and str(item["company_name"]).strip().upper() in comp_by_name:
            resolved_comp = comp_by_name[str(item["company_name"]).strip().upper()]
        elif len(companies) == 1:
            resolved_comp = companies[0]

        if not resolved_comp:
            resolved_comp = db.query(Company).filter(Company.is_active == True).first()
            if not resolved_comp:
                raise HTTPException(status_code=400, detail=f"Tidak ditemukan perusahaan untuk template '{tpl_name}'")

        existing = db.query(CustomBuilderTemplate).filter(
            CustomBuilderTemplate.company_id == resolved_comp.id,
            CustomBuilderTemplate.name == tpl_name
        ).first()

        if existing and overwrite:
            existing.config_json = json.dumps(config_data)
            existing.updated_at = now
            db.commit()
            results.append({
                "id": existing.id,
                "name": existing.name,
                "company": resolved_comp.initial_pt or resolved_comp.name,
                "action": "updated"
            })
        else:
            final_name = tpl_name
            if existing and not overwrite:
                final_name = f"{tpl_name} (Imported {datetime.now().strftime('%H%M%S')})"
                
            new_tpl = CustomBuilderTemplate(
                company_id=resolved_comp.id,
                name=final_name,
                config_json=json.dumps(config_data),
                created_at=now,
                updated_at=now
            )
            db.add(new_tpl)
            db.commit()
            db.refresh(new_tpl)
            results.append({
                "id": new_tpl.id,
                "name": new_tpl.name,
                "company": resolved_comp.initial_pt or resolved_comp.name,
                "action": "created"
            })

    return {
        "status": "success",
        "message": f"Berhasil mengimpor {len(results)} template",
        "imported": results
    }

class ImportTemplateRequest(BaseModel):
    data: Any
    target_company_id: Optional[int] = None
    overwrite: bool = True

@router.post("/templates/import")
def import_templates(payload: ImportTemplateRequest, db: Session = Depends(get_db)):
    raw = payload.data
    target_company_id = payload.target_company_id
    overwrite = payload.overwrite
    
    items_to_import = []
    if isinstance(raw, dict):
        if "templates" in raw and isinstance(raw["templates"], list):
            items_to_import = raw["templates"]
        elif "rows" in raw or "vessels" in raw:
            items_to_import = [{
                "name": f"Imported Template {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "config": raw
            }]
        elif "name" in raw and ("config" in raw or "config_json" in raw):
            cfg = raw.get("config") or (json.loads(raw["config_json"]) if isinstance(raw.get("config_json"), str) else {})
            items_to_import = [{
                "name": raw["name"],
                "company_initial": raw.get("company_initial"),
                "company_name": raw.get("company_name"),
                "config": cfg
            }]
        else:
            raise HTTPException(status_code=400, detail="Format JSON tidak dikenali sebagai template builder")
    elif isinstance(raw, list):
        items_to_import = raw
    else:
        raise HTTPException(status_code=400, detail="Data template harus berupa JSON Object atau Array")

    return save_imported_templates_core(items_to_import, target_company_id, overwrite, db)

@router.post("/templates/preview-excel")
async def preview_template_excel(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(('.xlsx', '.xlsm')):
        raise HTTPException(status_code=400, detail="File harus berformat Excel (.xlsx)")
    try:
        content = await file.read()
        parsed = parse_template_excel(content)
        return {"status": "success", "data": parsed}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal memproses file Excel: {str(e)}")

@router.post("/templates/import-excel")
async def import_template_excel(
    file: UploadFile = File(...),
    target_company_id: Optional[str] = Form(None),
    overwrite: str = Form("true"),
    template_name_override: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    if not file.filename.lower().endswith(('.xlsx', '.xlsm')):
        raise HTTPException(status_code=400, detail="File harus berformat Excel (.xlsx)")
        
    try:
        content = await file.read()
        parsed = parse_template_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal membaca file Excel: {str(e)}")

    target_cid = None
    if target_company_id and target_company_id != "null" and target_company_id != "":
        try:
            target_cid = int(target_company_id)
        except ValueError:
            target_cid = None

    is_overwrite = (str(overwrite).lower() in ("true", "1", "yes"))

    if parsed.get("is_bundle"):
        items_to_import = parsed.get("bundled_templates", [])
    else:
        name = template_name_override.strip() if template_name_override and template_name_override.strip() else parsed.get("template_name")
        if not name:
            clean_fn = re.sub(r'\.(xlsx|xlsm)$', '', file.filename, flags=re.IGNORECASE)
            name = clean_fn.replace("template_", "").replace("_", " ").strip()
            if not name:
                name = f"Template Excel {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                
        items_to_import = [{
            "name": name,
            "company_initial": parsed.get("company_initial"),
            "company_name": parsed.get("company_name"),
            "config": {
                "rows": parsed.get("rows", []),
                "vessels": parsed.get("vessels", [])
            }
        }]

    return save_imported_templates_core(items_to_import, target_cid, is_overwrite, db)

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
                    
            is_proportional = bool(r.get('is_proportional'))
            multiplier_row = str(r.get('multiplier_row') or '').strip()

            body.append({
                'label': label,
                'name': var_name,
                'row_type': row_type,
                'query_code': expr if row_type == 'query' else '',
                'style': style,
                'is_hidden': is_hidden,
                'is_percentage': bool(r.get('is_percentage')),
                'auto_expand_coa': auto_expand,
                'is_proportional': is_proportional,
                'multiplier_row': multiplier_row,
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
                        'parent_tag': expr,
                        'tag_name': expr,
                        'is_proportional': is_proportional,
                        'multiplier_row': multiplier_row,
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
