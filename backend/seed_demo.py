# backend/seed_minimal.py
from backend.db import SessionLocal, Base, engine
from backend.models import Building, Case, Inspector

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Inspectors
ins1 = Inspector(name="Inspector C", home_lat=33.5, home_lng=35.9, active=True)
ins2 = Inspector(name="Inspector D", home_lat=33.96,   home_lng=35.1,   active=True)
db.add_all([ins1, ins2])

# Buildings + Cases
b1 = Building(building_name="Hamra 12", latitude=33.895, longitude=35.480, district="Beirut")
b2 = Building(building_name="Corniche 8", latitude=33.906, longitude=35.505, district="Beirut")
db.add_all([b1, b2]); db.flush()

c1 = Case(building_id=b1.id, status="open")
c2 = Case(building_id=b2.id, status="open")
db.add_all([c1, c2])

db.commit()
print("Seeded: 2 inspectors, 2 buildings, 2 cases.")

