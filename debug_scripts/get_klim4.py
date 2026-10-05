import json
from app.db import SessionLocal
from app.models import Company, ReportTemplate

def main():
    db = SessionLocal()
    t = db.query(ReportTemplate).filter(ReportTemplate.report_name.ilike('%2026%')).first()
    matrix = json.loads(t.skeleton_json)
    
    for row in matrix.get('body', []):
        label = str(row.get('label', '')).upper()
        if '4000' in label or '5000' in label:
            print(f"Row: {label}")
            
if __name__ == '__main__': main()
