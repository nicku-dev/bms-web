import json
import sys
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import ReportTemplate, Company
from app.engine import ReportEngine

def clone_reports():
    db = SessionLocal()
    
    bms = db.query(Company).filter(Company.name == 'PT. BINA MARITIM SEJATI').first()
    if not bms:
        print("BMS company not found")
        return
        
    fps_report = db.query(ReportTemplate).filter(ReportTemplate.id == 1).first()
    if not fps_report or not fps_report.skeleton_json:
        print("FPS report 1 not found or no skeleton")
        return
        
    skeleton = json.loads(fps_report.skeleton_json)
    
    eng = ReportEngine(bms.target_db_name)
    all_vessels = eng.get_all_vessels()
    
    vessels_bms = [v for v in all_vessels if not v['is_third_party']]
    vessels_non_bms = [v for v in all_vessels if v['is_third_party']]
    
    # 1. Kapal BMS - 2026
    skel_bms = json.loads(fps_report.skeleton_json) # deep copy
    h0 = []
    for v in vessels_bms:
        h0.append({"label": v['name'], "description": None, "colspan": 5})
    h0.append({"label": "Total", "description": None, "colspan": 5})
    skel_bms['header'][0] = h0
    
    # Duplicate h1 to match the new colspan
    h1_base = [{"label": "Q1", "val": "q1"}, {"label": "Q2", "val": "q2"}, {"label": "Q3", "val": "q3"}, {"label": "Q4", "val": "q4"}, {"label": "YTD", "val": "ytd"}]
    skel_bms['header'][1] = h1_base * len(h0)
    
    rt_bms = ReportTemplate(
        company_id=bms.id,
        odoo_report_id=9001,
        report_name='Triwulan - Kapal BMS 2026',
        skeleton_json=json.dumps(skel_bms),
        last_sync='Cloned from FPS'
    )
    db.add(rt_bms)
    
    # 2. KAPAL NON BMS - 2026
    skel_non_bms = json.loads(fps_report.skeleton_json)
    h0_non = []
    for v in vessels_non_bms:
        h0_non.append({"label": v['name'], "description": None, "colspan": 5})
    h0_non.append({"label": "Total", "description": None, "colspan": 5})
    skel_non_bms['header'][0] = h0_non
    skel_non_bms['header'][1] = h1_base * len(h0_non)
    
    rt_non_bms = ReportTemplate(
        company_id=bms.id,
        odoo_report_id=9002,
        report_name='Triwulan - Kapal Non BMS 2026',
        skeleton_json=json.dumps(skel_non_bms),
        last_sync='Cloned from FPS'
    )
    db.add(rt_non_bms)
    
    # 3. Head Office - 2026
    skel_ho = json.loads(fps_report.skeleton_json)
    h0_ho = [{"label": "Head Office", "description": None, "colspan": 5}]
    skel_ho['header'][0] = h0_ho
    skel_ho['header'][1] = h1_base
    
    rt_ho = ReportTemplate(
        company_id=bms.id,
        odoo_report_id=9003,
        report_name='Triwulan - Head Office 2026',
        skeleton_json=json.dumps(skel_ho),
        last_sync='Cloned from FPS'
    )
    db.add(rt_ho)
    
    db.commit()
    print("3 BMS Reports created successfully!")

if __name__ == "__main__":
    clone_reports()
