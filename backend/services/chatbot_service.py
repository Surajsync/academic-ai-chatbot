import re
import json
import threading
import numpy as np
from sentence_transformers import SentenceTransformer
from backend.database.database import SessionLocal
from sqlalchemy.orm import Session

from backend.database.models import FAQ, Department, FeeStructure, Club, Placement, ScholarshipCell
from backend.services.ai_service import generate_answer
from backend.config import settings


_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
_embedding_model = None
_embedding_model_lock = threading.Lock()


def _get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        with _embedding_model_lock:
            if _embedding_model is None:
                try:
                    _embedding_model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
                except RuntimeError as exc:
                    # Retry once for transient hub/http client lifecycle glitches.
                    if "client has been closed" not in str(exc).lower():
                        raise
                    _embedding_model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
    return _embedding_model

OUT_OF_SCOPE_REPLY = "I don't have information about that in the college database. Please contact the Admin Office or the relevant department for assistance. You can also visit the college website or reach out to Student Services."

ALIAS_MAP = {
    "it": "information technology",
    "cse": "computer science engineering",
    "cs": "computer science",
    "ece": "electronics communication",
    "ee": "electrical engineering",
    "me": "mechanical engineering",
    "ce": "civil engineering",
    "hod": "head of department",
}

STOPWORDS = {
    "a", "an", "the", "is", "are", "of", "for", "to", "and", "in", "on", "at",
    "with", "by", "from", "me", "you", "your", "please", "tell", "about", "what",
    "which", "who", "where", "when", "why", "how", "do", "does", "did", "can", "could",
    "should", "would", "branch", "department", "details", "info", "information", "college",
}

FEE_QUERY_HINTS = {"fee", "fees", "tuition", "hostel"}
HOD_QUERY_HINTS = {"hod", "head", "faculty"}
CLUB_QUERY_HINTS = {"club", "clubs", "society", "activities", "extracurricular"}
PLACEMENT_QUERY_HINTS = {"placement", "placements", "job", "company", "companies", "recruit", "internship"}
SCHOLARSHIP_QUERY_HINTS = {"scholarship", "scholarships", "grant", "financial", "assistance"}

FEE_RECORD_HINTS = {"fee", "fees", "tuition", "fee structure", "hostel fee"}
HOD_RECORD_HINTS = {"hod", "head of department", "head"}
CLUB_RECORD_HINTS = {"club", "clubs", "society", "activity"}
PLACEMENT_RECORD_HINTS = {"placement", "placements", "company", "companies", "job", "recruit"}
SCHOLARSHIP_RECORD_HINTS = {"scholarship", "scholarships", "grant", "financial", "assistance"}


def _faq_keyword_text(faq: FAQ) -> str:
    return (getattr(faq, "keyword", None) or getattr(faq, "keywords", None) or getattr(faq, "question", None) or "")


def _faq_response_text(faq: FAQ) -> str:
    return (getattr(faq, "response", None) or getattr(faq, "answer", None) or "")


def _clean_reply_text(reply: str) -> str:
    """Remove noisy metadata-like lines before sending reply to UI."""
    if not reply:
        return OUT_OF_SCOPE_REPLY

    cleaned_lines = []
    for line in reply.splitlines():
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue

        lowered = stripped.lower()
        if lowered.startswith("source:"):
            continue

        # Drop common leaked metadata patterns from seeded/legacy content.
        if any(token in lowered for token in [".csv", ".xlsx", "amount:", "year:", "sheet:"]):
            continue

        cleaned_lines.append(stripped)

    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned or OUT_OF_SCOPE_REPLY


def _detect_intent(query_tokens: set[str]) -> str:
    if query_tokens.intersection(FEE_QUERY_HINTS):
        return "fee"
    if query_tokens.intersection(HOD_QUERY_HINTS):
        return "hod"
    if query_tokens.intersection(CLUB_QUERY_HINTS):
        return "club"
    if query_tokens.intersection(PLACEMENT_QUERY_HINTS):
        return "placement"
    if query_tokens.intersection(SCHOLARSHIP_QUERY_HINTS):
        return "scholarship"
    return "general"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def _tokenize(text: str) -> set[str]:
    normalized = _normalize(text)
    tokens = {t for t in normalized.split() if len(t) > 1}
    return {t for t in tokens if t not in STOPWORDS}


