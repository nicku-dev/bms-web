import sys, json, re
sys.path.append('.')
from app.odoo_api import OdooAPI
from app.db import SessionLocal
from app.models import Company, ReportTemplate

def build_manual_skeleton():
    db = SessionLocal()
    
    print("\n" + "="*40)
    print(" INTERACTIVE MANUAL SYNC ODOO REPORTS")
    print("="*40)
    
    # 1. Pilih Perusahaan
    companies = db.query(Company).filter(Company.is_active == True).all()
    print("\n=== DAFTAR PERUSAHAAN ===")
    for c in companies:
        print(f"[{c.id}] {c.name}")
    
    try:
        c_id = int(input("\nPilih ID Perusahaan yang ingin ditarik datanya: "))
    except ValueError:
        print("Input harus berupa angka!")
        return

    c = db.query(Company).filter(Company.id == c_id).first()
    if not c:
        print("Perusahaan tidak ditemukan.")
        return

    print(f"\nMenghubungkan ke Odoo untuk perusahaan: {c.name}...")
    api = OdooAPI(c.target_db_name, c.server_url, c.odoo_user, c.odoo_password)
    try:
        api.authenticate()
        print("Berhasil terhubung ke Odoo!")
    except Exception as e:
        print(f"Gagal login ke Odoo: {e}")
        return
        
    # 2. Ambil daftar laporan dari Odoo
    print("\nMengambil daftar laporan dari Odoo...")
    instances = api.execute_kw('mis.report.instance', 'search_read', [[], ['id', 'name', 'report_id']])
    
    print("\n=== DAFTAR LAPORAN TERSEDIA DI ODOO ===")
    for idx, inst in enumerate(instances):
        print(f"[{idx}] {inst['name']} (ID Odoo: {inst['id']})")
    print("[ALL] Ketik 'ALL' untuk menarik SEMUA laporan sekaligus")
    
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

    # 3. Proses penarikan
    for inst in selected_instances:
        instance_id = inst['id']
        instance_name = inst['name']
        print(f"\nMemproses: {instance_name} (ID: {instance_id})...")
        
        periods = api.execute_kw('mis.report.instance.period', 'search_read', 
            [[['report_instance_id', '=', instance_id]], ['name']]
        )
        
        if not periods:
            print(f'-> GAGAL: Laporan tidak memiliki kolom periode di Odoo.')
            continue
            
        report_id = inst['report_id'][0] if inst.get('report_id') else None
        if not report_id:
            print("-> GAGAL: Base report tidak ditemukan.")
            continue
            
        kpis = api.execute_kw('mis.report.kpi', 'search_read', 
            [[['report_id', '=', report_id]], ['name', 'description', 'expression']]
        )
        
        header = [[], []]
        for p in periods:
            header[0].append({'val': p['name'], 'colspan': 5})
            for sub in ['Q1', 'Q2', 'Q3', 'Q4', 'YTD']:
                header[1].append({'val': sub})
                
        body = []
        for kpi in kpis:
            tag_name = None
            if kpi.get('expression'):
                match = re.search(r'tag_ids\.name","=","([^"]+)"', kpi['expression'])
                if match:
                    tag_name = match.group(1)
            
            val_c = f"'tag_ids.name', '=', '{tag_name}'" if tag_name else ""
            
            row_cells = []
            for _ in range(len(periods) * 5):
                row_cells.append({'val_c': val_c, 'val': 0, 'val_r': '0.00'})
                
            body.append({
                'label': kpi['description'],
                'cells': row_cells
            })
            
        skeleton = {'header': header, 'body': body}
        
        # Insert or Update DB
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
            
        template.skeleton_json = json.dumps(skeleton)
        template.last_sync = f'Ready (Interactive Terminal)'
        db.commit()
        print('-> SUKSES TERSIMPAN!')
        
    print("\nSemua proses selesai! Silakan cek web dashboard Anda.")

if __name__ == '__main__':
    build_manual_skeleton()
