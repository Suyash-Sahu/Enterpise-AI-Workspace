from app.db.session import SessionLocal
from app.db.seed import seed_roles

db = SessionLocal()

seed_roles(db)

db.close()

print("Roles seeded successfully.")