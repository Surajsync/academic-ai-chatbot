from sentence_transformers import SentenceTransformer
import json
from backend.database.database import SessionLocal
from backend.database.models import FAQ

print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

db = SessionLocal()

faqs = db.query(FAQ).all()
print(f"Found {len(faqs)} FAQs")

for faq in faqs:
    source_text = " ".join(
        part.strip()
        for part in [faq.question or "", faq.keywords or "", faq.answer or ""]
        if part and part.strip()
    )
    embedding = model.encode(source_text, normalize_embeddings=True)
    faq.embedding = embedding.tolist()
    
db.commit()
db.close()

print("✅ Embeddings stored in DB")