def _expand_aliases(text: str) -> str:
    tokens = _normalize(text).split()
    expanded = []
    for token in tokens:
        expanded.append(token)
        alias_value = ALIAS_MAP.get(token)
        if alias_value:
            expanded.extend(alias_value.split())
    return " ".join(expanded)


def _score_overlap(query_tokens: set[str], candidate_text: str) -> int:
    candidate_tokens = _tokenize(candidate_text)
    if not candidate_tokens:
        return 0
    return len(query_tokens.intersection(candidate_tokens))


def _collect_relevant_faqs(
    db: Session,
    expanded_query: str,
    query_tokens: set[str],
    intent: str,
    limit: int = 6,
) -> list[FAQ]:
    ranked = []
    faqs = db.query(FAQ).filter(FAQ.is_active == True).all()

    for faq in faqs:
        keyword_text = _faq_keyword_text(faq)
        response_text = _faq_response_text(faq)
        searchable_text = f"{keyword_text} {response_text}".lower()

        # Intent-aware filtering to avoid noise in focused queries.
        if intent == "fee" and not any(hint in searchable_text for hint in FEE_RECORD_HINTS):
            continue
        if intent == "hod" and not any(hint in searchable_text for hint in HOD_RECORD_HINTS):
            continue
        if intent == "club" and not any(hint in searchable_text for hint in CLUB_RECORD_HINTS):
            continue
        if intent == "placement" and not any(hint in searchable_text for hint in PLACEMENT_RECORD_HINTS):
            continue
        if intent == "scholarship" and not any(hint in searchable_text for hint in SCHOLARSHIP_RECORD_HINTS):
            continue

        best_score = 0
        for phrase in keyword_text.lower().split(","):
            phrase = phrase.strip()
            if not phrase:
                continue

            score = _score_overlap(query_tokens, phrase)
            if phrase and phrase in expanded_query:
                score += 3

            if intent == "fee" and "fee" in phrase:
                score += 1
            if intent == "hod" and ("hod" in phrase or "head" in phrase):
                score += 1
            if intent == "club" and ("club" in phrase or "society" in phrase):
                score += 1
            if intent == "placement" and ("placement" in phrase or "company" in phrase):
                score += 1
            if intent == "scholarship" and ("scholarship" in phrase or "grant" in phrase):
                score += 1

            best_score = max(best_score, score)

        # Skip weak matches to reduce noisy context.
        min_score = 1 if intent in {"fee", "hod", "club", "placement", "scholarship"} else 2
        if best_score >= min_score:
            ranked.append((best_score, faq))

    ranked.sort(key=lambda row: row[0], reverse=True)
    return [faq for _score, faq in ranked[:limit]]


def _best_department_match(db: Session, query_tokens: set[str]) -> Department | None:
    best_match = None
    best_score = 0

    for dept in db.query(Department).all():
        score = _score_overlap(query_tokens, dept.name)
        if score > best_score:
            best_score = score
            best_match = dept

    if best_score >= 1:
        return best_match
    return None


def _best_fee_match(db: Session, query_tokens: set[str]) -> FeeStructure | None:
    best_match = None
    best_score = 0

    for fee in db.query(FeeStructure).all():
        score = _score_overlap(query_tokens, fee.branch)
        if score > best_score:
            best_score = score
            best_match = fee

    if best_score >= 1:
        return best_match
    return None


def _direct_structured_answer(db: Session, query_tokens: set[str]) -> tuple[str, str] | None:
    if query_tokens.intersection(HOD_QUERY_HINTS):
        department = _best_department_match(db, query_tokens)
        if department:
            return f"HOD of {department.name} is {department.hod}.", "structured"

    if query_tokens.intersection(FEE_QUERY_HINTS):
        fee = _best_fee_match(db, query_tokens)
        if fee:
            return f"Fee Structure for {fee.branch}: {fee.amount}", "structured"

    return None


