from sqlalchemy.orm import Session
from database.models import FAQ


def generate_reply(db: Session, message: str):

    message = message.lower().strip()

    faqs = db.query(FAQ).filter(FAQ.is_active == True).all()

    for faq in faqs:

        keywords = faq.keyword.lower().split(",")

        for k in keywords:
            if k.strip() in message:
                return faq.response

    return "Sorry, I don't know the answer yet."