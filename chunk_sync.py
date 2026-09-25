import sys, json, time, uuid
sys.path.append('.')
from app.odoo_api import OdooAPI
from app.db import SessionLocal
from app.models import Company, ReportTemplate

def run_chunk_sync(company_id, instance_id):
    db = SessionLocal()
    c = db.query(Company).filter(Company.id == company_id).first()
    api = OdooAPI(c.target_db_name, c.server_url, c.odoo_user, c.odoo_password)
    api.authenticate()
    
    print(f"Fetching original periods for instance {instance_id}...")
    periods = api.execute_kw('mis.report.instance.period', 'search_read', 
        [[['report_instance_id', '=', instance_id]], ['name', 'mode', 'type', 'manual_date_from', 'manual_date_to', 'date_from', 'date_to', 'analytic_domain', 'date_range_id', 'is_ytd']]
    )
    print(f"Found {len(periods)} periods.")
    
    # We create a dummy instance
    temp_name = f"TEMP CHUNK SKELETON {uuid.uuid4()}"
    print(f"Creating temp instance: {temp_name}")
    new_id = api.execute_kw('mis.report.instance', 'copy', [instance_id, {'name': temp_name}])
    
    if type(new_id) == list: new_id = new_id[0]
    
    # Delete all periods copied to the temp instance
    temp_periods = api.execute_kw('mis.report.instance.period', 'search', [[['report_instance_id', '=', new_id]]])
    api.execute_kw('mis.report.instance.period', 'unlink', [temp_periods])
    
    matrices = []
    
    for i, p in enumerate(periods):
        print(f"Processing period {i+1}/{len(periods)}: {p['name']}...")
        # Create just this one period in temp instance
        period_vals = {
            'report_instance_id': new_id,
            'name': p['name'],
            'mode': p['mode'] or 'fix',
            'manual_date_from': p['manual_date_from'],
            'manual_date_to': p['manual_date_to'],
            'date_range_id': p['date_range_id'][0] if p.get('date_range_id') else False,
            'analytic_domain': p['analytic_domain']
        }
        pid = api.execute_kw('mis.report.instance.period', 'create', [period_vals])
        
        # Compute matrix for this single period
        matrix = api.execute_kw('mis.report.instance', 'compute', [[new_id]])
        matrices.append(matrix)
        
        # Clean up this period
        api.execute_kw('mis.report.instance.period', 'unlink', [[pid]])
        
    print("Deleting temp instance...")
    api.execute_kw('mis.report.instance', 'unlink', [[new_id]])
    
    print("Merging matrices...")
    merged = {"header": [[], []], "body": []}
    for i, m in enumerate(matrices):
        if len(merged["header"][0]) == 0 and len(m["header"]) > 0:
            merged["header"] = [[] for _ in range(len(m["header"]))]
            
        for h_idx in range(len(m.get("header", []))):
            merged["header"][h_idx].extend(m["header"][h_idx])
            
        if i == 0:
            merged["body"] = m.get("body", [])
        else:
            for j, row in enumerate(m.get("body", [])):
                merged["body"][j]["cells"].extend(row.get("cells", []))
                
    print("Saving to DB...")
    template = db.query(ReportTemplate).filter(
        ReportTemplate.company_id == company_id, 
        ReportTemplate.odoo_report_id == instance_id
    ).first()
    
    if template:
        template.skeleton_json = json.dumps(merged)
        template.last_sync = f"Ready (Chunked) {len(periods)} periods"
        db.commit()
    print("Done!")

if __name__ == '__main__':
    run_chunk_sync(2, 1)
