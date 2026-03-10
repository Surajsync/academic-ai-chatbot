import pandas as pd
from database.database import SessionLocal
from database.models import FAQ   

# Read CSV
df = pd.read_csv("chatbot_data1.csv")

# Clean column names (important!)
df.columns = df.columns.str.strip()

db = SessionLocal()

count = 0

for _, row in df.iterrows():
    faq = FAQ(
        keyword=str(row["keyword"]).strip(),
        response=str(row["response"]).strip(),
        is_active=True
    )
    db.add(faq)
    count += 1

db.commit()
db.close()

print(f"Migration completed. {count} rows inserted.")