def build_context(db: Session, message: str) -> str:
    lines = []
    
    # College Header Info
    lines.append("=== REC BIJNOR - OFFICIAL COLLEGE INFORMATION ===")
    lines.append("College: Rajkiya Engineering College, Bijnor")
    lines.append("Type: Government Engineering Institute")
    lines.append("Recognition: Approved by AICTE, affiliated with AKTU, Lucknow")
    lines.append("")
    
    expanded_query = _expand_aliases(message)
    query_tokens = _tokenize(expanded_query)
    intent = _detect_intent(query_tokens)

    relevant_faqs = _collect_relevant_faqs(db, expanded_query, query_tokens, intent)
    if relevant_faqs:
        lines.append("📚 VERIFIED FAQS & INFORMATION:")
        for faq in relevant_faqs:
            keyword = _faq_keyword_text(faq).strip()
            response = _faq_response_text(faq).strip()
            if keyword and response:
                lines.append(f"  Q: {keyword}")
                lines.append(f"  A: {response}")
        lines.append("")

    departments = db.query(Department).all()
    department_lines = []
    for dept in departments:
        score = _score_overlap(query_tokens, f"{dept.name} {dept.hod}")
        if score >= 1:
            department_lines.append(f"  • {dept.name} - HOD: {dept.hod}")

    if department_lines:
        lines.append("🏫 DEPARTMENTS:")
        lines.extend(department_lines[:6])
        lines.append("")

    fees = db.query(FeeStructure).all()
    fee_lines = []
    for fee in fees:
        score = _score_overlap(query_tokens, f"{fee.branch} {fee.amount}")
        if score >= 1:
            fee_lines.append(f"  • {fee.branch}: ₹{fee.amount}")

    if fee_lines:
        lines.append("💰 FEE STRUCTURE:")
        lines.extend(fee_lines[:6])
        lines.append("")

    clubs = db.query(Club).all()
    club_lines = []
    for club in clubs:
        score = _score_overlap(query_tokens, f"{club.name} {club.category}")
        if score >= 1 or intent == "club":
            club_lines.append(club)

    if club_lines:
        lines.append("🎯 CLUBS & ACTIVITIES:")
        for club in club_lines[:8]:
            lines.append(f"  • {club.name} ({club.category}): {club.description}")
        lines.append("")

    placements = db.query(Placement).all()
    if intent == "placement" or any(token in expanded_query for token in ["company", "placement", "companies"]):
        companies = set()
        branches = set()
        placement_lines = []
        
        for placement in placements:
            companies.add(placement.company_name)
            branches.add(placement.branch)
            if len(placement_lines) < 5:
                score = _score_overlap(query_tokens, f"{placement.student_name} {placement.company_name} {placement.branch}")
                if score >= 1 or intent == "placement":
                    placement_lines.append(f"  • {placement.student_name} ({placement.branch}): {placement.company_name}, ₹{placement.package_lpa} LPA")
        
        if placement_lines:
            lines.append("🎓 PLACEMENT RECORDS:")
            lines.extend(placement_lines)
        elif companies or branches:
            lines.append("📊 PLACEMENT SUMMARY:")
            if companies:
                lines.append(f"  Companies: {', '.join(sorted(list(companies))[:12])}")
            if branches:
                lines.append(f"  Branches: {', '.join(sorted(list(branches)))}")
        lines.append("")
    else:
        # Show top placements by default
        top_placements = sorted(placements, key=lambda p: float(p.package_lpa) if p.package_lpa else 0, reverse=True)[:3]
        if top_placements:
            lines.append("🎯 TOP PLACEMENTS:")
            for placement in top_placements:
                lines.append(f"  • {placement.student_name} ({placement.branch}): {placement.company_name}, ₹{placement.package_lpa} LPA")

    scholarships = db.query(ScholarshipCell).all()
    scholarship_lines = []
    for scholarship in scholarships:
        score = _score_overlap(query_tokens, f"{scholarship.name} {scholarship.designation}")
        if score >= 1 or intent == "scholarship":
            scholarship_lines.append(f"  • {scholarship.name} ({scholarship.designation}): {scholarship.category}, Ph: {scholarship.contact_no}")

    if scholarship_lines:
        lines.append("")
        lines.append("🏆 SCHOLARSHIPS & FINANCIAL AID:")
        lines.extend(scholarship_lines[:6])

    return "\n".join(lines)


