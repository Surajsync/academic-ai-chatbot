from sentence_transformers import SentenceTransformer
from backend.database.database import SessionLocal
from backend.database.models import FAQ

print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

db = SessionLocal()

faqs = db.query(FAQ).all()
print(f"Found {len(faqs)} FAQs")

for faq in faqs:
    embedding = model.encode(faq.question).tolist()
    faq.embedding = embedding

db.commit()
db.close()

print("✅ Embeddings stored in DB")