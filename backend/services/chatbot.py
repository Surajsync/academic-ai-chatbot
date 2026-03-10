from database import SessionLocal
from models import FAQ

def generate_reply(user_message: str) -> str:

    if not isinstance(user_message, str):
        return "Invalid message."

    db = SessionLocal()

    faqs = db.query(FAQ).filter(FAQ.is_active == True).all()

    user_message = user_message.lower().strip()

    for faq in faqs:
        keywords = faq.keyword.lower().split(",")

        for keyword in keywords:
            if keyword.strip() in user_message:
                db.close()
                return faq.response

    db.close()
    return "Sorry, I don't have information about that."