def _generate_reply_with_source(db: Session, message: str):
    original_message = message.strip()
    normalized_message = original_message.lower()

    expanded_query = _expand_aliases(normalized_message)
    query_tokens = _tokenize(expanded_query)
    intent = _detect_intent(query_tokens)

    direct_answer = _direct_structured_answer(db, query_tokens)
    if direct_answer:
        return _clean_reply_text(direct_answer[0]), direct_answer[1]

    top_faq = _collect_relevant_faqs(db, expanded_query, query_tokens, intent, limit=1)
    if top_faq and intent == "fee":
        # Deterministic fast path for fee queries when a strong FAQ exists.
        return _clean_reply_text(_faq_response_text(top_faq[0])), "faq"

    # Avoid guessing HOD from weak/general FAQ entries.
    if intent == "hod":
        return _clean_reply_text(OUT_OF_SCOPE_REPLY), "fallback"

    context = build_context(db, normalized_message)
    if not context:
        return _clean_reply_text(OUT_OF_SCOPE_REPLY), "fallback"

    if settings.ENABLE_LLM:
        try:
            # print("DEBUG CONTEXT:", context)
            ai_reply = generate_answer(context, original_message)
            if ai_reply:
                return _clean_reply_text(ai_reply), "groq"
        except Exception as exc:
            # print(f"AI provider error: {exc}")
            pass

    fallback_faqs = _collect_relevant_faqs(db, expanded_query, query_tokens, intent, limit=1)
    if fallback_faqs:
        return _clean_reply_text(_faq_response_text(fallback_faqs[0])), "faq"

    return _clean_reply_text(OUT_OF_SCOPE_REPLY), "fallback"


def generate_reply(db: Session, message: str):
    reply, _source = _generate_reply_with_source(db, message)
    return reply


def generate_reply_with_source(db: Session, message: str):
    return _generate_reply_with_source(db, message)


# Semantic search implementation using sentence embeddings for improved relevance ranking.
def cosine_similarity(a,b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def semantic_faq_search(query: str):
    db= SessionLocal()

    model = _get_embedding_model()
    query_embedding = model.encode(query)
    faqs = db.query(FAQ).filter(FAQ.is_active == True).all()

    best_score = -1
    best_faq = None

    for faq in faqs:
        stored_embedding = np.array(json.loads(faq.embedding))
        score = cosine_similarity(query_embedding, stored_embedding)

        if score > best_score:
            best_score = score
            best_faq = faq
        
    db.close()
    if best_score >= 0.7:  # Threshold for relevance
        return _faq_response_text(best_faq), "semantic", best_score
    else:
        return None


# Main entry point for chatbot response generation, combining structured lookup, semantic search, and LLM fallback.
def get_response(query: str):
    db = SessionLocal()

    try:
        # preprocess (if you already have it)
        query_tokens = set(query.lower().split()) #later optimize with better tokenization and stopword removal

        # 1. Structured answer
        structured = _direct_structured_answer(db, query_tokens)
        if structured:
            return {
                "answer": structured[0],
                "type": "structured"
            }

        # 2. Semantic search
        semantic = semantic_faq_search(query)
        if semantic:
            return {
                "answer": semantic[0],
                "type": "semantic",
                "score": semantic[2]
            }

        # 3. LLM fallback
        answer = generate_answer(query)

        return {
            "answer": answer,
            "type": "llm"
        }

    finally:
        db.close()