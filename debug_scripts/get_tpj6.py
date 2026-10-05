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

    print("LABELS FOUND:")
    for row in body:
        label = str(row.get('label', ''))
        if 'PENDAPATAN JASA' in label.upper() or 'TPJ' in label.upper():
            print(f"- {label}")

if __name__ == '__main__': main()
