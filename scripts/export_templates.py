#!/usr/bin/env python3
"""
CLI Script to export Custom Report Builder templates from app_config.db to JSON.
Usage:
    python scripts/export_templates.py --all --output all_templates.json
    python scripts/export_templates.py --company BMS --output bms_templates.json
    python scripts/export_templates.py --template-id 4 --output template_bms.json
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime

DEFAULT_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app_config.db"))

def export_templates(db_path, company=None, template_id=None, output=None, format_type="json"):
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Pre-fetch companies
    cur.execute("SELECT id, name, initial_pt FROM companies")
    comp_map = {r["id"]: dict(r) for r in cur.fetchall()}

    query = "SELECT id, company_id, name, config_json, created_at, updated_at FROM custom_builder_templates WHERE 1=1"
    params = []

    if template_id is not None:
        query += " AND id = ?"
        params.append(template_id)
    elif company is not None and str(company).lower() != "all":
        # Check if company is numeric ID or initial_pt
        matched_id = None
        for cid, cinfo in comp_map.items():
            if str(cid) == str(company) or (cinfo["initial_pt"] and cinfo["initial_pt"].lower() == str(company).lower()):
                matched_id = cid
                break
        if matched_id is not None:
            query += " AND company_id = ?"
            params.append(matched_id)
        else:
            print(f"Error: Perusahaan '{company}' tidak ditemukan.", file=sys.stderr)
            sys.exit(1)

    query += " ORDER BY company_id, id"
    cur.execute(query, params)
    rows = cur.fetchall()

    templates_list = []
    for r in rows:
        cid = r["company_id"]
        cinfo = comp_map.get(cid, {"initial_pt": "UNKNOWN", "name": "Unknown Company"})
        try:
            cfg = json.loads(r["config_json"])
        except Exception:
            cfg = {}

        templates_list.append({
            "name": r["name"],
            "company_initial": cinfo.get("initial_pt") or "UNKNOWN",
            "company_name": cinfo.get("name") or "Unknown Company",
            "config": cfg,
            "created_at": r["created_at"],
            "updated_at": r["updated_at"]
        })

    conn.close()

    export_envelope = {
        "version": "1.0",
        "system": "bms-report-builder",
        "exported_at": datetime.now().isoformat(),
        "count": len(templates_list),
        "templates": templates_list
    }

    # Cek format (excel vs json)
    is_excel = False
    if output and output.lower().endswith(('.xlsx', '.xlsm')):
        is_excel = True
    elif format_type and format_type.lower() in ("excel", "xlsx"):
        is_excel = True

    if is_excel:
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from app.builder_excel import export_single_template_excel, export_all_templates_bundle_excel
        
        if not output:
            output = f"templates_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
        out_dir = os.path.dirname(os.path.abspath(output))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            
        if len(templates_list) == 1:
            t0 = templates_list[0]
            bytes_data = export_single_template_excel(t0["name"], t0["company_initial"], t0["company_name"], t0["config"])
        else:
            bytes_data = export_all_templates_bundle_excel(templates_list)
            
        with open(output, "wb") as f:
            f.write(bytes_data)
        print(f"✅ Sukses: {len(templates_list)} template berhasil diexport ke Excel (Gaya Odoo): {output}")
        return

    json_str = json.dumps(export_envelope, indent=2, ensure_ascii=False)

    if output:
        out_dir = os.path.dirname(os.path.abspath(output))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"✅ Sukses: {len(templates_list)} template berhasil diexport ke: {output}")
    else:
        print(json_str)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Report Builder Templates to JSON or Excel (Odoo Style)")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path ke app_config.db")
    parser.add_argument("--company", help="ID atau Inisial Perusahaan (misal: BMS, FPS, ALJ)")
    parser.add_argument("--template-id", type=int, help="Export satu template berdasarkan ID")
    parser.add_argument("--all", action="store_true", help="Export seluruh template dari semua perusahaan")
    parser.add_argument("--format", choices=["json", "excel", "xlsx"], default="json", help="Format export: json atau excel (default: json)")
    parser.add_argument("--output", "-o", help="Path file output (.json atau .xlsx)")
    args = parser.parse_args()

    comp_arg = "all" if args.all else args.company
    export_templates(args.db, company=comp_arg, template_id=args.template_id, output=args.output, format_type=args.format)
