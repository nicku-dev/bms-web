import json
from app.models import ReportTemplate, Company
from app.database import SessionLocal
db = SessionLocal()
try:
    c = db.query(Company).first()
    matrix = {"dummy": "data" * 10000}
    t = ReportTemplate(company_id=c.id, odoo_report_id=999, report_name="Test")
    t.skeleton_json = json.dumps(matrix)
    db.add(t)
    db.commit()
    print("SUCCESS")
except Exception as e:
    import traceback
    traceback.print_exc()
