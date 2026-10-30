from fastapi import FastAPI, Request, Form, File, UploadFile
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
from app.builder import router as builder_router

app = FastAPI(title="ISA Fleet Report - Modern View")
app.include_router(builder_router)

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
    
    db = SessionLocal()
    user = db.query(User).filter(User.username == request.cookies.get("session_token")).first()
    db.close()
    
    if not user:
        return RedirectResponse(url="/logout", status_code=303)
        
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"request": request, "user": user})

@app.get("/dashboard", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    if "session_token" not in request.cookies:
        return RedirectResponse(url="/login", status_code=303)
        
    db = SessionLocal()
    user = db.query(User).filter(User.username == request.cookies.get("session_token")).first()
    db.close()
    
    if not user:
        return RedirectResponse(url="/logout", status_code=303)
        
    return templates.TemplateResponse(request=request, name="dashboard.html", context={"request": request, "user": user})

@app.get("/login", response_class=HTMLResponse)
async def read_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

@app.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response

@app.get("/builder", response_class=HTMLResponse)
async def read_builder(request: Request):
    if "session_token" not in request.cookies:
        return RedirectResponse(url="/login", status_code=303)
    db = SessionLocal()
    user = db.query(User).filter(User.username == request.cookies.get("session_token")).first()
    db.close()
    if not user:
        return RedirectResponse(url="/logout", status_code=303)
    return templates.TemplateResponse(request=request, name="builder.html", context={"request": request, "user": user})

@app.post("/api/login")
async def api_login(req: LoginRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username, User.is_active == True).first()
        if not user:
            return JSONResponse(status_code=401, content={"status": "error", "message": "Username tidak ditemukan atau tidak aktif."})

        authenticated = False
        
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
            companies_data = [{"id": user.company.id, "name": user.company.name, "initial_pt": user.company.initial_pt}]
        else:
            companies = db.query(Company).filter(Company.is_active == True).all()
            companies_data = [{"id": c.id, "name": c.name, "initial_pt": c.initial_pt} for c in companies]
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

        from app.models import CustomBuilderTemplate
        builder_templates = db.query(CustomBuilderTemplate).filter(
            CustomBuilderTemplate.company_id == company.id
        ).order_by(CustomBuilderTemplate.id).all()
        reports = [{"id": r.id, "name": r.name} for r in builder_templates]
        
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
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    ssh_host: Optional[str] = None

class TestConnectionRequest(BaseModel):
    server_url: str
    target_db_name: str
    odoo_user: str
    odoo_password: str
    company_id: Optional[int] = None

@app.get("/config", response_class=HTMLResponse)
async def read_config(request: Request):
    if "session_token" not in request.cookies:
        return RedirectResponse(url="/login", status_code=303)
        
    db = SessionLocal()
    user = db.query(User).filter(User.username == request.cookies.get("session_token")).first()
    db.close()
    
    if not user:
        return RedirectResponse(url="/logout", status_code=303)
        
    perms = user.permissions.split(',') if user.permissions else []
    is_admin = (user.role == 'admin' or user.permissions == '*' or user.username in ["admin_isa", "admin_dev"])
    if not is_admin and 'config' not in perms:
        return RedirectResponse(url="/dashboard", status_code=303)
        
    return templates.TemplateResponse(request=request, name="config.html", context={"request": request, "user": user})

@app.get("/reference", response_class=HTMLResponse)
async def read_reference(request: Request):
    if "session_token" not in request.cookies:
        return RedirectResponse(url="/login", status_code=303)
        
    db = SessionLocal()
    user = db.query(User).filter(User.username == request.cookies.get("session_token")).first()
    db.close()
    
    if not user:
        return RedirectResponse(url="/logout", status_code=303)
        
    perms = user.permissions.split(',') if user.permissions else []
    is_admin = (user.role == 'admin' or user.permissions == '*' or user.username in ["admin_isa", "admin_dev"])
    if not is_admin and 'reference' not in perms:
        return RedirectResponse(url="/dashboard", status_code=303)
        
    return templates.TemplateResponse(request=request, name="reference.html", context={"request": request, "user": user})


@app.get("/api/admin/references")
async def api_admin_references(request: Request):
    if "session_token" not in request.cookies:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
        
    db = SessionLocal()
    user = db.query(User).filter(User.username == request.cookies.get("session_token")).first()
    
    if not user or (user.role != 'admin' and user.username not in ["admin_isa", "admin_dev"]):
        db.close()
        return JSONResponse(status_code=403, content={"status": "error", "message": "Forbidden"})
        
    company_filter = request.query_params.get("company", "all")
    year_filter = request.query_params.get("year", "all")
    
    if company_filter != "all":
        companies = db.query(Company).filter(Company.is_active == True, Company.initial_pt == company_filter).all()
    else:
        companies = db.query(Company).filter(Company.is_active == True).all()
    db.close()
    
    import duckdb
    from app.config import settings
    
    results = []
    
    for comp in companies:
        if not comp.target_db_name:
            continue
            
        con = duckdb.connect()
        try:
            con.execute("INSTALL postgres; LOAD postgres;")
            pg_url = settings.get_postgres_connection_string(comp.target_db_name)
            con.execute(f"ATTACH '{pg_url}' AS pg (TYPE postgres, READ_ONLY);")
            
            # Fetch all views that start with 'tw' from mis_report_query
            query = """
            SELECT DISTINCT q.name AS var_name, m.model AS odoo_model, REPLACE(m.model, '.', '_') AS sql_view
            FROM pg.mis_report_query q
            JOIN pg.ir_model m ON q.model_id = m.id
            WHERE m.model LIKE 'tw%'
            """
            views = con.execute(query).fetchall()
            
            for var_name, odoo_model, sql_view in views:
                view_year = "2026" if "26" in sql_view else ("2025" if "25" in sql_view else "Auto")
                if year_filter != "all" and year_filter != view_year:
                    continue
                
                row_data = {
                    "inisial": comp.initial_pt or "N/A",
                    "nama_pt": comp.name,
                    "keterangan": f"KPI: {var_name}",
                    "nama_tabel": sql_view,
                    "tahun": view_year,
                    "q1": 0.0,
                    "q2": 0.0,
                    "q3": 0.0,
                    "q4": 0.0,
                    "ytd": 0.0
                }
                try:
                    cols = con.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{sql_view}'").fetchall()
                    col_names = [c[0] for c in cols]
                    
                    q1_col = next((c for c in col_names if 'q1' in c), None)
                    q2_col = next((c for c in col_names if 'q2' in c), None)
                    q3_col = next((c for c in col_names if 'q3' in c), None)
                    q4_col = next((c for c in col_names if 'q4' in c), None)
                    ytd_col = next((c for c in col_names if 'ytd' in c), None)
                    
                    selects = []
                    selects.append(f"SUM({q1_col}) as q1" if q1_col else "0 as q1")
                    selects.append(f"SUM({q2_col}) as q2" if q2_col else "0 as q2")
                    selects.append(f"SUM({q3_col}) as q3" if q3_col else "0 as q3")
                    selects.append(f"SUM({q4_col}) as q4" if q4_col else "0 as q4")
                    selects.append(f"SUM({ytd_col}) as ytd" if ytd_col else "0 as ytd")
                    
                    custom_tags = {
                        'tpbb': 'TW_Pendapatan bunga bank',
                        'tpll': 'TW_Pendapatan lain-lain',
                        'tlsk': 'TW_Laba selisih Kurs',
                        'tbll': 'TW_Biaya Lain-lain',
                        'tbab': 'TW_Biaya Admin Bank',
                        'trsk': 'TW_Rugi selisih Kurs',
                        'tbpll': 'TW_Beban Pajak Lain-lain'
                    }
                    if var_name in custom_tags:
                        tag_name = custom_tags[var_name]
                        data_query = f"""
                            WITH custom_view AS (
                                SELECT 
                                    1 as id,
                                    '2026-12-31'::date as date,
                                    '{tag_name}' as keterangan,
                                    COALESCE(SUM(CASE WHEN EXTRACT(QUARTER FROM aml.date) = 1 THEN aml.balance ELSE 0 END), 0) as {q1_col or 'sumq1_25'},
                                    COALESCE(SUM(CASE WHEN EXTRACT(QUARTER FROM aml.date) = 2 THEN aml.balance ELSE 0 END), 0) as {q2_col or 'sumq2_25'},
                                    COALESCE(SUM(CASE WHEN EXTRACT(QUARTER FROM aml.date) = 3 THEN aml.balance ELSE 0 END), 0) as {q3_col or 'sumq3_25'},
                                    COALESCE(SUM(CASE WHEN EXTRACT(QUARTER FROM aml.date) = 4 THEN aml.balance ELSE 0 END), 0) as {q4_col or 'sumq4_25'},
                                    COALESCE(SUM(aml.balance), 0) as {ytd_col or 'ytd_25'}
                                FROM pg.account_move_line aml
                                JOIN pg.account_account_account_tag aaat ON aaat.account_account_id = aml.account_id 
                                JOIN pg.account_account_tag aat ON aat.id = aaat.account_account_tag_id 
                                WHERE aat.name->>'en_US' = '{tag_name}' 
                                  AND aml.parent_state = 'posted'
                            )
                            SELECT {', '.join(selects)} FROM custom_view
                        """
                    else:
                        data_query = f"SELECT {', '.join(selects)} FROM pg.{sql_view}"
                    data = con.execute(data_query).fetchone()
                    
                    row_data["q1"] = float(data[0] or 0)
                    row_data["q2"] = float(data[1] or 0)
                    row_data["q3"] = float(data[2] or 0)
                    row_data["q4"] = float(data[3] or 0)
                    row_data["ytd"] = float(data[4] or 0)
                except Exception as ex:
                    print(f"Skipping {sql_view} on {comp.name}: {ex}")
                
                results.append(row_data)

        except Exception as e:
            print(f"Error fetching from {comp.target_db_name}: {e}")
        finally:
            con.close()
            
    return JSONResponse(content={"status": "success", "data": results})

@app.get("/api/admin/companies")

async def api_admin_companies(include_inactive: bool = False):
    db = SessionLocal()
    query = db.query(Company)
    if not include_inactive:
        query = query.filter(Company.is_active == True)
    companies = query.order_by(Company.id).all()
    data = []
    for c in companies:
        data.append({
            "id": c.id, 
            "initial_pt": c.initial_pt,
            "name": c.name, 
            "is_active": bool(c.is_active),
            "server_url": c.server_url,
            "target_db_name": c.target_db_name,
            "odoo_user": c.odoo_user,
            "odoo_password": "🔑 Tersimpan rahasia" if c.odoo_password else "",
            "db_host": c.db_host or "",
            "db_port": c.db_port or 5432,
            "db_user": c.db_user or "",
            "db_password": "🔑 Tersimpan rahasia" if c.db_password else "",
            "ssh_host": c.ssh_host or ""
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
        odoo_password=req.odoo_password,
        db_host=req.db_host,
        db_port=req.db_port or 5432,
        db_user=req.db_user,
        db_password=req.db_password,
        ssh_host=req.ssh_host
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
    db_host: Optional[str] = None
    db_port: Optional[int] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    ssh_host: Optional[str] = None

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
    if req.db_host is not None:
        c.db_host = req.db_host
    if req.db_port is not None:
        c.db_port = req.db_port
    if req.db_user is not None:
        c.db_user = req.db_user
    if req.db_password:
        c.db_password = req.db_password
    if req.ssh_host is not None:
        c.ssh_host = req.ssh_host
        
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

class CompanyActiveRequest(BaseModel):
    is_active: bool

@app.patch("/api/admin/companies/{company_id}/active")
async def api_admin_toggle_company_active(company_id: int, req: CompanyActiveRequest):
    db = SessionLocal()
    try:
        c = db.query(Company).filter(Company.id == company_id).first()
        if not c:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Perusahaan tidak ditemukan"})
        c.is_active = req.is_active
        db.commit()
        state = "diaktifkan" if req.is_active else "dinonaktifkan"
        return {"status": "success", "message": f"Perusahaan {state}"}
    finally:
        db.close()

@app.post("/api/admin/test_connection")
async def api_admin_test_connection(req: TestConnectionRequest):
    from app.odoo_api import OdooAPI
    from app.models import Company
    db = SessionLocal()
    try:
        # If password is empty (e.g. from UI placeholder), fetch existing from DB
        password = req.odoo_password
        if (not password or password == "********") and req.company_id:
            c = db.query(Company).filter(Company.id == req.company_id).first()
            if c:
                password = c.odoo_password
                
        if not password:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Password diperlukan untuk menguji koneksi."})
            
        api = OdooAPI(
            db_name=req.target_db_name, 
            url=req.server_url, 
            username=req.odoo_user, 
            password=password
        )
        api.authenticate()
        return {"status": "success", "message": "Koneksi ke Odoo berhasil!"}
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})
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
        
        # Parse template ID from frontend (menunjuk ke CustomBuilderTemplate.id)
        try:
            template_id = int(req.template)
        except (ValueError, TypeError):
            template_id = None

        from app.models import CustomBuilderTemplate
        template_record = None
        if template_id:
            template_record = db.query(CustomBuilderTemplate).filter(
                CustomBuilderTemplate.company_id == company.id,
                CustomBuilderTemplate.id == template_id
            ).first()

        if not template_record and req.template_name:
            template_record = db.query(CustomBuilderTemplate).filter(
                CustomBuilderTemplate.company_id == company.id,
                CustomBuilderTemplate.name == req.template_name
            ).first()

        if not template_record:
            return JSONResponse(status_code=400, content={
                "status": "error", 
                "message": f"Template '{req.template_name}' tidak ditemukan di Report Builder. Silakan buat template terlebih dahulu di menu Report Builder."
            })
            
        cfg = json.loads(template_record.config_json)
        vessels = cfg.get("vessels", [])
        rows = cfg.get("rows", [])
        
        # Determine year: from config, or from template_name, fallback to current year
        year = cfg.get("year")
        if not year:
            year_match = re.search(r'\d{4}', req.template_name or template_record.name)
            year = int(year_match.group()) if year_match else datetime.date.today().year
        else:
            year = int(year)

        from app.builder import build_and_compile_matrix
        matrix = build_and_compile_matrix(company, str(year), vessels, rows, db)
        compile_status = "OK (Live Matrix Compiler)"
        
        report_display_name = template_record.name
        clean_name = report_display_name.replace(' ', '_').replace('/', '_')
        
        if str(year) in clean_name:
            clean_name = clean_name.replace(f"_{year}", "")
            clean_name = clean_name.replace(str(year), "")
            
        clean_name = clean_name.strip('_')
        timestamp_seq = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{clean_name}_{year}_{timestamp_seq}.xlsx"
        
        os.makedirs("app/static/reports", exist_ok=True)
        output_path = f"app/static/reports/{output_filename}"
        
        writer = ExcelWriter(
            output_path=output_path,
            matrix_data=matrix,
            report_name=report_display_name,
            company_name=company.name,
            year=year,
            db_name=company.target_db_name,
            compile_status=compile_status
        )
        writer.generate()
        
        # Save to ReportHistory
        from app.models import ReportHistory
        now_str = datetime.datetime.now().strftime("%d %b %Y %H:%M")
        history = ReportHistory(
            user_id=user.id if user else None,
            company_id=company.id,
            template_name=report_display_name,
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



@app.get("/api/audit_trail")
async def api_get_audit_trail(
    company_id: int, 
    year: int, 
    quarter: str, 
    vessel_name: str, 
    tag_name: Optional[str] = None, 
    account_code: Optional[str] = None,
    request: Request = None
):
    if request and "session_token" not in request.cookies:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})

    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id, Company.is_active == True).first()
        if not company:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Perusahaan tidak ditemukan."})

        from app.engine import ReportEngine
        engine = ReportEngine(db_name=company.target_db_name, pg_kwargs=company.get_pg_kwargs())
        
        # Quarter can be 'q1', 'q2', 'q3', 'q4', or 'ytd'
        data = engine.get_audit_trail(
            year=year,
            quarter=quarter,
            vessel_name=vessel_name,
            tag_name=tag_name,
            account_code=account_code
        )
        engine.close()
        
        return {"status": "success", "data": data}
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

