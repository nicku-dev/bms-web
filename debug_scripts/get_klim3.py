import json
from app.db import SessionLocal
from app.models import Company, ReportTemplate

def main():
    db = SessionLocal()
    t = db.query(ReportTemplate).filter(ReportTemplate.report_name.ilike('%2026%')).first()
    matrix = json.loads(t.skeleton_json)
    
    for row in matrix.get('body', []):
        label = str(row.get('label', '')).upper()
        if 'KLAIM SUSUT' in label or 'CHARTER KAPAL' in label or '4000011000' in label or '5000092000' in label:
            print(f"Row: {label}")
            cells = row.get('cells', [])
            if cells:
                print(cells[0].get('val_c', ''))
            print("---")
            
if __name__ == '__main__': main()
