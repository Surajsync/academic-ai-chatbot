"""
Parse placements.csv and populate Placement table.
Run from project root: python backend/database/seed/seed_placements.py
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
from database.models import Placement


def seed_placements():
    """Parse placements CSV and insert into database."""
    data_dir = PROJECT_ROOT / "DATA"
    placements_csv = data_dir / "placements.csv.xls"
    
    db = SessionLocal()
    try:
        inserted = 0
        with open(placements_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                student_name = row.get("student_name", "").strip()
                branch = row.get("branch", "").strip()
                company_name = row.get("company_name", "").strip()
                package_lpa = row.get("package_lpa", "").strip()
                placement_year = row.get("placement_year", "").strip()
                
                if not all([student_name, branch, company_name, placement_year]):
                    continue
                
                db.add(Placement(
                    student_name=student_name,
                    branch=branch,
                    company_name=company_name if company_name else None,
                    package_lpa=package_lpa if package_lpa else None,
                    placement_year=placement_year
                ))
                inserted += 1
        
        db.commit()
        print(f"Inserted {inserted} placement records.")
        return inserted
    except Exception as e:
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_placements()
