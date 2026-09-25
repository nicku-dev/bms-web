import json
from app.db import SessionLocal
from app.models import ReportTemplate, Company
from app.engine import ReportEngine

def clone_non_bms_to_bms():
    db = SessionLocal()
    bms = db.query(Company).filter(Company.name == 'PT. BINA MARITIM SEJATI').first()
    
    # Instance 2 is "KAPAL NON BMS" which was successfully fetched from Odoo
    non_bms_rt = db.query(ReportTemplate).filter(ReportTemplate.company_id == bms.id, ReportTemplate.odoo_report_id == 2).first()
    if not non_bms_rt or not non_bms_rt.skeleton_json:
        print("Non BMS template not found")
        return
        
    skel = json.loads(non_bms_rt.skeleton_json)
    
    # We want to create "Kapal BMS" (odoo_report_id=9001) using this skeleton
    eng = ReportEngine(bms.target_db_name)
    all_vessels = eng.get_all_vessels()
    vessels_bms = [v for v in all_vessels if not v['is_third_party']]
    
    h0 = []
    for v in vessels_bms:
        h0.append({"label": v['name'], "description": None, "colspan": 5})
    h0.append({"label": "Total", "description": None, "colspan": 5})
    
    skel['header'][0] = h0
    h1_base = [{"label": "Q1", "val": "q1"}, {"label": "Q2", "val": "q2"}, {"label": "Q3", "val": "q3"}, {"label": "Q4", "val": "q4"}, {"label": "YTD", "val": "ytd"}]
    skel['header'][1] = h1_base * len(h0)
    
    # Update or Create 9001
    rt_bms = db.query(ReportTemplate).filter(ReportTemplate.odoo_report_id == 9001).first()
    if not rt_bms:
        rt_bms = ReportTemplate(
            company_id=bms.id,
            odoo_report_id=9001,
            report_name='Triwulan - Kapal BMS 2026',
            is_active=True
        )
        db.add(rt_bms)
        
    rt_bms.skeleton_json = json.dumps(skel)
    rt_bms.last_sync = "Cloned from Non BMS (Correct COAs)"
    
    db.commit()
    print("Successfully cloned Non BMS to BMS!")

if __name__ == '__main__':
    clone_non_bms_to_bms()
