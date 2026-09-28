import sys, json, time, uuid
sys.path.append('.')
from app.odoo_api import OdooAPI
from app.db import SessionLocal
from app.models import Company, ReportTemplate

def build_true_skeleton():
    db = SessionLocal()
    
    print("\n" + "="*50)
    print(" INTERACTIVE TRUE SYNC (ODOO NATIVE COMPUTATION) ")
    print("="*50)
    
    companies = db.query(Company).filter(Company.is_active == True).all()
    print("\n=== DAFTAR PERUSAHAAN ===")
    for c in companies:
        print(f"[{c.id}] {c.name}")
    
    try:
        c_id = int(input("\nPilih ID Perusahaan: "))
    except ValueError:
        print("Input harus berupa angka!")
        return

    c = db.query(Company).filter(Company.id == c_id).first()
    if not c:
        print("Perusahaan tidak ditemukan.")
        return

    # Bypass Nginx to avoid 504 Gateway Timeout!
    local_odoo_url = "http://127.0.0.1:8069"
    print(f"\nMenghubungkan ke Odoo Lokal (Bypass Nginx): {local_odoo_url}...")
    api = OdooAPI(c.target_db_name, local_odoo_url, c.odoo_user, c.odoo_password)
    try:
        api.authenticate()
        print("Berhasil terhubung ke Odoo!")
    except Exception as e:
        print(f"Gagal login ke Odoo lokal: {e}")
        print("Mencoba fallback ke URL publik...")
        api = OdooAPI(c.target_db_name, c.server_url, c.odoo_user, c.odoo_password)
        try:
            api.authenticate()
        except Exception as e2:
            print(f"Gagal login ke Odoo publik: {e2}")
            return
        
    print("\nMengambil daftar laporan dari Odoo...")
    instances = api.execute_kw('mis.report.instance', 'search_read', [[], ['id', 'name', 'report_id']])
    
    print("\n=== DAFTAR LAPORAN ===")
    for idx, inst in enumerate(instances):
        print(f"[{idx}] {inst['name']} (ID Odoo: {inst['id']})")
    
    pilihan = input("\nPilih nomor laporan (atau 'ALL'): ").strip().upper()
    
    selected_instances = []
    if pilihan == 'ALL':
        selected_instances = instances
    else:
        try:
            idx = int(pilihan)
            selected_instances = [instances[idx]]
        except (ValueError, IndexError):
            print("Pilihan tidak valid.")
            return

    for inst in selected_instances:
        instance_id = inst['id']
        instance_name = inst['name']
        print(f"\nMemproses: {instance_name} (ID: {instance_id})...")
        
        periods = api.execute_kw('mis.report.instance.period', 'search_read', 
            [[['report_instance_id', '=', instance_id]], ['name', 'mode', 'type', 'manual_date_from', 'manual_date_to', 'date_from', 'date_to', 'analytic_domain', 'date_range_id', 'is_ytd']]
        )
        
        if not periods:
            print(f'-> GAGAL: Tidak ada periode.')
            continue
            
        print(f"Ditemukan {len(periods)} periode. Membuat instance temporary...")
        temp_name = f"TEMP CHUNK {uuid.uuid4()}"
        new_id = api.execute_kw('mis.report.instance', 'copy', [instance_id, {'name': temp_name}])
        if type(new_id) == list: new_id = new_id[0]
        
        temp_periods = api.execute_kw('mis.report.instance.period', 'search', [[['report_instance_id', '=', new_id]]])
        api.execute_kw('mis.report.instance.period', 'unlink', [temp_periods])
        
        matrices = []
        for i, p in enumerate(periods):
            print(f"  -> Menghitung periode {i+1}/{len(periods)}: {p['name']}...")
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
            
            # Compute via Odoo! This gives the true perfect matrix!
            matrix = api.execute_kw('mis.report.instance', 'compute', [[new_id]])
            matrices.append(matrix)
            
            api.execute_kw('mis.report.instance.period', 'unlink', [[pid]])
            
        print("Membersihkan temporary instance...")
        api.execute_kw('mis.report.instance', 'unlink', [[new_id]])
        
        print("Menggabungkan matrix...")
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
                    
        template = db.query(ReportTemplate).filter(
            ReportTemplate.company_id == c_id,
            ReportTemplate.odoo_report_id == instance_id
        ).first()
        
        if not template:
            template = ReportTemplate(
                company_id=c_id,
                odoo_report_id=instance_id,
                report_name=instance_name,
                is_active=True
            )
            db.add(template)
            db.commit() 
            
        template.skeleton_json = json.dumps(merged)
        template.last_sync = f'Ready (True Sync) {len(periods)} periods'
        db.commit()
        print('-> SUKSES TERSIMPAN!')
        
    print("\nSemua proses selesai! Silakan cek web dashboard Anda.")

if __name__ == '__main__':
    build_true_skeleton()
