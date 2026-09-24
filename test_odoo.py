from app.config import settings
from app.odoo_api import OdooAPI

# We need the company db name. Let's assume the first company in the local sqlite db.
from app.db import SessionLocal
from app.models import Company

db = SessionLocal()
companies = db.query(Company).all()
if not companies:
    print("No companies found")
else:
    for c in companies:
        print(f"Company: {c.name}, DB: {c.target_db_name}")
        try:
            api = OdooAPI(db_name=c.target_db_name)
            reports = api.search_read('mis.report.instance', [], ['id', 'name'])
            print("Available Reports:", reports)
        except Exception as e:
            print("Error connecting:", e)
db.close()
