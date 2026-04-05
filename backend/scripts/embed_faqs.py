from sentence_transformers import SentenceTransformer
import pandas as pd
import os

model = None

def get_model():
    global model
    if model is None:
        print("Loading embedding model...")
        model = SentenceTransformer('all-MiniLM-L6-v2')
    return model

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

csv_path = os.path.join(BASE_DIR, "data", "faq_optimized.csv")

output_path = os.path.join(BASE_DIR, "data", "faq_with_embeddings.json")

df = pd.read_csv(csv_path)

def create_embeddings(text):
    return get_model().encode(text).tolist()

print("Creating embeddings...")
df['embedding'] = df['question'].apply(create_embeddings)
df.to_json(output_path, orient='records', indent=2)

print("Done! Saved file.")