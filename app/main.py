from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import xmlrpc.client
import ssl
import json
from app.db import SessionLocal, init_db
from app.models import User, Company
from app.config import settings

app = FastAPI(title="ISA Fleet Report - Modern View")

# Mount static files (for css, js, images if needed)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates setup
templates = Jinja2Templates(directory="app/templates")

# Initialize DB on startup
init_db()

class LoginRequest(BaseModel):
    username: str
    password: str

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    if "session_token" not in request.cookies:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    if "session_token" not in request.cookies:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/login", response_class=HTMLResponse)
async def read_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.post("/api/login")
async def api_login(req: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username, User.is_active == True).first()
        if not user:
            return JSONResponse(status_code=401, content={"status": "error", "message": "Username tidak ditemukan atau tidak aktif."})

        authenticated = False
        
        if req.username in ["admin_isa", "admin_dev"] or user.role == "admin":
            if user.password == req.password:
                authenticated = True
        else:
            # XML-RPC Authentication with Odoo
            context = ssl._create_unverified_context()
            common = xmlrpc.client.ServerProxy(f'{settings.odoo_url}/xmlrpc/2/common', context=context)
            
            dbs_to_check = []
            if user.company_id:
                dbs_to_check.append(user.company.target_db_name)
            else:
                companies = db.query(Company).filter(Company.is_active == True).all()
                dbs_to_check = [c.target_db_name for c in companies]
                
            for db_name in dbs_to_check:
                try:
                    uid = common.authenticate(db_name, req.username, req.password, {})
                    if uid:
                        authenticated = True
                        break
                except Exception:
                    pass
                    
        if authenticated:
            # Set a simple cookie or return success for JS to redirect
            response = JSONResponse(content={"status": "success", "message": "Login berhasil"})
            response.set_cookie(key="session_token", value=req.username, httponly=True, max_age=86400)
            return response
        else:
            return JSONResponse(status_code=401, content={"status": "error", "message": "Password salah."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()

@app.get("/api/companies")
async def api_get_companies(request: Request):
    username = request.cookies.get("session_token")
    if not username:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
        
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        companies_data = []
        if user and user.company_id:
            companies_data = [{"id": user.company.id, "name": user.company.name}]
        else:
            companies = db.query(Company).filter(Company.is_active == True).all()
            companies_data = [{"id": c.id, "name": c.name} for c in companies]
        return {"status": "success", "companies": companies_data}
    finally:
        db.close()

@app.get("/api/reports/{company_id}")
async def api_get_reports(company_id: int, request: Request):
    username = request.cookies.get("session_token")
    if not username:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id, Company.is_active == True).first()
        if not company:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Perusahaan tidak ditemukan."})

        from app.models import ReportTemplate
        synced_reports = db.query(ReportTemplate).filter(ReportTemplate.company_id == company.id, ReportTemplate.is_active == True).all()
        reports = [{"id": r.odoo_report_id, "name": r.report_name} for r in synced_reports]
        
        return {"status": "success", "reports": reports}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()

from typing import Optional

class CompanyRequest(BaseModel):
    initial_pt: Optional[str] = None
    name: str
    server_url: Optional[str] = None
    target_db_name: str
    odoo_user: Optional[str] = None
    odoo_password: Optional[str] = None

@app.get("/config", response_class=HTMLResponse)
async def read_config(request: Request):
    return templates.TemplateResponse(request=request, name="config.html")

@app.get("/api/admin/companies")
async def api_admin_companies():
    db = SessionLocal()
    companies = db.query(Company).filter(Company.is_active == True).all()
    data = []
    for c in companies:
        data.append({
            "id": c.id, 
            "initial_pt": c.initial_pt,
            "name": c.name, 
            "server_url": c.server_url,
            "target_db_name": c.target_db_name,
            "odoo_user": c.odoo_user,
            "odoo_password": "🔑 Tersimpan rahasia" if c.odoo_password else ""
        })
    return {"status": "success", "data": data}

@app.post("/api/admin/companies")
async def api_admin_add_company(req: CompanyRequest):
    db = SessionLocal()
    c = Company(
        initial_pt=req.initial_pt,
        name=req.name, 
        server_url=req.server_url,
        target_db_name=req.target_db_name,
        odoo_user=req.odoo_user,
        odoo_password=req.odoo_password
    )
    db.add(c)
    db.commit()
    return {"status": "success", "message": "Perusahaan ditambahkan"}

class CompanyEditRequest(BaseModel):
    initial_pt: Optional[str] = None
    name: str
    server_url: Optional[str] = None
    target_db_name: str
    odoo_user: Optional[str] = None
    odoo_password: Optional[str] = None

@app.put("/api/admin/companies/{company_id}")
async def api_admin_edit_company(company_id: int, req: CompanyEditRequest):
    db = SessionLocal()
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        return {"status": "error", "message": "Perusahaan tidak ditemukan"}
    
    c.initial_pt = req.initial_pt
    c.name = req.name
    c.server_url = req.server_url
    c.target_db_name = req.target_db_name
    c.odoo_user = req.odoo_user
    if req.odoo_password:
        c.odoo_password = req.odoo_password
        
    db.commit()
    return {"status": "success", "message": "Perusahaan berhasil diperbarui"}

@app.delete("/api/admin/companies/{company_id}")
async def api_admin_delete_company(company_id: int):
    db = SessionLocal()
    c = db.query(Company).filter(Company.id == company_id).first()
    if c:
        c.is_active = False
        db.commit()
    return {"status": "success", "message": "Perusahaan dihapus"}
@app.get("/api/admin/odoo_reports/{company_id}")
async def api_admin_odoo_reports(company_id: int):
    db = SessionLocal()
    from app.odoo_api import OdooAPI
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Company not found"})
    try:
        api = OdooAPI(
            db_name=company.target_db_name, 
            url=company.server_url, 
            username=company.odoo_user, 
            password=company.odoo_password
        )
        reports = api.search_read('mis.report.instance', [], ['id', 'name'])
        return {"status": "success", "data": reports}
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Gagal terhubung ke Odoo ({company.name}): {str(e)}"})

class SyncItem(BaseModel):
    odoo_report_id: int
    report_name: str

class SyncTemplatesRequest(BaseModel):
    company_id: int
    templates: list[SyncItem]

@app.post("/api/admin/sync_templates")
async def api_admin_sync_templates(req: SyncTemplatesRequest):
    import json
    from datetime import datetime
    from app.odoo_api import OdooAPI
    from app.models import ReportTemplate
    
    db = SessionLocal()
    company = db.query(Company).filter(Company.id == req.company_id, Company.is_active == True).first()
    if not company:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Company not found"})
        
    try:
        api = OdooAPI(
            db_name=company.target_db_name, 
            url=company.server_url, 
            username=company.odoo_user, 
            password=company.odoo_password
        )
        
        for item in req.templates:
            matrix = api.generate_mis_report(item.odoo_report_id, '1970-01-01', '1970-01-01')
            
            template = db.query(ReportTemplate).filter(
                ReportTemplate.company_id == company.id,
                ReportTemplate.odoo_report_id == item.odoo_report_id
            ).first()
            
            if not template:
                template = ReportTemplate(company_id=company.id, odoo_report_id=item.odoo_report_id, report_name=item.report_name)
                db.add(template)
            elif not template.report_name:
                template.report_name = item.report_name
                
            template.skeleton_json = json.dumps(matrix)
            template.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        db.commit()
        return {"status": "success", "message": f"{len(req.templates)} Template berhasil disinkronisasi"}
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": f"Gagal narik skeleton Odoo ({company.name}): {str(e)}"})

@app.get("/api/admin/templates")
async def api_admin_templates():
    db = SessionLocal()
    from app.models import ReportTemplate
    templates = db.query(ReportTemplate).join(Company).all()
    data = []
    for t in templates:
        data.append({
            "id": t.id,
            "company_initial": t.company.initial_pt or t.company.name,
            "report_name": t.report_name,
            "odoo_report_id": t.odoo_report_id,
            "is_active": t.is_active,
            "last_sync": t.last_sync
        })
    return {"status": "success", "data": data}

@app.get("/api/admin/template/{template_id}")
async def api_admin_template_detail(template_id: int):
    db = SessionLocal()
    from app.models import ReportTemplate
    try:
        t = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
        if not t:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Template tidak ditemukan"})
            
        data = {
            "id": t.id,
            "report_name": t.report_name,
            "last_sync": t.last_sync,
            "rows": [],
            "cols": []
        }
        
        if t.skeleton_json:
            skeleton = json.loads(t.skeleton_json)
            if "body" in skeleton:
                for row in skeleton["body"]:
                    label = row.get("label", "")
                    if label:
                        data["rows"].append(label)
                        
            if "header" in skeleton and len(skeleton["header"]) > 0:
                for col in skeleton["header"][0].get("cols", []):
                    data["cols"].append(col.get("label", ""))
                    
        return {"status": "success", "data": data}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()

class TemplateUpdateRequest(BaseModel):
    report_name: str
    is_active: Optional[bool] = True

@app.put("/api/admin/template/{template_id}")
async def api_admin_update_template(template_id: int, req: TemplateUpdateRequest):
    db = SessionLocal()
    from app.models import ReportTemplate
    try:
        t = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
        if not t:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Template tidak ditemukan"})
        
        t.report_name = req.report_name.strip()
        if req.is_active is not None:
            t.is_active = req.is_active
            
        db.commit()
        return {"status": "success", "message": "Template berhasil diperbarui"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()

@app.delete("/api/admin/template/{template_id}")
async def api_admin_delete_template(template_id: int):
    db = SessionLocal()
    from app.models import ReportTemplate
    try:
        t = db.query(ReportTemplate).filter(ReportTemplate.id == template_id).first()
        if not t:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Template tidak ditemukan"})
        
        db.delete(t)
        db.commit()
        return {"status": "success", "message": "Template berhasil dihapus"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()



class ReportRequest(BaseModel):
    company_id: int
    template: str
    template_name: str
    force_refresh: bool = False

@app.post("/api/generate_report")
async def api_generate_report(req: ReportRequest, request: Request):
    username = request.cookies.get("session_token")
    if not username:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        if not user:
            return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
            
        company = db.query(Company).filter(Company.id == req.company_id, Company.is_active == True).first()
        if not company:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Perusahaan tidak ditemukan."})
            
        # Optional: check if user is allowed to generate for this company
        if user.company_id and user.company_id != company.id:
            return JSONResponse(status_code=403, content={"status": "error", "message": "Forbidden access to this company."})
            
        # In a real app we'd fetch the report from the DB by name and company
        import os
        import re, datetime
        from app.odoo_api import OdooAPI
        from app.excel_writer import ExcelWriter
        
        # Determine year from the report name (frontend passes template_name)
        year_match = re.search(r'\d{4}', req.template_name)
        year = int(year_match.group()) if year_match else datetime.date.today().year
        date_from = f"{year}-01-01"
        date_to = f"{year}-12-31"
        
        # ID dari frontend
        odoo_report_id = int(req.template)
        
        # Ambil Skeleton dari SQLite (Sinkronisasi Admin)
        from app.models import ReportTemplate
        template_record = db.query(ReportTemplate).filter(
            ReportTemplate.company_id == company.id,
            ReportTemplate.odoo_report_id == odoo_report_id
        ).first()
        
        if not template_record or not template_record.skeleton_json:
            return JSONResponse(status_code=400, content={
                "status": "error", 
                "message": f"Template '{req.template_name}' belum disinkronisasi. Silakan hubungi Admin untuk melakukan sinkronisasi di Konfigurasi Sistem."
            })
            
        print(f"SQLite Skeleton HIT for Report {odoo_report_id} - {year}")
        matrix = json.loads(template_record.skeleton_json)
        
        # Skenario 1 Full: Inject Live Data!
        try:
            report_type = 'fps'
            if 'BMS' in req.template_name.upper():
                report_type = 'non_fps'
            elif 'HO' in req.template_name.upper() or 'HEAD OFFICE' in req.template_name.upper():
                report_type = 'ho'
                
            from app.compiler import FastMatrixCompiler
            compiler = FastMatrixCompiler(db_name=company.target_db_name, year=year, report_type=report_type)
            matrix = compiler.compile(matrix)
        except Exception as e:
            print("FastMatrixCompiler fallback to pure skeleton: ", e)

        
        clean_name = req.template_name.replace(' ', '_').replace('/', '_')
        output_filename = f"{clean_name}_{year}.xlsx"
        
        os.makedirs("app/static/reports", exist_ok=True)
        output_path = f"app/static/reports/{output_filename}"
        
        writer = ExcelWriter(
            output_path=output_path,
            matrix_data=matrix,
            report_name=req.template_name,
            company_name=company.name,
            year=year
        )
        writer.generate()
        
        # Save to ReportHistory
        from app.models import ReportHistory
        now_str = datetime.datetime.now().strftime("%d %b %Y %H:%M")
        history = ReportHistory(
            user_id=user.id if user else None,
            company_id=company.id,
            template_name=req.template_name,
            file_name=output_filename,
            file_path=output_path,
            generated_at=now_str
        )
        db.add(history)
        db.commit()
        
        return {
            "status": "success", 
            "message": "Report generation finished", 
            "file_url": f"/static/reports/{output_filename}",
            "matrix": matrix
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()

@app.get("/api/history")
async def api_get_history(request: Request):
    username = request.cookies.get("session_token")
    if not username:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        from app.models import ReportHistory
        query = db.query(ReportHistory).order_by(ReportHistory.id.desc()).limit(20)
        
        if user and user.company_id:
            query = query.filter(ReportHistory.company_id == user.company_id)
            
        histories = query.all()
        data = []
        for h in histories:
            data.append({
                "id": h.id,
                "template_name": h.template_name,
                "company_name": h.company.name if h.company else "-",
                "file_url": f"/static/reports/{h.file_name}",
                "generated_at": h.generated_at,
                "user": h.user.username if h.user else "System"
            })
        return {"status": "success", "data": data}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()
