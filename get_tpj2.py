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
    
    if isinstance(compiled, list):
        body = compiled
        col_map = []
    else:
        body = compiled.get('body', [])
        col_map = compiled.get('header', {}).get('col_map', [])
        if not col_map and hasattr(compiler, 'col_map'):
            col_map = compiler.col_map
            
    # Try to find col_map if still empty
    if not col_map:
        if isinstance(matrix, dict) and 'header' in matrix:
            col_map = matrix['header'].get('col_map', [])
            
    print(f"ColMap length: {len(col_map)}")
    
    tpj_row = None
    for row in body:
        if 'PENDAPATAN JASA' in str(row.get('label', '')).upper():
            tpj_row = row
            break
            
    if not tpj_row:
        print("Not found")
        return
        
    print("VALUES:")
    for i, col in enumerate(col_map):
        if col.get('period') == 'q3':
            v = col.get('vessel_name', '')
            val = tpj_row['cells'][i].get('val', 0.0) if i < len(tpj_row['cells']) else 0.0
            print(f"- {v}: {val:,.2f}")

if __name__ == '__main__': main()
