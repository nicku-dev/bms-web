import json
from app.db import SessionLocal
from app.models import Company, ReportTemplate
from app.compiler import FastMatrixCompiler

def main():
    db = SessionLocal()
    t = db.query(ReportTemplate).filter(ReportTemplate.report_name.ilike('%2026%')).first()
    if not t: return

    company = db.query(Company).filter(Company.id == t.company_id).first()
    matrix = json.loads(t.skeleton_json)

    report_type = 'fps'
    if 'BMS' in t.report_name.upper(): report_type = 'non_fps'

    compiler = FastMatrixCompiler(db_name=company.target_db_name, year=2026, report_type=report_type, odoo_report_id=t.odoo_report_id)
    compiled = compiler.compile(matrix)
    body = compiled.get('body', [])

    col_map = []
    h0 = matrix['header'][0]
    h1 = matrix['header'][1]
    
    h0_cells = h0.get('cells', []) if isinstance(h0, dict) else h0
    h1_cells = h1.get('cells', []) if isinstance(h1, dict) else h1
    
    vessels = []
    for cell in h0_cells:
        for _ in range(cell.get('colspan', 1)):
            vessels.append(str(cell.get('val', '')).strip())
    
    for i, cell in enumerate(h1_cells):
        if i < len(vessels):
            val_c = str(cell.get('val_c', '')).lower()
            period = 'ytd' if 'ytd' in val_c else 'total' if 'total' in val_c else 'q'
            if period == 'q':
                if 'q1' in val_c: period = 'q1'
                elif 'q2' in val_c: period = 'q2'
                elif 'q3' in val_c: period = 'q3'
                elif 'q4' in val_c: period = 'q4'
            col_map.append({'vessel_name': vessels[i], 'period': period})
            
    tpj_row = None
    for row in body:
        label = str(row.get('label', '')).upper()
        if 'TOTAL PENDAPATAN JASA' in label or 'TPJ' in label:
            tpj_row = row
            # Keep searching to find the last match just in case
            
    if not tpj_row:
        print("Not found")
        return
        
    print(f"Total Pendapatan Jasa Q3:")
    total_q3 = 0.0
    for i, col in enumerate(col_map):
        if col.get('period') == 'q3':
            v = col.get('vessel_name', '')
            val = tpj_row['cells'][i].get('val', 0.0) if i < len(tpj_row['cells']) else 0.0
            if val != 0:
                print(f"{v}: {val:,.2f}")
                if 'TOTAL' not in v.upper():
                    total_q3 += val

if __name__ == '__main__': main()
