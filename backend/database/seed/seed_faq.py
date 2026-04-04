import json
from pathlib import Path
from backend.database.database import SessionLocal
from backend.database.models import FAQ

def seed_faq():
    db = SessionLocal()
    BASE_DIR= Path(__file__).resolve().parents[2]
    file_path = BASE_DIR / "data" / "faq_with_embeddings.json"

    with open(file_path, "r") as f:
        faqs = json.load(f)

        for item in faqs:
            db_faq = FAQ(
                question=item.get("question"),
                answer=item.get("answer"),
                keywords=item.get("keywords"),
                embedding=json.dumps(item.get("embedding")),  # Store as JSON string
                is_active=True
            )
            db.add(db_faq)

    db.commit()
    db.close()

    print("FAQ seeding completed!")
if __name__ == "__main__":
    seed_faq()