import json
from app.db import SessionLocal
from app.models import Company, ReportTemplate
from app.odoo_api import OdooAPI
from app.engine import ReportEngine

def sync_bms_safe():
    db = SessionLocal()
    c = db.query(Company).filter(Company.id == 2).first()
    if not c:
        print("BMS company not found")
        return

    api = OdooAPI(c.target_db_name, c.server_url, c.odoo_user, c.odoo_password)
    eng = ReportEngine(c.target_db_name)
    all_vessels = eng.get_all_vessels()
    
    # 1. We already synced Instance 2 (Non BMS) and Instance 3 (Head Office) successfully.
    # Now we just need Instance 1 (Kapal BMS).
    instance_id = 1
    
    print("Copying Instance 1 to a temporary instance...")
    try:
        new_id_res = api.execute_kw('mis.report.instance', 'copy', [[instance_id]])
        new_id = new_id_res[0] if isinstance(new_id_res, list) else new_id_res
        
        # Get periods of the new instance
        periods = api.search_read('mis.report.instance.period', [['report_instance_id', '=', new_id]], ['id'])
        
        # Keep only the first period, delete the rest to speed up computation
        if len(periods) > 1:
            pids_to_delete = [p['id'] for p in periods[1:]]
            api.execute_kw('mis.report.instance.period', 'unlink', [pids_to_delete])
            
        # Change the remaining period to 1970
        first_pid = periods[0]['id']
        api.execute_kw('mis.report.instance.period', 'write', [[first_pid], {'date_from': '1970-01-01', 'date_to': '1970-01-01'}])
        
        print("Computing temporary instance...")
        matrix_list = api.execute_kw('mis.report.instance', 'compute', [[new_id]])
        matrix = matrix_list[0] if isinstance(matrix_list, list) and len(matrix_list) > 0 else matrix_list
        
        print("Unlinking temporary instance...")
        api.execute_kw('mis.report.instance', 'unlink', [[new_id]])
        
        # We got the matrix! Now let's fix its header to contain ALL BMS vessels.
        vessels_bms = [v for v in all_vessels if not v['is_third_party']]
        
        h0 = []
        for v in vessels_bms:
            h0.append({"label": v['name'], "description": None, "colspan": 5})
        h0.append({"label": "Total", "description": None, "colspan": 5})
        
        matrix['header'][0] = h0
        
        h1_base = [{"label": "Q1", "val": "q1"}, {"label": "Q2", "val": "q2"}, {"label": "Q3", "val": "q3"}, {"label": "Q4", "val": "q4"}, {"label": "YTD", "val": "ytd"}]
        matrix['header'][1] = h1_base * len(h0)
        
        # Save to DB
        t = db.query(ReportTemplate).filter(ReportTemplate.company_id == c.id, ReportTemplate.odoo_report_id == instance_id).first()
        if not t:
            t = ReportTemplate(
                company_id=c.id,
                odoo_report_id=instance_id,
                report_name='Triwulan - Kapal BMS - 2026',
                is_active=True
            )
            db.add(t)
            
        t.skeleton_json = json.dumps(matrix)
        t.last_sync = "Safely synced via clone"
        db.commit()
        
        print("Instance 1 synced successfully with correct BMS COAs!")
        
    except Exception as e:
        print("Error:", e)
        db.rollback()

if __name__ == '__main__':
    sync_bms_safe()
