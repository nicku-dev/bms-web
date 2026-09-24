from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default='user')
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=True)
    is_active = Column(Boolean, default=True)
    
    company = relationship('Company', back_populates='users')

class Company(Base):
    __tablename__ = 'companies'
    id = Column(Integer, primary_key=True, autoincrement=True)
    initial_pt = Column(String(20), nullable=True) # e.g. BMS, FPS
    name = Column(String(100), unique=True, nullable=False) # e.g. PT Bintang Mas Samudra
    target_db_name = Column(String(100), nullable=False) # e.g. BMS_26_PRODUCTION
    server_url = Column(String(100), nullable=True) # e.g. http://localhost:8069
    odoo_user = Column(String(50), nullable=True)
    odoo_password = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    
    reports = relationship('ReportTemplate', back_populates='company', cascade="all, delete-orphan")
    users = relationship('User', back_populates='company')

class ReportTemplate(Base):
    __tablename__ = 'report_templates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    odoo_report_id = Column(Integer, nullable=False)
    report_name = Column(String(100), nullable=False)
    skeleton_json = Column(String, nullable=True) # JSON stored as string
    last_sync = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    
    company = relationship('Company', back_populates='reports')

class ReportHistory(Base):
    __tablename__ = 'report_history'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    template_name = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    generated_at = Column(String(50), nullable=False)

    company = relationship('Company')
    user = relationship('User')
