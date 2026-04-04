import csv
import sys
from pathlib import Path
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
for p in (PROJECT_ROOT, BACKEND_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from backend.database.database import SessionLocal
from backend.database.models import FeeStructure

BASE_DIR = Path(__file__).resolve().parents[2]
CSV_FILE = BASE_DIR / "data" / "fee_structure.csv"

def seed_fee_structures():
    db: Session = SessionLocal()

    try:
        # Optional: clear old data
        db.query(FeeStructure).delete()
        db.commit()

        with open(CSV_FILE, newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            inserted = 0

            for row in reader:
                fee_type = row.get("fee_type", "").strip()
                year = row.get("year", "").strip()
                amount = row.get("amount", "").strip()

                if not all([fee_type, year, amount]):
                    continue

                fee = FeeStructure(
                    # Model uses `branch`; CSV provides `fee_type`.
                    # Store fee_type in branch to keep existing query logic working.
                    branch=fee_type,
                    year=int(year),
                    amount=int(amount),
                )

                db.add(fee)
                inserted += 1

        db.commit()
        print(f"Seeded {inserted} fee records successfully.")

    except Exception as e:
        db.rollback()
        print("Error while seeding fee structures:", e)
        raise

    finally:
        db.close()


def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
    
    
if __name__ == "__main__":
    seed_fee_structures()