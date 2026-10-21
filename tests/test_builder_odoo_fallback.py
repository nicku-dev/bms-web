from app.db import SessionLocal
from app.models import Company
from app.builder import get_vessels, get_tags, get_accounts

def test_get_vessels_odoo_fallback():
    db = SessionLocal()
    try:
        # Company 3 is ALJ which does not have local/default Postgres DB
        vessels = get_vessels(company_id=3, db=db)
        assert len(vessels) > 0
        vessel_names = [v['name'] for v in vessels]
        assert any("Arung Lautan" in name for name in vessel_names)
    finally:
        db.close()

def test_get_tags_odoo_fallback():
    db = SessionLocal()
    try:
        tags = get_tags(company_id=3, db=db)
        assert len(tags) > 0
        assert any(t.startswith("TW_") for t in tags)
    finally:
        db.close()

def test_get_accounts_odoo_fallback():
    db = SessionLocal()
    try:
        accs = get_accounts(company_id=3, tag_name="TW_PENDAPATAN JASA", db=db)
        assert len(accs) > 0
        assert any("Pendapatan" in a["name"] for a in accs)
    finally:
        db.close()