@app.delete("/api/history")
async def api_clear_history(request: Request):
    username = request.cookies.get("session_token")
    if not username:
        return JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username, User.is_active == True).first()
        if not user or (user.role != 'admin' and user.username not in ["admin_isa", "admin_dev"]):
            return JSONResponse(status_code=403, content={"status": "error", "message": "Hanya admin yang dapat menghapus riwayat."})

        from app.models import ReportHistory
        import os
        histories = db.query(ReportHistory).all()
        
        for h in histories:
            try:
                if h.file_path and os.path.exists(h.file_path):
                    os.remove(h.file_path)
            except:
                pass
            db.delete(h)
            
        db.commit()
        return {"status": "success", "message": "Semua riwayat berhasil dihapus"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()

class UserCreateRequest(BaseModel):
    username: str
    password: str
    role: str = 'user'
    company_id: Optional[int] = None
    is_active: bool = True
    permissions: str = '*'

class UserUpdateRequest(BaseModel):
    username: str
    password: Optional[str] = None
    role: str = 'user'
    company_id: Optional[int] = None
    is_active: bool = True
    permissions: str = '*'

@app.get("/api/admin/users")
async def api_admin_users():
    db = SessionLocal()
    users = db.query(User).all()
    data = []
    for u in users:
        data.append({
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "company_id": u.company_id,
            "company_name": u.company.name if u.company else "Semua",
            "is_active": u.is_active,
            "permissions": u.permissions
        })
    db.close()
    return {"status": "success", "data": data}

@app.post("/api/admin/users")
async def api_admin_create_user(req: UserCreateRequest):
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == req.username).first():
            return JSONResponse(status_code=400, content={"status": "error", "message": "Username sudah ada"})
            
        u = User(
            username=req.username,
            password=req.password,
            role=req.role,
            company_id=req.company_id,
            is_active=req.is_active,
            permissions=req.permissions
        )
        db.add(u)
        db.commit()
        return {"status": "success", "message": "User berhasil dibuat"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()

@app.put("/api/admin/users/{user_id}")
async def api_admin_update_user(user_id: int, req: UserUpdateRequest):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            return JSONResponse(status_code=404, content={"status": "error", "message": "User tidak ditemukan"})
            
        if req.username != u.username and db.query(User).filter(User.username == req.username).first():
            return JSONResponse(status_code=400, content={"status": "error", "message": "Username sudah ada"})
            
        u.username = req.username
        if req.password:
            u.password = req.password
        u.role = req.role
        u.company_id = req.company_id
        u.is_active = req.is_active
        u.permissions = req.permissions
        db.commit()
        return {"status": "success", "message": "User berhasil diupdate"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()

@app.delete("/api/admin/users/{user_id}")
async def api_admin_delete_user(user_id: int):
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        if not u:
            return JSONResponse(status_code=404, content={"status": "error", "message": "User tidak ditemukan"})
        db.delete(u)
        db.commit()
        return {"status": "success", "message": "User berhasil dihapus"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        db.close()

@app.get("/api/reference_queries")
async def api_reference_queries(request: Request):
    db = SessionLocal()
    companies = db.query(Company).filter(Company.is_active == True).all()
    db.close()
    
    if not companies:
        return JSONResponse(status_code=400, content={"status": "error", "message": "No active companies found"})
        
    try:
        from app.engine import ReportEngine
        
        results = []
        target_queries = ['tbab', 'tbak', 'tbg', 'tbj', 'tbk', 'tbll', 'tbp', 'tbpga', 'tbpll', 'tlsk', 'tpbb', 'tpll', 'trsk']
        
        for comp in companies:
            if not comp.target_db_name:
                continue
                
            try:
                engine = ReportEngine(comp.target_db_name, pg_kwargs=comp.get_pg_kwargs())
                
                try:
                    # Look for BMS or FPS report
                    report_name_match = "%BMS%2026%" if "BMS" in comp.name else "%FPS%2026%"
                    duckdb_query = f"SELECT id FROM postgres_query('pg', 'SELECT id FROM mis_report WHERE name ILIKE ''{report_name_match}'' LIMIT 1')"
                    report_id = engine.conn.execute(duckdb_query).fetchone()[0]
                except Exception:
                    report_id = 18 # fallback
                    
                queries_data = engine.get_mis_report_queries(report_id)
                
                kpi_query = f"SELECT name, description FROM postgres_query('pg', 'SELECT name, description FROM mis_report_kpi WHERE report_id = {report_id}')"
                try:
                    kpi_rows = engine.conn.execute(kpi_query).fetchall()
                    kpi_map = {r[0]: r[1] for r in kpi_rows}
                except Exception:
                    kpi_map = {}
                    
                for q_code in target_queries:
                    keterangan = kpi_map.get(q_code, "Unknown")
                    vals = queries_data.get(q_code, {})
                    
                    q1 = 0; q2 = 0; q3 = 0; q4 = 0; ytd = 0
                    for k, v in vals.items():
                        k_lower = k.lower()
                        val_float = float(v) if v else 0.0
                        if 'q1' in k_lower: q1 += val_float
                        elif 'q2' in k_lower: q2 += val_float
                        elif 'q3' in k_lower: q3 += val_float
                        elif 'q4' in k_lower: q4 += val_float
                        elif 'ytd' in k_lower: ytd += val_float
                        
                    results.append({
                        "perusahaan": comp.name,
                        "date_tahun": "2026",
                        "keterangan": keterangan,
                        "model_name": f"tw.{q_code}",
                        "code": q_code,
                        "q1": q1,
                        "q2": q2,
                        "q3": q3,
                        "q4": q4,
                        "ytd": ytd
                    })
            except Exception as e:
                print(f"Failed to fetch for {comp.name}: {e}")
                
        return {"status": "success", "data": results}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/checker", response_class=HTMLResponse)
async def checker_ui(request: Request):
    if "session_token" not in request.cookies:
        return RedirectResponse(url="/login", status_code=303)
        
    db = SessionLocal()
    user = db.query(User).filter(User.username == request.cookies.get("session_token")).first()
    companies = db.query(Company).filter(Company.is_active == True).all()
    comp_list = [{"id": c.id, "name": c.name, "target_db_name": c.target_db_name} for c in companies]
    db.close()
    
    if not user:
        return RedirectResponse(url="/logout", status_code=303)
        
    perms = user.permissions.split(',') if user.permissions else []
    is_admin = (user.role == 'admin' or user.permissions == '*' or user.username in ["admin_isa", "admin_dev"])
    if not is_admin and 'checker' not in perms:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse(request=request, name="checker.html", context={"request": request, "user": user, "companies": comp_list})

@app.get("/reconcile")
async def reconcile_page_redirect():
    return RedirectResponse(url="/checker?tab=reconcile", status_code=303)

class CheckerQuery(BaseModel):
    db_name: str
    date_from: str
    date_to: str
    tag_name: str = None

@app.post("/api/checker/query")
async def execute_checker_query(payload: CheckerQuery):
    from app.engine import ReportEngine
    import math
    try:
        db = SessionLocal()
        comp = db.query(Company).filter(Company.target_db_name == payload.db_name).first()
        pg_kwargs = comp.get_pg_kwargs() if comp else None
        db.close()
        engine = ReportEngine(payload.db_name, pg_kwargs=pg_kwargs)
        
        # Base query
        query = """
            SELECT 
                m.date,
                m.name as move_name,
                l.name as label,
                a.code_store as account_code,
                a.name->>'en_US' as account_name,
                t.name->>'en_US' as tag_name,
                l.debit,
                l.credit,
                (l.debit - l.credit) as balance
            FROM pg.account_move_line l
            JOIN pg.account_move m ON l.move_id = m.id
            JOIN pg.account_account a ON l.account_id = a.id
            JOIN pg.account_account_account_tag rel ON a.id = rel.account_account_id
            JOIN pg.account_account_tag t ON rel.account_account_tag_id = t.id
            WHERE m.state = 'posted'
        """
        
        # Add date filters
        query += f" AND m.date >= '{payload.date_from}' AND m.date <= '{payload.date_to}'"
        
        # Add tag filter if provided
        if payload.tag_name:
            # We must escape single quotes in tag names just in case
            safe_tag = payload.tag_name.replace("'", "''")
            query += f" AND t.name::VARCHAR LIKE '%\"en_US\": \"{safe_tag}\"%' "
        
        query += " ORDER BY m.date, m.name"
        
        df = engine.conn.execute(query).df()
        engine.close()
        
        # Convert nan/NaT to None for JSON serialization
        df = df.where(df.notnull(), None)
        
        # Convert date to string
        if not df.empty:
            df['date'] = df['date'].astype(str)
            
        data = df.to_dict('records')
        return {"status": "success", "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/checker/reconcile")
async def reconcile_mis_builder(
    request: Request,
    company_id: int = Form(...),
    template_id: int = Form(...),
    year: int = Form(...),
    tolerance: float = Form(1.0),
    file: UploadFile = File(...)
):
    import os
    import datetime
    from app.models import CustomBuilderTemplate
    from app.builder import build_and_compile_matrix
    from app.diff_checker import parse_mis_builder_excel, compare_matrices, export_diff_matrix_excel
    
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Perusahaan tidak ditemukan."})
            
        template_record = db.query(CustomBuilderTemplate).filter(
            CustomBuilderTemplate.id == template_id,
            CustomBuilderTemplate.company_id == company.id
        ).first()
        if not template_record:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Template tidak ditemukan."})
            
        file_bytes = await file.read()
        if not file_bytes:
            return JSONResponse(status_code=400, content={"status": "error", "message": "File Excel kosong."})
            
        try:
            mis_data = parse_mis_builder_excel(file_bytes)
        except Exception as e:
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Gagal membaca format Excel MIS Builder: {str(e)}"})
            
        cfg = json.loads(template_record.config_json)
        vessels = cfg.get("vessels", [])
        rows = cfg.get("rows", [])
        
        # Live matrix compilation via DuckDB
        bms_matrix = build_and_compile_matrix(company, str(year), vessels, rows, db)
        
        # Compare matrices cell by cell
        diff_result = compare_matrices(bms_matrix, mis_data, tolerance=tolerance)
        
        # Generate & save Diff Excel
        clean_name = template_record.name.replace(' ', '_').replace('/', '_')
        timestamp_seq = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"reconcile_diff_{clean_name}_{year}_{timestamp_seq}.xlsx"
        
        os.makedirs("app/static/reports", exist_ok=True)
        output_path = f"app/static/reports/{output_filename}"
        
        excel_bytes = export_diff_matrix_excel(diff_result, company.name, template_record.name, year)
        with open(output_path, "wb") as f_out:
            f_out.write(excel_bytes)
            
        return {
            "status": "success",
            "kpi": diff_result["kpi"],
            "headers": diff_result["headers"],
            "rows": diff_result["rows"],
            "discrepancies": diff_result["discrepancies"],
            "excel_url": f"/static/reports/{output_filename}",
            "mis_meta": {
                "company_name": mis_data.get("company_name"),
                "report_title": mis_data.get("report_title"),
                "year": mis_data.get("year")
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Proses rekonsiliasi gagal: {str(e)}"})
    finally:
        db.close()

