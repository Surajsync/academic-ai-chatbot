"""
Parse college_cubs.csv and populate Club table.
Run from project root: python backend/database/seed/seed_clubs.py
"""

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
for p in (PROJECT_ROOT, BACKEND_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from database.database import SessionLocal
from database.models import Club


def seed_clubs():
    """Parse clubs CSV and insert into database."""
    data_dir = PROJECT_ROOT / "DATA"
    clubs_csv = data_dir / "college_cubs.csv.xls"
    
    db = SessionLocal()
    try:
        inserted = 0
        with open(clubs_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                club_name = row.get("club_name", "").strip()
                category = row.get("category", "").strip()
                description = row.get("description", "").strip()
                
                if not club_name:
                    continue
                
                existing = db.query(Club).filter(Club.name == club_name).first()
                if existing:
                    print(f"Club '{club_name}' already exists. Skipping.")
                    continue
                
                db.add(Club(
                    name=club_name,
                    category=category,
                    description=description
                ))
                inserted += 1
        
        db.commit()
        print(f"Inserted {inserted} clubs.")
        return inserted
    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_clubs()
