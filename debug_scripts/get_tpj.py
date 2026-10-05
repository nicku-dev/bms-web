import json
from app.db import SessionLocal
from app.models import Company, ReportTemplate
from app.compiler import FastMatrixCompiler

def main():
    db = SessionLocal()
    # Find active templates
    templates = db.query(ReportTemplate).all()
        
    # Assuming we want the first BMS/FPS template
    t = db.query(ReportTemplate).filter(ReportTemplate.report_name.ilike('%2026%')).first()
    if not t:
        print("Template not found!")
        return

    company = db.query(Company).filter(Company.id == t.company_id).first()
    matrix = json.loads(t.skeleton_json)

    report_type = 'fps'
    if 'BMS' in t.report_name.upper():
        report_type = 'non_fps'
    elif 'HO' in t.report_name.upper():
        report_type = 'ho'

    compiler = FastMatrixCompiler(
        db_name=company.target_db_name, 
        year=2026, 
        report_type=report_type, 
        odoo_report_id=t.odoo_report_id
    )
    
    compiled_matrix = compiler.compile(matrix)
    
    # Extract Total Pendapatan Jasa
    col_map = compiled_matrix.get('header', {}).get('col_map', [])
    body = compiled_matrix.get('body', [])
    
    tpj_row = None
    for row in body:
        label = str(row.get('label', '')).upper()
        if 'PENDAPATAN JASA' in label:
            tpj_row = row
            break
            
    if not tpj_row:
        print("PENDAPATAN JASA row not found!")
        return
        
    print(f"\nTotal Pendapatan Jasa Q3 ({t.report_name}):")
    total_q3 = 0.0
    for i, col in enumerate(col_map):
        if col.get('period') == 'q3':
            vessel = col.get('vessel_name', '')
            if i < len(tpj_row.get('cells', [])):
                val = tpj_row['cells'][i].get('val', 0.0)
                if val > 0:
                    print(f"{vessel} {val:,.2f}")
                    total_q3 += val
                    
    print(f"---")
    print(f"TOTAL: {total_q3:,.2f}")

if __name__ == '__main__':
    main()
