import time
from app.db import SessionLocal
from app.models import Company, ReportTemplate
from app.odoo_api import OdooAPI

def run_test():
    print("=" * 50)
    print("TEST HEAVY ODOO MIS REPORT")
    print("=" * 50)
    
    db = SessionLocal()
    company = db.query(Company).filter(Company.is_active == True).first()
    if not company:
        print("[-] Tidak ada perusahaan aktif ditemukan di SQLite.")
        return

    print(f"[+] Menggunakan perusahaan: {company.name}")
    print(f"    URL: {company.server_url}")
    print(f"    DB: {company.target_db_name}")
    print(f"    User: {company.odoo_user}")

    # Ambil template pertama yang ada
    template = db.query(ReportTemplate).filter(ReportTemplate.company_id == company.id).first()
    if not template:
        print("[-] Tidak ada template laporan ditemukan untuk perusahaan ini.")
        return
        
    print(f"[+] Mencoba test tarik skeleton untuk Report: {template.report_name} (ID: {template.odoo_report_id})")

    try:
        # Override the timeout manually just for this test
        api = OdooAPI(
            db_name=company.target_db_name, 
            url=company.server_url, 
            username=company.odoo_user, 
            password=company.odoo_password
        )
        # We manually change the session timeout strategy or just let requests handle the timeout
        print("[+] Berhasil login ke Odoo.")
        
        print(f"[!] Mulai menarik skeleton dari Odoo... (Ini bisa memakan waktu lama)")
        start_time = time.time()
        
        # Panggil generate_mis_report yang akan melakukan request ke Odoo
        matrix = api.generate_mis_report(template.odoo_report_id, '1970-01-01', '1970-01-01')
        
        end_time = time.time()
        duration = end_time - start_time
        
        if matrix:
            print(f"\n[SUCCESS] Berhasil menarik skeleton dalam waktu {duration:.2f} detik!")
            print(f"[INFO] Ukuran skeleton JSON: {len(str(matrix))} karakter")
        else:
            print(f"\n[FAIL] Selesai dalam {duration:.2f} detik, tapi matrix kosong/None.")
        
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        print(f"\n[ERROR] Gagal saat menarik skeleton: {e}")
        print(f"[INFO] Gagal setelah menunggu selama {duration:.2f} detik.")

if __name__ == '__main__':
    run_test()
