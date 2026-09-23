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
    name = Column(String(50), unique=True, nullable=False)
    target_db_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    
    reports = relationship('ReportTemplate', back_populates='company', cascade="all, delete-orphan")
    users = relationship('User', back_populates='company')

class ReportTemplate(Base):
    __tablename__ = 'report_templates'
    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False)
    report_name = Column(String(100), nullable=False)
    report_type = Column(String(20), nullable=False)
    template_format = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    
    company = relationship('Company', back_populates='reports')
