from fastapi import APIRouter, HTTPException, Body
from datetime import datetime
import json
import sqlite3
import os
from pathlib import Path
from pydantic import BaseModel

router = APIRouter(prefix="/api/builder", tags=["builder"])

def get_db_path():
    return str(Path(os.getcwd()) / 'app_config.db')

@router.get("/tags")
def get_tags(company_id: int):
    import duckdb
    db_path = os.path.join(os.getcwd(), 'app_cache.duckdb')
    try:
        conn = duckdb.connect(db_path, read_only=True)
        res = conn.execute("SELECT DISTINCT name->>'en_US' FROM pg.account_account_tag WHERE name->>'en_US' LIKE 'TW_%'").fetchall()
        tags = [r[0] for r in res if r[0]]
        conn.close()
        return tags
    except Exception as e:
        return ["TW_PENDAPATAN JASA", "TW_BIAYA LAIN-LAIN"]

@router.get("/vessels")
def get_vessels(company_id: int):
    return [{"id": 1, "name": "GRAND HIJAU LESTARI"}, {"id": 2, "name": "MANDIRI JAYA"}]

@router.get("/templates")
def list_templates(company_id: int):
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM bms_reports")
    reports = cursor.fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"]} for r in reports]

@router.get("/templates/{template_id}")
def get_template(template_id: int):
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM bms_reports WHERE id = ?", (template_id,))
        report = cursor.fetchone()
        if not report:
            raise HTTPException(status_code=404, detail="Template not found")
            
        cursor.execute("SELECT * FROM bms_report_rows WHERE report_id = ? ORDER BY sequence ASC", (template_id,))
        rows = cursor.fetchall()
        
        ui_rows = []
        for r in rows:
            row_type = 'data' if r['row_type'] == 'tag_query' else 'formula'
            expr = r['tag_name'] if r['row_type'] == 'tag_query' else r['formula']
            ui_rows.append({
                "id": r['id'],
                "code": r['variable_name'],
                "type": row_type,
                "label": r['label'],
                "expression": expr
            })
            
        return {
            "status": "success",
            "data": {
                "id": report['id'],
                "name": report['name'],
                "config": {
                    "vessels": [],
                    "rows": ui_rows
                }
            }
        }
    finally:
        conn.close()

class BuilderTemplateRequest(BaseModel):
    company_id: int
    name: str
    config: dict
    id: int = None

@router.post("/templates")
def save_template(payload: BuilderTemplateRequest):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    try:
        if payload.id:
            cursor.execute("UPDATE bms_reports SET name = ? WHERE id = ?", (payload.name, payload.id))
            report_id = payload.id
            cursor.execute("DELETE FROM bms_report_rows WHERE report_id = ?", (report_id,))
        else:
            cursor.execute("INSERT INTO bms_reports (name, description) VALUES (?, ?)", (payload.name, "From Builder UI"))
            report_id = cursor.lastrowid
        
        seq = 10
        for row in payload.config.get('rows', []):
            row_type = 'tag_query' if row.get('type') == 'data' else 'formula'
            tag_name = row.get('expression') if row_type == 'tag_query' else None
            formula = row.get('expression') if row_type == 'formula' else None
            
            if formula and formula.startswith(row.get('code', '') + " ="):
                formula = formula.split("=", 1)[1].strip()
                
            cursor.execute("""
                INSERT INTO bms_report_rows (report_id, sequence, label, variable_name, row_type, tag_name, formula)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (report_id, seq, row.get('label'), row.get('code'), row_type, tag_name, formula))
            seq += 10
            
        conn.commit()
        return {"status": "success", "id": report_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
