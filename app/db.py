from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base, User, Company, ReportTemplate
from .config import settings
import os

DB_PATH = 'app_config.db'
# Gunakan app_config_db_url dari .env (Settings) jika ada di production
DATABASE_URL = settings.app_config_db_url if settings.app_config_db_url else f"sqlite:///{DB_PATH}"

# check_same_thread hanya dibutuhkan untuk SQLite
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Seed Companies and Reports first because User depends on Company
    if not db.query(Company).first():
        # FPS
        fps = Company(name='FPS', target_db_name='MASTER_PROD_2_1')
        db.add(fps)
        db.flush()
        
        db.add(ReportTemplate(company_id=fps.id, report_name='⚓ Laporan Kapal FPS', report_type='fps', template_format='references/TW FPS - KAPAL FPS - {year}.xlsx'))
        db.add(ReportTemplate(company_id=fps.id, report_name='🛳️ Laporan Kapal Non-FPS', report_type='non_fps', template_format='references/TW FPS - KAPAL NON FPS - {year}.xlsx'))
        db.add(ReportTemplate(company_id=fps.id, report_name='🏢 Laporan Head Office', report_type='ho', template_format='references/TW FPS - HEAD OFFICE - {year}.xlsx'))

        # BMS
        bms = Company(name='BMS', target_db_name='BMS_26_PRODUCTION')
        db.add(bms)
        db.flush()
        
        db.add(ReportTemplate(company_id=bms.id, report_name='⚓ Laporan Kapal BMS', report_type='fps', template_format='references/TW BMS - KAPAL BMS - {year}.xlsx'))
        db.add(ReportTemplate(company_id=bms.id, report_name='🛳️ Laporan Kapal Non-BMS', report_type='non_fps', template_format='references/TW BMS - KAPAL NON BMS - {year}.xlsx'))
        db.add(ReportTemplate(company_id=bms.id, report_name='🏢 Laporan Head Office', report_type='ho', template_format='references/TW BMS - HEAD OFFICE - {year}.xlsx'))
        
        # Seed Users after companies
        if not db.query(User).first():
            db.add(User(username='admin_isa', password='password123', role='admin', company_id=None))
            db.add(User(username='user_all', password='password123', role='user', company_id=None))
            db.add(User(username='user_bms', password='password123', role='user', company_id=bms.id))
            db.add(User(username='user_fps', password='password123', role='user', company_id=fps.id))
            
    db.commit()
    db.close()
