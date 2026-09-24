import sys
import os
import asyncio

# Setup path so it can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import background_sync_templates
from app.db import SessionLocal
from app.models import Company, ReportTemplate
from pydantic import BaseModel

class SyncItem(BaseModel):
    odoo_report_id: int
    report_name: str

def run_test():
    db = SessionLocal()
    company = db.query(Company).filter(Company.is_active == True).first()
    if not company:
        print("No active company")
        return
        
    template = db.query(ReportTemplate).filter(ReportTemplate.company_id == company.id).first()
    if not template:
        print("No template")
        return
        
    item = SyncItem(odoo_report_id=template.odoo_report_id, report_name=template.report_name)
    print(f"Syncing item: {item.odoo_report_id}")
    
    background_sync_templates(company.id, [item])
    print("Done background sync")

if __name__ == '__main__':
    run_test()
