import sqlite3
import json
import re

def migrate_bms_report():
    db_path = "/Users/nickufritzie/odoo-dev-18/bms-web/app_config.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Fetch old skeleton
    cursor.execute("SELECT skeleton_json FROM report_templates WHERE report_name = 'Laporan Triwulan - Kapal BMS 2026'")
    row = cursor.fetchone()
    if not row:
        print("Laporan Triwulan - Kapal BMS 2026 not found in report_templates!")
        return
        
    skel = json.loads(row[0])
    
    # 2. Create new native report
    cursor.execute("INSERT INTO bms_reports (name, description) VALUES (?, ?)", ("Native: Laporan Triwulan - Kapal BMS 2026", "Migrated from skeleton JSON"))
    report_id = cursor.lastrowid
    print(f"Created report ID: {report_id}")
    
    # 3. Iterate over body
    seq = 10
    
    for item in skel.get('body', []):
        label = item.get('label', '')
        var_name = item.get('name', '')
        desc = item.get('description', '')
        style = item.get('style', '')
        cells = item.get('cells', [])
        
        is_pct = '%' in label or 'font-style: italic' in style
        
        val_c = ""
        # Get q1 val_c to figure out row_type
        if cells and len(cells) > 0:
            val_c = cells[0].get('val_c', '')
            
        row_type = 'header'
        tag_name = None
        formula = None
        
        # Analyze val_c
        # e.g. "pendapatan_jasa.q1 = balp[(\"tag_ids.name\",\"=\",\"TW_PENDAPATAN JASA\")][('date', '>=', '2026-01-01'),('date', '<=', '2026-03-31')]"
        if '=' in val_c:
            rhs = val_c.split('=', 1)[1].strip()
            if not rhs:
                row_type = 'header'
            elif 'balp[("tag_ids.name"' in rhs or "balp[('tag_ids.name'" in rhs:
                row_type = 'tag_query'
                # Extract tag
                match = re.search(r'tag_ids\.name","=","([^"]+)"', rhs)
                if not match:
                    match = re.search(r"tag_ids\.name','=','([^']+)'", rhs)
                
                if match:
                    tag_name = match.group(1)
                else:
                    tag_name = desc # fallback to description
            else:
                row_type = 'formula'
                formula = rhs
        
        cursor.execute("""
            INSERT INTO bms_report_rows 
            (report_id, sequence, label, variable_name, row_type, tag_name, formula, is_percentage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (report_id, seq, label, var_name, row_type, tag_name, formula, is_pct))
        
        seq += 10
        
    conn.commit()
    conn.close()
    print("Migration finished!")

if __name__ == '__main__':
    migrate_bms_report()
