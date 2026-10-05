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

    print("SKELETON CELLS FOR PENDAPATAN JASA:")
    for row in matrix.get('body', []):
        label = str(row.get('label', '')).upper()
        if label == 'PENDAPATAN JASA':
            print(json.dumps(row.get('cells', [])[:2], indent=2))
            break

if __name__ == '__main__': main()
