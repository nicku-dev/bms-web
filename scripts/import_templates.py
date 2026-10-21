#!/usr/bin/env python3
"""
CLI Script to import Custom Report Builder templates from JSON into app_config.db.
Usage:
    python scripts/import_templates.py --file all_templates.json --overwrite
    python scripts/import_templates.py --file bms_templates.json --company BMS --overwrite
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime

DEFAULT_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app_config.db"))

def import_templates(db_path, file_path, company=None, overwrite=False):
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(file_path):
        print(f"Error: JSON file not found at {file_path}", file=sys.stderr)
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    # Parse templates list
    items = []
    if isinstance(raw_data, dict):
        if "templates" in raw_data and isinstance(raw_data["templates"], list):
            items = raw_data["templates"]
        elif "rows" in raw_data or "vessels" in raw_data:
            items = [{
                "name": f"Imported Template {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "config": raw_data
            }]
        elif "name" in raw_data and ("config" in raw_data or "config_json" in raw_data):
            cfg = raw_data.get("config") or (json.loads(raw_data["config_json"]) if isinstance(raw_data.get("config_json"), str) else {})
            items = [{
                "name": raw_data["name"],
                "company_initial": raw_data.get("company_initial"),
                "company_name": raw_data.get("company_name"),
                "config": cfg
            }]
        else:
            print("Error: Format JSON tidak dikenali sebagai template builder.", file=sys.stderr)
            sys.exit(1)
    elif isinstance(raw_data, list):
        items = raw_data
    else:
        print("Error: File JSON harus berupa Object atau Array.", file=sys.stderr)
        sys.exit(1)

    if not items:
        print("Peringatan: Tidak ada template ditemukan dalam file JSON.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id, name, initial_pt FROM companies")
    all_comps = [dict(r) for r in cur.fetchall()]
    comp_by_id = {c["id"]: c for c in all_comps}
    comp_by_initial = {c["initial_pt"].strip().upper(): c for c in all_comps if c.get("initial_pt")}
    comp_by_name = {c["name"].strip().upper(): c for c in all_comps if c.get("name")}

    target_override_comp = None
    if company:
        for cid, cinfo in comp_by_id.items():
            if str(cid) == str(company) or (cinfo["initial_pt"] and cinfo["initial_pt"].lower() == str(company).lower()):
                target_override_comp = cinfo
                break
        if not target_override_comp:
            print(f"Error: Perusahaan target '{company}' tidak ditemukan di database.", file=sys.stderr)
            sys.exit(1)

    now = datetime.now().isoformat()
    imported_count = 0

    for item in items:
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

        # Resolve target company
        resolved_comp = target_override_comp
        if not resolved_comp:
            if item.get("company_initial") and str(item["company_initial"]).strip().upper() in comp_by_initial:
                resolved_comp = comp_by_initial[str(item["company_initial"]).strip().upper()]
            elif item.get("company_name") and str(item["company_name"]).strip().upper() in comp_by_name:
                resolved_comp = comp_by_name[str(item["company_name"]).strip().upper()]
            elif len(all_comps) == 1:
                resolved_comp = all_comps[0]

        if not resolved_comp:
            print(f"⚠️ Melewati template '{tpl_name}': Perusahaan tidak dapat dicocokkan (Gunakan opsi --company).")
            continue

        comp_id = resolved_comp["id"]
        comp_name = resolved_comp.get("initial_pt") or resolved_comp.get("name")

        # Check existing
        cur.execute("SELECT id FROM custom_builder_templates WHERE company_id = ? AND name = ?", (comp_id, tpl_name))
        existing_row = cur.fetchone()

        config_str = json.dumps(config_data)

        if existing_row and overwrite:
            tpl_id = existing_row["id"]
            cur.execute("UPDATE custom_builder_templates SET config_json = ?, updated_at = ? WHERE id = ?", (config_str, now, tpl_id))
            print(f"🔄 [UPDATE] ID {tpl_id}: '{tpl_name}' ({comp_name}) berhasil diperbarui.")
            imported_count += 1
        else:
            final_name = tpl_name
            if existing_row and not overwrite:
                final_name = f"{tpl_name} (Imported {datetime.now().strftime('%H%M%S')})"

            cur.execute(
                "INSERT INTO custom_builder_templates (company_id, name, config_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (comp_id, final_name, config_str, now, now)
            )
            new_id = cur.lastrowid
            print(f"✨ [CREATE] ID {new_id}: '{final_name}' ({comp_name}) berhasil dibuat.")
            imported_count += 1

    conn.commit()
    conn.close()
    print(f"\n🎉 Selesai: {imported_count} template berhasil diimpor ke database.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Report Builder Templates from JSON into SQLite DB")
    parser.add_argument("--file", "-f", required=True, help="Path ke file JSON template")
    parser.add_argument("--db", default=DEFAULT_DB, help="Path ke app_config.db")
    parser.add_argument("--company", help="ID atau Inisial Perusahaan tujuan (override)")
    parser.add_argument("--overwrite", action="store_true", help="Timpa template jika nama sudah ada di perusahaan target")
    args = parser.parse_args()

    import_templates(args.db, args.file, company=args.company, overwrite=args.overwrite)
