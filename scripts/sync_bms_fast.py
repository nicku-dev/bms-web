import json
from app.db import SessionLocal
from app.models import Company, ReportTemplate
from app.odoo_api import OdooAPI

def force_sync_bms():
    db = SessionLocal()
    c = db.query(Company).filter(Company.id == 2).first()
    if not c:
        print("BMS company not found")
        return

    api = OdooAPI(c.target_db_name, c.server_url, c.odoo_user, c.odoo_password)
    
    # We want to sync instance IDs 1, 2, 3
    for instance_id in [1, 2, 3]:
        print(f"Processing Instance {instance_id}...")
        
        # 1. Fetch periods
        periods = api.search_read('mis.report.instance.period', [['report_instance_id', '=', instance_id]], ['id', 'date_from', 'date_to'])
        
        # Save old dates to revert later
        old_dates = {p['id']: {'date_from': p['date_from'], 'date_to': p['date_to']} for p in periods}
        
        try:
            # 2. Update all periods to 1970
            for p in periods:
                api.execute_kw('mis.report.instance.period', 'write', [[p['id']], {'date_from': '1970-01-01', 'date_to': '1970-01-01'}])
                
            print(f"Periods for Instance {instance_id} temporarily set to 1970. Computing...")
            
            # 3. Compute matrix
            matrix = api.execute_kw('mis.report.instance', 'compute', [[instance_id]])
            
            # 4. Save to local DB
            # First, check if template exists.
            t = db.query(ReportTemplate).filter(ReportTemplate.company_id == 2, ReportTemplate.odoo_report_id == instance_id).first()
            if not t:
                # Get name
                info = api.search_read('mis.report.instance', [['id', '=', instance_id]], ['name'])
                name = info[0]['name'] if info else f"Report {instance_id}"
                t = ReportTemplate(
                    company_id=c.id,
                    odoo_report_id=instance_id,
                    report_name=name,
                    is_active=True
                )
                db.add(t)
            
            t.skeleton_json = json.dumps(matrix)
            t.last_sync = "Fast Synced via Script"
            db.commit()
            print(f"Instance {instance_id} synced successfully!")
            
        except Exception as e:
            print(f"Error syncing {instance_id}: {e}")
            db.rollback()
            
        finally:
            # 5. Revert dates
            print(f"Reverting dates for Instance {instance_id}...")
            for pid, dates in old_dates.items():
                try:
                    api.execute_kw('mis.report.instance.period', 'write', [[pid], dates])
                except Exception as e:
                    print(f"Failed to revert period {pid}: {e}")

    print("All done!")

if __name__ == '__main__':
    force_sync_bms()
