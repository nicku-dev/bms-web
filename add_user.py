from app.db import SessionLocal
from app.models import User
db = SessionLocal()
user = db.query(User).filter_by(username='admin_dev').first()
if not user:
    user = User(username='admin_dev', password='admin_dev', role='admin', is_active=True)
    db.add(user)
    db.commit()
print("admin_dev created")
