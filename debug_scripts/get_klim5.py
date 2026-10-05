import json
from app.db import SessionLocal
from app.models import ReportTemplate

def main():
    db = SessionLocal()
    ts = db.query(ReportTemplate).all()
    for t in ts:
        matrix = json.loads(t.skeleton_json)
        found = False
        for row in matrix.get('body', []):
            label = str(row.get('label', '')).upper()
            if '4000' in label or '5000' in label:
                print(f"Row in {t.report_name}: {label}")
                found = True
        if found:
            print(f"Found in {t.report_name}")
            
if __name__ == '__main__': main()
