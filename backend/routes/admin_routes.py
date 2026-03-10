from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from utils.helpers import get_db
from models import FAQ, Conversation, FailedQuery

router = APIRouter()


@router.get("/admin/dashboard")
def dashboard(db: Session = Depends(get_db)):

    total_faqs = db.query(FAQ).count()
    active_faqs = db.query(FAQ).filter(FAQ.is_active == True).count()
    total_conversations = db.query(Conversation).count()
    failed_queries = db.query(FailedQuery).count()

    return {
        "total_faqs": total_faqs,
        "active_faqs": active_faqs,
        "total_conversations": total_conversations,
        "failed_queries": failed_queries
    }


@router.get("/admin/faqs")
def get_faqs(db: Session = Depends(get_db)):
    return db.query(FAQ).all()